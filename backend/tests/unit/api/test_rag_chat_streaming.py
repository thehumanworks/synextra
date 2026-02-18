from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from synextra_backend.api.rag_chat import build_rag_chat_router
from synextra_backend.schemas.rag_chat import RagChatRequest, RagChatResponse


class _FakeOrchestrator:
    def __init__(self, *, answer: str = "assistant answer", should_raise: bool = False) -> None:
        self._answer = answer
        self._should_raise = should_raise
        self.calls: list[tuple[str, RagChatRequest]] = []

    async def handle_message(
        self,
        *,
        session_id: str,
        request: RagChatRequest,
    ) -> RagChatResponse:
        if self._should_raise:
            raise RuntimeError("stream failed")

        self.calls.append((session_id, request))
        return RagChatResponse(
            session_id=session_id,
            mode=request.retrieval_mode,
            answer=self._answer,
            tools_used=["bm25_search"],
            citations=[],
            agent_events=[],
        )


@pytest_asyncio.fixture
async def stream_client() -> AsyncIterator[AsyncClient]:
    app = FastAPI()
    app.state.rag_orchestrator = _FakeOrchestrator()
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_chat_stream_endpoint_streams_answer_text() -> None:
    orchestrator = _FakeOrchestrator(
        answer=(
            "Streaming responses should be emitted as chunks from FastAPI "
            "and reconstructed by the client."
        )
    )
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://testserver") as client,
        client.stream(
            "POST",
            "/v1/rag/sessions/session-1/messages/stream",
            json={
                "prompt": "Explain streaming",
                "retrieval_mode": "vector",
                "reasoning_effort": "high",
            },
        ) as response,
    ):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        parts = [chunk async for chunk in response.aiter_text() if chunk]

    assert "".join(parts) == orchestrator._answer
    assert len(parts) >= 1
    assert len(orchestrator.calls) == 1
    session_id, request = orchestrator.calls[0]
    assert session_id == "session-1"
    assert request.retrieval_mode == "hybrid"
    assert request.reasoning_effort == "high"


@pytest.mark.asyncio
async def test_chat_stream_endpoint_returns_json_error_on_failure() -> None:
    app = FastAPI()
    app.state.rag_orchestrator = _FakeOrchestrator(should_raise=True)
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/rag/sessions/session-err/messages/stream",
            json={"prompt": "Hello"},
        )

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "chat_failed"
    assert body["error"]["recoverable"] is True
