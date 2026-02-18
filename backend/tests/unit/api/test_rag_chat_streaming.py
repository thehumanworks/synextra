from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from synextra_backend.api.rag_chat import (
    _STREAM_EVENTS_SEPARATOR,
    _STREAM_METADATA_SEPARATOR,
    build_rag_chat_router,
)
from synextra_backend.schemas.rag_chat import (
    RagChatRequest,
    RagChatResponse,
    RagCitation,
    ReasoningEffort,
    SearchEvent,
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
        stream_events: list[Any] | None = None,
        return_events_in_collect_result: bool = True,
        raise_after_stream_events: bool = False,
    ) -> None:
        self._tokens = tokens or ["Hello", " world", "!"]
        self._citations = citations or []
        self._should_raise = should_raise
        self._stream_events = stream_events or []
        self._return_events_in_collect_result = return_events_in_collect_result
        self._raise_after_stream_events = raise_after_stream_events
        self._session_memory = SessionMemory()
        self.collect_evidence_calls: list[tuple[str, RagChatRequest]] = []

    async def handle_message(self, *, session_id: str, request: RagChatRequest) -> RagChatResponse:
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
        self,
        *,
        session_id: str,
        request: RagChatRequest,
        event_sink: Callable[[Any], Awaitable[None]] | None = None,
    ) -> tuple[RetrievalResult, list[Any]]:
        if self._should_raise and not self._raise_after_stream_events:
            raise RuntimeError("stream failed")
        self.collect_evidence_calls.append((session_id, request))

        if event_sink is not None:
            for event in self._stream_events:
                await event_sink(event)
                await asyncio.sleep(0)

        if self._should_raise and self._raise_after_stream_events:
            raise RuntimeError("stream failed after events")

        retrieval = RetrievalResult(
            answer="".join(self._tokens),
            evidence=[],
            citations=self._citations,
            tools_used=["bm25_search"],
        )
        if self._return_events_in_collect_result:
            return retrieval, self._stream_events
        return retrieval, []

    async def stream_synthesis(
        self,
        *,
        prompt: str,
        retrieval: RetrievalResult,
        reasoning_effort: ReasoningEffort,
    ) -> AsyncIterator[str]:
        for token in self._tokens:
            yield token


def _parse_stream_body(body: str) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """Parse the full stream body into (events, answer, metadata).

    The stream format is:
      <event_json_lines...>\x1d<answer_tokens>\x1e<metadata_json>
    """
    # Split off the metadata trailer first
    meta_idx = body.rfind(_STREAM_METADATA_SEPARATOR)
    assert meta_idx != -1, "metadata separator not found in stream body"
    pre_meta = body[:meta_idx]
    metadata = json.loads(body[meta_idx + 1 :])

    # Split events from answer tokens using the group separator
    events_sep_idx = pre_meta.find(_STREAM_EVENTS_SEPARATOR)
    assert events_sep_idx != -1, "events separator not found in stream body"
    events_section = pre_meta[:events_sep_idx]
    answer = pre_meta[events_sep_idx + 1 :]

    events: list[dict[str, Any]] = []
    for line in events_section.splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))

    return events, answer, metadata


def _split_stream_body(body: str) -> tuple[str, dict[str, Any]]:
    """Legacy helper — strips the events section and returns (answer, metadata)."""
    _, answer, metadata = _parse_stream_body(body)
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
    assert any(turn.role == "assistant" and turn.content == "Answer text." for turn in turns)


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
async def test_stream_uses_event_sink_even_when_collect_evidence_event_list_is_empty() -> None:
    """Events are streamed from the live sink, not only from collect_evidence return values."""
    events = [
        SearchEvent(
            event="search",
            tool="bm25_search",
            query="live-event",
            timestamp="2024-01-01T00:00:00+00:00",
        ),
    ]
    orchestrator = _FakeOrchestrator(
        tokens=["Answer."],
        stream_events=events,
        return_events_in_collect_result=False,
    )
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/rag/sessions/live-events/messages/stream",
            json={"prompt": "hello"},
        )

    assert response.status_code == 200
    parsed_events, answer, _metadata = _parse_stream_body(response.text)
    assert len(parsed_events) == 1
    assert parsed_events[0]["tool"] == "bm25_search"
    assert parsed_events[0]["query"] == "live-event"
    assert answer == "Answer."


@pytest.mark.asyncio
async def test_stream_handles_retrieval_failure_after_events_have_started() -> None:
    """If retrieval fails after events were emitted, stream ends with fallback answer + metadata."""
    events = [
        SearchEvent(
            event="search",
            tool="bm25_search",
            query="live-event",
            timestamp="2024-01-01T00:00:00+00:00",
        ),
    ]
    orchestrator = _FakeOrchestrator(
        should_raise=True,
        raise_after_stream_events=True,
        stream_events=events,
    )
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/rag/sessions/live-events-fail/messages/stream",
            json={"prompt": "hello"},
        )

    assert response.status_code == 200
    parsed_events, answer, metadata = _parse_stream_body(response.text)
    assert len(parsed_events) == 1
    assert parsed_events[0]["tool"] == "bm25_search"
    assert "internal error" in answer
    assert metadata["tools_used"] == ["chat_failed"]
    assert metadata["citations"] == []


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
            json={"prompt": "hello", "retrieval_mode": "embedded"},
        )

    assert len(orchestrator.collect_evidence_calls) == 1
    _, request = orchestrator.collect_evidence_calls[0]
    assert request.retrieval_mode == "hybrid"


@pytest.mark.asyncio
async def test_stream_emits_events_before_group_separator() -> None:
    """Events are emitted as JSON lines before the \\x1d separator."""
    events = [
        SearchEvent(
            event="search",
            tool="bm25_search",
            query="test",
            timestamp="2024-01-01T00:00:00+00:00",
        ),
    ]
    orchestrator = _FakeOrchestrator(tokens=["Answer."], stream_events=events)
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/rag/sessions/events-test/messages/stream",
            json={"prompt": "hello"},
        )

    assert response.status_code == 200
    body = response.text
    parsed_events, answer, _metadata = _parse_stream_body(body)

    # Events section should have one JSON object
    assert len(parsed_events) == 1
    assert parsed_events[0]["event"] == "search"
    assert parsed_events[0]["tool"] == "bm25_search"
    assert parsed_events[0]["query"] == "test"

    # Answer tokens are after the separator
    assert answer == "Answer."


@pytest.mark.asyncio
async def test_stream_events_separator_present_even_with_no_events() -> None:
    """The \\x1d separator is always present even when there are no events."""
    orchestrator = _FakeOrchestrator(tokens=["Hi."], stream_events=[])
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/rag/sessions/no-events/messages/stream",
            json={"prompt": "hello"},
        )

    body = response.text
    assert _STREAM_EVENTS_SEPARATOR in body
    assert _STREAM_METADATA_SEPARATOR in body

    parsed_events, answer, _ = _parse_stream_body(body)
    assert parsed_events == []
    assert answer == "Hi."


@pytest.mark.asyncio
async def test_stream_multiple_events_are_newline_separated() -> None:
    """Multiple events appear as newline-delimited JSON before \\x1d."""
    from synextra_backend.schemas.rag_chat import ReviewEvent

    ts0 = "2024-01-01T00:00:00+00:00"
    ts1 = "2024-01-01T00:00:01+00:00"
    ts2 = "2024-01-01T00:00:02+00:00"
    events: list[Any] = [
        SearchEvent(event="search", tool="bm25_search", query="q1", timestamp=ts0),
        SearchEvent(event="search", tool="read_document", page=0, timestamp=ts1),
        ReviewEvent(event="review", iteration=1, verdict="approved", timestamp=ts2),
    ]
    orchestrator = _FakeOrchestrator(tokens=["Done."], stream_events=events)
    app = FastAPI()
    app.state.rag_orchestrator = orchestrator
    app.include_router(build_rag_chat_router())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/rag/sessions/multi-events/messages/stream",
            json={"prompt": "hello"},
        )

    body = response.text
    parsed_events, answer, _ = _parse_stream_body(body)

    assert len(parsed_events) == 3
    assert parsed_events[0]["event"] == "search"
    assert parsed_events[0]["tool"] == "bm25_search"
    assert parsed_events[1]["event"] == "search"
    assert parsed_events[1]["tool"] == "read_document"
    assert parsed_events[2]["event"] == "review"
    assert parsed_events[2]["verdict"] == "approved"
    assert answer == "Done."
