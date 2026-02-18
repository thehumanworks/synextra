from __future__ import annotations

import types
from typing import Any

import pytest

from synextra_backend.repositories.rag_document_repository import InMemoryRagDocumentRepository
from synextra_backend.retrieval.bm25_search import Bm25IndexStore
from synextra_backend.retrieval.types import EvidenceChunk
from synextra_backend.schemas.rag_chat import RagChatRequest
from synextra_backend.services.rag_agent_orchestrator import (
    AgentCallResult,
    RagAgentOrchestrator,
    RetrievalResult,
    _simple_summary,
)
from synextra_backend.services.session_memory import SessionMemory


@pytest.fixture(autouse=True)
def _set_required_openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def _chunk(
    *,
    chunk_id: str,
    text: str,
    document_id: str = "doc",
    page_number: int | None = 0,
    score: float = 1.0,
    source_tool: str = "bm25_search",
) -> EvidenceChunk:
    return EvidenceChunk(
        document_id=document_id,
        chunk_id=chunk_id,
        page_number=page_number,
        text=text,
        score=score,
        source_tool=source_tool,
    )


def _orchestrator() -> RagAgentOrchestrator:
    return RagAgentOrchestrator(
        repository=InMemoryRagDocumentRepository(),
        bm25_store=Bm25IndexStore(),
        session_memory=SessionMemory(),
    )


def test_simple_summary_collapses_internal_newlines() -> None:
    summary = _simple_summary(
        [
            _chunk(
                chunk_id="c1",
                text="application\nmissing\n<EOS>\nopinion\nperfect\nshould\n<pad>\nnever\nwhat",
            )
        ]
    )

    assert "\n" not in summary
    assert "application missing <EOS> opinion" in summary


def test_build_citations_dedupes_equivalent_quotes_across_chunks() -> None:
    orchestrator = _orchestrator()
    shared_prefix = "token " * 35

    citations = orchestrator._build_citations(
        [
            _chunk(
                chunk_id="c1",
                page_number=14,
                text=f"{shared_prefix}alpha tail",
            ),
            _chunk(
                chunk_id="c2",
                page_number=13,
                text=f"{shared_prefix}beta tail",
            ),
            _chunk(
                chunk_id="c3",
                page_number=6,
                text=(
                    "The Transformer uses multi-head attention in both encoder and "
                    "decoder layers."
                ),
            ),
        ]
    )

    assert len(citations) == 2
    assert citations[0].chunk_id == "c1"
    assert citations[1].chunk_id == "c3"


@pytest.mark.asyncio
async def test_synthesize_answer_uses_openai_with_required_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNEXTRA_CHAT_MODEL", "gpt-test-model")

    captured: dict[str, object] = {}

    class _FakeResponses:
        def create(
            self, *, model: str, input: object, instructions: str, reasoning: object
        ) -> object:
            captured["model"] = model
            captured["input"] = input
            captured["instructions"] = instructions
            captured["reasoning"] = reasoning
            return types.SimpleNamespace(output_text="Generated answer")

    class _FakeOpenAI:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == "test-key"
            self.responses = _FakeResponses()

    monkeypatch.setattr(
        "synextra_backend.services.rag_agent_orchestrator.OpenAI",
        _FakeOpenAI,
    )

    orchestrator = _orchestrator()
    evidence = [
        _chunk(
            chunk_id="c1",
            page_number=2,
            text="The Transformer is an encoder-decoder architecture based on attention.",
        )
    ]
    citations = orchestrator._build_citations(evidence)
    answer = await orchestrator._synthesize_answer(
        prompt="What is the Transformer model described in the paper?",
        evidence=evidence,
        citations=citations,
        reasoning_effort="high",
    )

    assert answer == "Generated answer"
    assert captured["model"] == "gpt-test-model"
    assert isinstance(captured["input"], str)
    assert "Question: What is the Transformer model described in the paper?" in str(
        captured["input"]
    )
    assert "Answer the user's question using only the provided evidence." in str(
        captured.get("instructions", "")
    )
    assert captured["reasoning"] == {"effort": "high"}


@pytest.mark.asyncio
async def test_run_retrieval_prefers_agent_tool_calls_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class _FakeOpenAI:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == "test-key"
            pass

    monkeypatch.setattr(
        "synextra_backend.services.rag_agent_orchestrator.OpenAI",
        _FakeOpenAI,
    )

    orchestrator = _orchestrator()

    def _fake_call_agent(**_kwargs: Any) -> AgentCallResult:
        return AgentCallResult(
            output_text="Agent-grounded answer",
            evidence=[
                _chunk(
                    chunk_id="c-agent",
                    text="Retrieved via tool call.",
                    source_tool="openai_vector_store_search",
                )
            ],
            tools_used=["bm25_search", "vector_search"],
        )

    async def _manual_should_not_run(**_kwargs: Any) -> tuple[list[EvidenceChunk], list[str]]:
        raise AssertionError("manual retrieval should not be used when agent path succeeds")

    monkeypatch.setattr(orchestrator, "_call_agent", _fake_call_agent)
    monkeypatch.setattr(orchestrator, "_run_manual_retrieval", _manual_should_not_run)

    result = await orchestrator._run_retrieval(
        prompt="What is the model?",
        mode="hybrid",
        reasoning_effort="high",
    )

    assert result.answer == "Agent-grounded answer"
    assert result.evidence
    assert result.citations
    assert result.citations[0].source_tool == "openai_vector_store_search"
    assert "vector_search" in result.tools_used


@pytest.mark.asyncio
async def test_collect_evidence_returns_retrieval_result_without_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeOpenAI:
        def __init__(self, *, api_key: str) -> None:
            pass

    monkeypatch.setattr(
        "synextra_backend.services.rag_agent_orchestrator.OpenAI",
        _FakeOpenAI,
    )
    monkeypatch.setattr(
        "synextra_backend.services.rag_agent_orchestrator.AsyncOpenAI",
        _FakeOpenAI,
    )

    orchestrator = _orchestrator()

    def _fake_call_agent(**_kwargs: Any) -> AgentCallResult:
        return AgentCallResult(
            output_text="Agent answer (should be discarded for streaming)",
            evidence=[
                _chunk(chunk_id="c1", text="Evidence text.", source_tool="bm25_search"),
            ],
            tools_used=["bm25_search"],
        )

    monkeypatch.setattr(orchestrator, "_call_agent", _fake_call_agent)

    request = RagChatRequest(prompt="What?", retrieval_mode="hybrid")
    result = await orchestrator.collect_evidence(session_id="s1", request=request)

    assert isinstance(result, RetrievalResult)
    assert len(result.evidence) == 1
    assert len(result.citations) == 1
    assert "bm25_search" in result.tools_used
    # RetrievalResult has no answer field
    assert not hasattr(result, "answer")


@pytest.mark.asyncio
async def test_stream_synthesis_yields_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNEXTRA_CHAT_MODEL", "gpt-test")

    emitted_tokens = ["The ", "Transformer ", "model."]

    class _FakeEvent:
        def __init__(self, event_type: str, delta: str = "") -> None:
            self.type = event_type
            self.delta = delta

    class _FakeStream:
        def __init__(self) -> None:
            self._events = [
                _FakeEvent("response.output_text.delta", "The "),
                _FakeEvent("response.output_text.delta", "Transformer "),
                _FakeEvent("response.output_text.delta", "model."),
                _FakeEvent("response.output_text.done"),
                _FakeEvent("response.completed"),
            ]
            self._idx = 0

        def __aiter__(self) -> _FakeStream:
            return self

        async def __anext__(self) -> _FakeEvent:
            if self._idx >= len(self._events):
                raise StopAsyncIteration
            event = self._events[self._idx]
            self._idx += 1
            return event

    class _FakeAsyncResponses:
        async def create(self, **kwargs: Any) -> _FakeStream:
            assert kwargs.get("stream") is True
            return _FakeStream()

    class _FakeAsyncOpenAI:
        def __init__(self, *, api_key: str) -> None:
            self.responses = _FakeAsyncResponses()

    monkeypatch.setattr(
        "synextra_backend.services.rag_agent_orchestrator.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )
    monkeypatch.setattr(
        "synextra_backend.services.rag_agent_orchestrator.OpenAI",
        lambda **_: types.SimpleNamespace(),
    )

    orchestrator = _orchestrator()
    retrieval = RetrievalResult(
        evidence=[_chunk(chunk_id="c1", text="Evidence.")],
        citations=orchestrator._build_citations(
            [_chunk(chunk_id="c1", text="Evidence.")]
        ),
        tools_used=["bm25_search"],
    )

    tokens: list[str] = []
    async for token in orchestrator.stream_synthesis(
        prompt="What is the Transformer?",
        retrieval=retrieval,
        reasoning_effort="medium",
    ):
        tokens.append(token)

    assert tokens == emitted_tokens
    assert "".join(tokens) == "The Transformer model."


@pytest.mark.asyncio
async def test_stream_synthesis_falls_back_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeAsyncResponses:
        async def create(self, **kwargs: Any) -> None:
            raise RuntimeError("OpenAI API error")

    class _FakeAsyncOpenAI:
        def __init__(self, *, api_key: str) -> None:
            self.responses = _FakeAsyncResponses()

    monkeypatch.setattr(
        "synextra_backend.services.rag_agent_orchestrator.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )
    monkeypatch.setattr(
        "synextra_backend.services.rag_agent_orchestrator.OpenAI",
        lambda **_: types.SimpleNamespace(),
    )

    orchestrator = _orchestrator()
    evidence = [
        _chunk(
            chunk_id="c1",
            text="The Transformer is based on attention. It uses multi-head attention.",
        ),
    ]
    retrieval = RetrievalResult(
        evidence=evidence,
        citations=orchestrator._build_citations(evidence),
        tools_used=["bm25_search"],
    )

    tokens: list[str] = []
    async for token in orchestrator.stream_synthesis(
        prompt="What?",
        retrieval=retrieval,
        reasoning_effort="medium",
    ):
        tokens.append(token)

    # Falls back to _simple_summary which returns joined sentences
    full_text = "".join(tokens)
    assert "Transformer" in full_text
    assert "attention" in full_text
