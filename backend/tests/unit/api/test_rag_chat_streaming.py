from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from synextra_backend.api.rag_chat import _STREAM_METADATA_SEPARATOR, build_rag_chat_router
from synextra_backend.schemas.rag_chat import (
    RagChatRequest,
    RagChatResponse,
    RagCitation,
    ReasoningEffort,
)
from synextra_backend.services.rag_agent_orchestrator import RetrievalResult
from synextra_backend.services.session_memory import SessionMemory


class _FakeOrchestrator:
    def __init__(
        self,
        *,
        tokens: list[str] | None = None,
        citations: list[RagCitation] | None = None,
        should_raise: bool = False,
    ) -> None:
        self._tokens = tokens or ["Hello", " world", "!"]
        self._citations = citations or []
        self._should_raise = should_raise
        self._session_memory = SessionMemory()
        self.collect_evidence_calls: list[tuple[str, RagChatRequest]] = []

    async def handle_message(
        self, *, session_id: str, request: RagChatRequest
    ) -> RagChatResponse:
        if self._should_raise:
            raise RuntimeError("stream failed")
        return RagChatResponse(
            session_id=session_id,
            mode=request.retrieval_mode,
            answer="".join(self._tokens),
            tools_used=["bm25_search"],
            citations=self._citations,
            agent_events=[],
        )

    async def collect_evidence(
        self, *, session_id: str, request: RagChatRequest
    ) -> RetrievalResult:
        if self._should_raise:
            raise RuntimeError("stream failed")
        self.collect_evidence_calls.append((session_id, request))
        return RetrievalResult(
            evidence=[],
            citations=self._citations,
            tools_used=["bm25_search"],
        )

    async def stream_synthesis(
        self,
        *,
        prompt: str,
        retrieval: RetrievalResult,
        reasoning_effort: ReasoningEffort,
    ) -> AsyncIterator[str]:
        for token in self._tokens:
            yield token


def _split_stream_body(body: str) -> tuple[str, dict]:
    idx = body.rfind(_STREAM_METADATA_SEPARATOR)
    assert idx != -1, "metadata separator not found in stream body"
    answer = body[:idx]
    metadata = json.loads(body[idx + 1 :])
    return answer, metadata


@pytest.mark.asyncio
async def test_stream_yields_individual_tokens() -> None:
    """Verify tokens arrive individually, not in fixed-size chunks."""
    tokens = ["The ", "answer ", "is ", "42."]
    orchestrator = _FakeOrchestrator(tokens=tokens)
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://testserver") as client,
        client.stream(
            "POST",
            "/v1/rag/sessions/s1/messages/stream",
            json={"prompt": "What is the answer?"},
        ) as response,
    ):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        parts = [chunk async for chunk in response.aiter_text() if chunk]

    full_body = "".join(parts)
    answer, metadata = _split_stream_body(full_body)
    assert answer == "The answer is 42."
    assert metadata["tools_used"] == ["bm25_search"]


@pytest.mark.asyncio
async def test_stream_includes_citations_in_metadata() -> None:
    citations = [
        RagCitation(
            document_id="doc-1",
            chunk_id="c1",
            page_number=3,
            supporting_quote="The attention mechanism.",
            source_tool="bm25",
            score=0.85,
        ),
    ]
    orchestrator = _FakeOrchestrator(
        tokens=["Here ", "is ", "the answer."],
        citations=citations,
    )
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/rag/sessions/cite/messages/stream",
            json={"prompt": "What?"},
        )

    assert response.status_code == 200
    answer, metadata = _split_stream_body(response.text)
    assert answer == "Here is the answer."
    assert len(metadata["citations"]) == 1
    assert metadata["citations"][0]["document_id"] == "doc-1"


@pytest.mark.asyncio
async def test_stream_sets_no_buffering_header() -> None:
    orchestrator = _FakeOrchestrator()
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/rag/sessions/s1/messages/stream",
            json={"prompt": "hello"},
        )

    assert response.headers.get("x-accel-buffering") == "no"
    assert "no-cache" in response.headers.get("cache-control", "")


@pytest.mark.asyncio
async def test_stream_records_assistant_turn_in_session_memory() -> None:
    orchestrator = _FakeOrchestrator(tokens=["Answer ", "text."])
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/v1/rag/sessions/mem-test/messages/stream",
            json={"prompt": "hello"},
        )

    turns = orchestrator._session_memory.list_turns("mem-test")
    assert any(
        turn.role == "assistant" and turn.content == "Answer text."
        for turn in turns
    )


@pytest.mark.asyncio
async def test_stream_returns_json_error_on_retrieval_failure() -> None:
    app = FastAPI()
    app.state.rag_orchestrator = _FakeOrchestrator(should_raise=True)
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/rag/sessions/err/messages/stream",
            json={"prompt": "Hello"},
        )

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "chat_failed"
    assert body["error"]["recoverable"] is True


@pytest.mark.asyncio
async def test_stream_forces_hybrid_retrieval_mode() -> None:
    orchestrator = _FakeOrchestrator()
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/v1/rag/sessions/s1/messages/stream",
            json={"prompt": "hello", "retrieval_mode": "vector"},
        )

    assert len(orchestrator.collect_evidence_calls) == 1
    _, request = orchestrator.collect_evidence_calls[0]
    assert request.retrieval_mode == "hybrid"
