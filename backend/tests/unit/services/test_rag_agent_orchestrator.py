from __future__ import annotations

import json
from typing import Any

import pytest
from synextra.repositories.rag_document_repository import InMemoryRagDocumentRepository
from synextra.retrieval.bm25_search import Bm25IndexStore
from synextra.retrieval.types import EvidenceChunk
from synextra.schemas.rag_chat import RagChatRequest
from synextra.services.document_store import DocumentStore, PageText
from synextra.services.rag_agent_orchestrator import (
    AgentCallResult,
    JudgeVerdict,
    RagAgentOrchestrator,
    RetrievalResult,
    _simple_summary,
)
from synextra.services.session_memory import SessionMemory


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


def _document_store() -> DocumentStore:
    store = DocumentStore()
    store.store_pages(
        document_id="doc",
        filename="paper.pdf",
        pages=[
            PageText(page_number=0, lines=["Line one.", "Line two."], line_count=2),
            PageText(page_number=1, lines=["Page two line one."], line_count=1),
        ],
    )
    return store


def _orchestrator(document_store: DocumentStore | None = None) -> RagAgentOrchestrator:
    return RagAgentOrchestrator(
        repository=InMemoryRagDocumentRepository(),
        bm25_store=Bm25IndexStore(),
        session_memory=SessionMemory(),
        document_store=document_store or _document_store(),
    )


class _FakeRunResult:
    """Mimics agents.RunResult for non-streamed Runner.run()."""

    def __init__(self, final_output: str) -> None:
        self.final_output = final_output


# ---------------------------------------------------------------------------
# Original Tests
# ---------------------------------------------------------------------------


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
                    "The Transformer uses multi-head attention in both encoder and decoder layers."
                ),
            ),
        ]
    )

    assert len(citations) == 2
    assert citations[0].chunk_id == "c1"
    assert citations[1].chunk_id == "c3"


@pytest.mark.asyncio
async def test_synthesize_answer_is_programmatic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fail_run(agent: Any, **kwargs: Any) -> None:
        raise AssertionError("Runner.run must not be called for synthesis")

    monkeypatch.setattr(
        "synextra.services.rag_agent_orchestrator.Runner.run",
        staticmethod(_fail_run),
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

    assert "Transformer" in answer
    assert "attention" in answer


@pytest.mark.asyncio
async def test_run_retrieval_prefers_agent_tool_calls_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = _orchestrator()

    async def _fake_call_agent(**_kwargs: Any) -> AgentCallResult:
        return AgentCallResult(
            output_text="Agent-grounded answer",
            evidence=[
                _chunk(
                    chunk_id="c-agent",
                    text="Retrieved via read_document tool call.",
                    source_tool="read_document",
                )
            ],
            tools_used=["bm25_search", "read_document"],
        )

    monkeypatch.setattr(orchestrator, "_call_agent", _fake_call_agent)

    result = await orchestrator._run_retrieval(
        prompt="What is the model?",
        reasoning_effort="high",
    )

    assert result.answer == "Agent-grounded answer"
    assert result.evidence
    assert result.citations
    assert result.citations[0].source_tool == "read_document"
    assert "read_document" in result.tools_used


@pytest.mark.asyncio
async def test_collect_evidence_returns_retrieval_result_with_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = _orchestrator()

    async def _fake_call_agent(**_kwargs: Any) -> AgentCallResult:
        return AgentCallResult(
            output_text="Agent answer (should be used for streaming)",
            evidence=[
                _chunk(chunk_id="c1", text="Evidence text.", source_tool="bm25_search"),
            ],
            tools_used=["bm25_search"],
        )

    monkeypatch.setattr(orchestrator, "_call_agent", _fake_call_agent)

    request = RagChatRequest(prompt="What?")
    result, events = await orchestrator.collect_evidence(session_id="s1", request=request)

    assert isinstance(result, RetrievalResult)
    assert result.answer == "Agent answer (should be used for streaming)"
    assert len(result.evidence) == 1
    assert len(result.citations) == 1
    assert "bm25_search" in result.tools_used
    assert events == []


@pytest.mark.asyncio
async def test_stream_synthesis_yields_tokens() -> None:
    emitted_answer = "The Transformer model."

    orchestrator = _orchestrator()
    retrieval = RetrievalResult(
        answer=emitted_answer,
        evidence=[_chunk(chunk_id="c1", text="Evidence.")],
        citations=orchestrator._build_citations([_chunk(chunk_id="c1", text="Evidence.")]),
        tools_used=["bm25_search"],
    )

    tokens: list[str] = []
    async for token in orchestrator.stream_synthesis(
        prompt="What is the Transformer?",
        retrieval=retrieval,
        reasoning_effort="medium",
    ):
        tokens.append(token)

    assert "".join(tokens) == emitted_answer


@pytest.mark.asyncio
async def test_stream_synthesis_falls_back_to_simple_summary_when_answer_missing() -> None:
    orchestrator = _orchestrator()
    evidence = [
        _chunk(
            chunk_id="c1",
            text="The Transformer is based on attention. It uses multi-head attention.",
        ),
    ]
    retrieval = RetrievalResult(
        answer="",
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

    full_text = "".join(tokens)
    assert "Transformer" in full_text
    assert "attention" in full_text


def test_agent_instructions_include_document_info() -> None:
    orchestrator = _orchestrator()
    instructions = orchestrator._agent_instructions()

    assert "paper.pdf" in instructions
    assert "read_document" in instructions
    assert "bm25_search" in instructions


def test_agent_instructions_mandate_both_tools() -> None:
    orchestrator = _orchestrator()
    instructions = orchestrator._agent_instructions()

    assert "MUST use both" in instructions
    assert "MANDATORY" in instructions


def test_read_document_returns_evidence_chunk() -> None:
    orchestrator = _orchestrator()

    result = orchestrator.run_read_document(
        document_id="doc",
        page=0,
    )

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], EvidenceChunk)
    assert result[0].page_number == 0
    assert result[0].source_tool == "read_document"
    assert "Line one" in result[0].text


def test_read_document_with_line_range() -> None:
    orchestrator = _orchestrator()

    result = orchestrator.run_read_document(
        document_id="doc",
        page=0,
        start_line=1,
        end_line=1,
    )

    assert len(result) == 1
    assert "Line one" in result[0].text
    assert "Line two" not in result[0].text


def test_create_agent_tools_produces_named_tools() -> None:
    """Verify that _create_agent_tools returns correctly named FunctionTool objects."""
    orchestrator = _orchestrator()

    collector: list[EvidenceChunk] = []
    tools = orchestrator._create_agent_tools(collector)

    assert len(tools) == 3
    tool_names = [t.name for t in tools]
    assert "bm25_search" in tool_names
    assert "read_document" in tool_names
    assert "parallel_search" in tool_names


@pytest.mark.asyncio
async def test_synthesize_answer_returns_no_evidence_message() -> None:
    orchestrator = _orchestrator()
    evidence: list[EvidenceChunk] = []
    citations: list[Any] = []

    answer = await orchestrator._synthesize_answer(
        prompt="What is the Transformer?",
        evidence=evidence,
        citations=citations,
        reasoning_effort="medium",
    )

    assert "couldn't find relevant information" in answer


@pytest.mark.asyncio
async def test_run_retrieval_falls_back_to_bm25_when_agent_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When _call_agent raises, _run_retrieval falls back to deterministic behavior."""

    async def _failing_call_agent(**_kwargs: Any) -> AgentCallResult:
        raise RuntimeError("Agent failed")

    orchestrator = _orchestrator()
    monkeypatch.setattr(orchestrator, "_call_agent", _failing_call_agent)

    result = await orchestrator._run_retrieval(
        prompt="anything",
        reasoning_effort="medium",
    )

    assert "agent_retrieval_failed" in result.tools_used
    assert result.answer == "I could not find reliable information to answer your question."


@pytest.mark.asyncio
async def test_stream_synthesis_yields_no_evidence_message() -> None:
    """When retrieval has no evidence, stream_synthesis yields a fixed message."""
    orchestrator = _orchestrator()
    retrieval = RetrievalResult(answer="", evidence=[], citations=[], tools_used=[])

    tokens: list[str] = []
    async for token in orchestrator.stream_synthesis(
        prompt="What?",
        retrieval=retrieval,
        reasoning_effort="medium",
    ):
        tokens.append(token)

    full = "".join(tokens)
    assert "couldn't find relevant information" in full


def test_chat_model_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from synextra.services.rag_agent_orchestrator import _chat_model

    assert _chat_model() == "gpt-5.2"

    monkeypatch.setenv("SYNEXTRA_CHAT_MODEL", "custom-model")
    assert _chat_model() == "custom-model"


# ---------------------------------------------------------------------------
# Task 1: parallel_search tool tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parallel_search_tool_runs_bm25_queries_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """parallel_search with bm25_search items collects evidence for all queries."""
    orchestrator = _orchestrator()

    # Patch bm25 search to return predictable results
    call_count = 0

    def _fake_bm25_search(*, query: str, top_k: int = 8) -> list[EvidenceChunk]:
        nonlocal call_count
        call_count += 1
        return [
            _chunk(
                chunk_id=f"c{call_count}",
                text=f"Result for query: {query}",
                source_tool="bm25_search",
            )
        ]

    monkeypatch.setattr(orchestrator._bm25_store, "search", _fake_bm25_search)

    collector: list[EvidenceChunk] = []
    tools = orchestrator._create_agent_tools(collector)
    parallel_tool = next(t for t in tools if t.name == "parallel_search")

    inner_queries = json.dumps(
        [
            {"type": "bm25_search", "query": "Transformer architecture", "top_k": 3},
            {"type": "bm25_search", "query": "attention mechanism", "top_k": 3},
        ]
    )
    # The SDK's on_invoke_tool expects a JSON object mapping param names to values
    tool_input = json.dumps({"queries": inner_queries})

    result_json = await parallel_tool.on_invoke_tool(None, tool_input)
    result = json.loads(result_json)

    # Should have 2 result sets (one per query)
    assert isinstance(result, list)
    assert len(result) == 2
    # Each result set should contain evidence chunks
    assert isinstance(result[0], list)
    assert isinstance(result[1], list)
    # Evidence collector should have results from both queries
    assert len(collector) == 2
    assert call_count == 2


@pytest.mark.asyncio
async def test_parallel_search_tool_runs_read_document_queries() -> None:
    """parallel_search with read_document items collects page content."""
    orchestrator = _orchestrator()

    collector: list[EvidenceChunk] = []
    tools = orchestrator._create_agent_tools(collector)
    parallel_tool = next(t for t in tools if t.name == "parallel_search")

    inner_queries = json.dumps(
        [
            {"type": "read_document", "page": 0},
            {"type": "read_document", "page": 1},
        ]
    )
    tool_input = json.dumps({"queries": inner_queries})

    result_json = await parallel_tool.on_invoke_tool(None, tool_input)
    result = json.loads(result_json)

    assert isinstance(result, list)
    assert len(result) == 2
    # Both page reads should succeed
    assert "error" not in result[0]
    assert "error" not in result[1]
    # Evidence collector should have both pages
    assert len(collector) == 2
    page_numbers = {c.page_number for c in collector}
    assert 0 in page_numbers
    assert 1 in page_numbers


@pytest.mark.asyncio
async def test_parallel_search_tool_handles_mixed_query_types() -> None:
    """parallel_search can mix bm25_search and read_document in one call."""
    orchestrator = _orchestrator()

    collector: list[EvidenceChunk] = []
    tools = orchestrator._create_agent_tools(collector)
    parallel_tool = next(t for t in tools if t.name == "parallel_search")

    inner_queries = json.dumps(
        [
            {"type": "bm25_search", "query": "line one", "top_k": 2},
            {"type": "read_document", "page": 0},
        ]
    )
    tool_input = json.dumps({"queries": inner_queries})

    result_json = await parallel_tool.on_invoke_tool(None, tool_input)
    result = json.loads(result_json)

    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_parallel_search_tool_accepts_structured_query_lists() -> None:
    """parallel_search accepts native list payloads (not only encoded JSON strings)."""
    orchestrator = _orchestrator()

    collector: list[EvidenceChunk] = []
    tools = orchestrator._create_agent_tools(collector)
    parallel_tool = next(t for t in tools if t.name == "parallel_search")

    tool_input = json.dumps(
        {
            "queries": [
                {"type": "bm25_search", "query": "line one", "top_k": 2},
                {"type": "read_document", "page": 0},
            ]
        }
    )

    result_json = await parallel_tool.on_invoke_tool(None, tool_input)
    result = json.loads(result_json)

    assert isinstance(result, list)
    assert len(result) == 2
    assert "error" not in result[0]
    assert "error" not in result[1]
    assert len(collector) >= 1


@pytest.mark.asyncio
async def test_parallel_search_tool_returns_error_for_invalid_json() -> None:
    """parallel_search returns an error dict when given invalid JSON."""
    orchestrator = _orchestrator()

    collector: list[EvidenceChunk] = []
    tools = orchestrator._create_agent_tools(collector)
    parallel_tool = next(t for t in tools if t.name == "parallel_search")

    # Pass invalid JSON as the inner "queries" value
    tool_input = json.dumps({"queries": "not-valid-json"})
    result_json = await parallel_tool.on_invoke_tool(None, tool_input)
    result = json.loads(result_json)

    assert "error" in result
    assert len(collector) == 0


@pytest.mark.asyncio
async def test_parallel_search_tool_returns_error_for_unknown_type() -> None:
    """parallel_search returns an error for unknown query type."""
    orchestrator = _orchestrator()

    collector: list[EvidenceChunk] = []
    tools = orchestrator._create_agent_tools(collector)
    parallel_tool = next(t for t in tools if t.name == "parallel_search")

    inner_queries = json.dumps([{"type": "unknown_tool", "query": "test"}])
    tool_input = json.dumps({"queries": inner_queries})
    result_json = await parallel_tool.on_invoke_tool(None, tool_input)
    result = json.loads(result_json)

    assert isinstance(result, list)
    assert "error" in result[0]


@pytest.mark.asyncio
async def test_parallel_search_emits_events_to_collector() -> None:
    """parallel_search adds SearchEvent entries to the event_collector."""
    from synextra.schemas.rag_chat import SearchEvent

    orchestrator = _orchestrator()

    collector: list[EvidenceChunk] = []
    event_collector: list[Any] = []
    tools = orchestrator._create_agent_tools(collector, event_collector)
    parallel_tool = next(t for t in tools if t.name == "parallel_search")

    inner_queries = json.dumps(
        [
            {"type": "bm25_search", "query": "test query", "top_k": 2},
            {"type": "read_document", "page": 0},
        ]
    )
    tool_input = json.dumps({"queries": inner_queries})

    await parallel_tool.on_invoke_tool(None, tool_input)

    # Two SearchEvents should have been appended
    assert len(event_collector) == 2
    assert all(isinstance(e, SearchEvent) for e in event_collector)
    assert event_collector[0].tool == "bm25_search"
    assert event_collector[0].query == "test query"
    assert event_collector[1].tool == "read_document"
    assert event_collector[1].page == 0


# ---------------------------------------------------------------------------
# Task 2: Judge / Review agent loop tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_judge_answer_returns_approved_on_good_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_judge_answer returns approved=True when the judge approves."""

    async def _fake_run(agent: Any, **kwargs: Any) -> _FakeRunResult:
        return _FakeRunResult(final_output='{"approved": true}')

    monkeypatch.setattr(
        "synextra.services.rag_agent_orchestrator.Runner.run",
        staticmethod(_fake_run),
    )

    orchestrator = _orchestrator()
    evidence = [_chunk(chunk_id="c1", text="The Transformer uses attention.")]
    citations = orchestrator._build_citations(evidence)

    verdict = await orchestrator._judge_answer(
        prompt="What is the Transformer?",
        answer="The Transformer uses attention mechanisms.",
        evidence=evidence,
        citations=citations,
    )

    assert verdict.approved is True
    assert verdict.feedback == ""


@pytest.mark.asyncio
async def test_judge_answer_returns_rejected_with_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_judge_answer returns approved=False with feedback when judge rejects."""

    async def _fake_run(agent: Any, **kwargs: Any) -> _FakeRunResult:
        return _FakeRunResult(
            final_output=(
                '{"approved": false, "feedback": "The answer fabricates details not in evidence."}'
            )
        )

    monkeypatch.setattr(
        "synextra.services.rag_agent_orchestrator.Runner.run",
        staticmethod(_fake_run),
    )

    orchestrator = _orchestrator()
    evidence = [_chunk(chunk_id="c1", text="The Transformer uses attention.")]
    citations = orchestrator._build_citations(evidence)

    verdict = await orchestrator._judge_answer(
        prompt="What is the Transformer?",
        answer="The Transformer was invented in 2017 at Google Brain.",
        evidence=evidence,
        citations=citations,
    )

    assert verdict.approved is False
    assert "fabricates" in verdict.feedback


@pytest.mark.asyncio
async def test_judge_answer_approves_on_runner_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the judge agent fails, _judge_answer defaults to approved=True."""

    async def _fake_run(agent: Any, **kwargs: Any) -> None:
        raise RuntimeError("Judge LLM unavailable")

    monkeypatch.setattr(
        "synextra.services.rag_agent_orchestrator.Runner.run",
        staticmethod(_fake_run),
    )

    orchestrator = _orchestrator()
    evidence = [_chunk(chunk_id="c1", text="Some evidence.")]
    citations = orchestrator._build_citations(evidence)

    verdict = await orchestrator._judge_answer(
        prompt="What?",
        answer="Some answer.",
        evidence=evidence,
        citations=citations,
    )

    # Failure defaults to approved to avoid blocking
    assert verdict.approved is True


@pytest.mark.asyncio
async def test_run_retrieval_with_review_approves_on_first_iteration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When judge approves on first try, result is returned immediately."""
    orchestrator = _orchestrator()

    async def _fake_call_agent(**_kwargs: Any) -> AgentCallResult:
        return AgentCallResult(
            output_text="Good answer supported by evidence.",
            evidence=[_chunk(chunk_id="c1", text="Evidence text.")],
            tools_used=["bm25_search"],
        )

    async def _fake_judge(**_kwargs: Any) -> JudgeVerdict:
        return JudgeVerdict(approved=True, feedback="")

    monkeypatch.setattr(orchestrator, "_call_agent", _fake_call_agent)
    monkeypatch.setattr(orchestrator, "_judge_answer", _fake_judge)

    result = await orchestrator._run_retrieval_with_review(
        prompt="What is the answer?",
        reasoning_effort="medium",
    )

    assert result.answer == "Good answer supported by evidence."
    assert result.evidence


@pytest.mark.asyncio
async def test_run_retrieval_with_review_retries_on_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When judge rejects, the agent is called again with updated prompt."""
    orchestrator = _orchestrator()

    call_count = 0
    prompts_seen: list[str] = []

    async def _fake_call_agent(**kwargs: Any) -> AgentCallResult:
        nonlocal call_count
        call_count += 1
        prompts_seen.append(kwargs.get("prompt", ""))
        return AgentCallResult(
            output_text=f"Answer attempt {call_count}.",
            evidence=[_chunk(chunk_id="c1", text="Evidence text.")],
            tools_used=["bm25_search"],
        )

    judge_call_count = 0

    async def _fake_judge(**_kwargs: Any) -> JudgeVerdict:
        nonlocal judge_call_count
        judge_call_count += 1
        if judge_call_count == 1:
            return JudgeVerdict(approved=False, feedback="Need more detail on X.")
        return JudgeVerdict(approved=True, feedback="")

    monkeypatch.setattr(orchestrator, "_call_agent", _fake_call_agent)
    monkeypatch.setattr(orchestrator, "_judge_answer", _fake_judge)

    result = await orchestrator._run_retrieval_with_review(
        prompt="Original question.",
        reasoning_effort="medium",
    )

    # Should have called agent twice (once rejected, once approved)
    assert call_count == 2
    assert judge_call_count == 2
    # Second prompt should include rejection feedback
    assert "Previous answer was rejected" in prompts_seen[1]
    assert "Need more detail on X." in prompts_seen[1]
    # Final answer is from the second (approved) attempt
    assert "Answer attempt 2" in result.answer


@pytest.mark.asyncio
async def test_run_retrieval_with_review_falls_back_after_max_iterations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When all judge iterations are exhausted, fallback answer is returned."""
    orchestrator = _orchestrator()

    async def _fake_call_agent(**_kwargs: Any) -> AgentCallResult:
        return AgentCallResult(
            output_text="Answer that keeps getting rejected.",
            evidence=[_chunk(chunk_id="c1", text="Some evidence.")],
            tools_used=["bm25_search"],
        )

    async def _fake_judge(**_kwargs: Any) -> JudgeVerdict:
        return JudgeVerdict(approved=False, feedback="Still not good enough.")

    monkeypatch.setattr(orchestrator, "_call_agent", _fake_call_agent)
    monkeypatch.setattr(orchestrator, "_judge_answer", _fake_judge)

    result = await orchestrator._run_retrieval_with_review(
        prompt="What?",
        reasoning_effort="medium",
    )

    # After max iterations, should return the fallback message
    assert "could not find reliable information" in result.answer


@pytest.mark.asyncio
async def test_run_retrieval_with_review_emits_review_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review events are emitted to event_collector for each judge evaluation."""
    from synextra.schemas.rag_chat import ReviewEvent

    orchestrator = _orchestrator()

    call_count = 0

    async def _fake_call_agent(**_kwargs: Any) -> AgentCallResult:
        nonlocal call_count
        call_count += 1
        return AgentCallResult(
            output_text=f"Answer {call_count}.",
            evidence=[_chunk(chunk_id="c1", text="Evidence text.")],
            tools_used=["bm25_search"],
        )

    judge_call_count = 0

    async def _fake_judge(**_kwargs: Any) -> JudgeVerdict:
        nonlocal judge_call_count
        judge_call_count += 1
        if judge_call_count == 1:
            return JudgeVerdict(approved=False, feedback="Feedback 1.")
        return JudgeVerdict(approved=True, feedback="")

    monkeypatch.setattr(orchestrator, "_call_agent", _fake_call_agent)
    monkeypatch.setattr(orchestrator, "_judge_answer", _fake_judge)

    event_collector: list[Any] = []
    await orchestrator._run_retrieval_with_review(
        prompt="What?",
        reasoning_effort="medium",
        event_collector=event_collector,
    )

    review_events = [e for e in event_collector if isinstance(e, ReviewEvent)]
    assert len(review_events) == 2
    assert review_events[0].verdict == "rejected"
    assert review_events[0].iteration == 1
    assert review_events[0].feedback == "Feedback 1."
    assert review_events[1].verdict == "approved"
    assert review_events[1].iteration == 2
    assert review_events[1].feedback is None


# ---------------------------------------------------------------------------
# Task 3: Streaming Events Protocol tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collect_evidence_returns_events_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """collect_evidence uses judge loop, returns (RetrievalResult, list[StreamEvent])."""
    from synextra.schemas.rag_chat import SearchEvent
    from synextra.services.rag_agent_orchestrator import JudgeVerdict

    orchestrator = _orchestrator()

    async def _fake_call_agent(**kwargs: Any) -> AgentCallResult:
        event_collector = kwargs.get("event_collector")
        if event_collector is not None:
            event_collector.append(
                SearchEvent(
                    event="search",
                    tool="bm25_search",
                    query="test",
                    timestamp="2024-01-01T00:00:00+00:00",
                )
            )
        return AgentCallResult(
            output_text="Answer.",
            evidence=[_chunk(chunk_id="c1", text="Evidence.")],
            tools_used=["bm25_search"],
        )

    async def _fake_judge(**_kwargs: Any) -> JudgeVerdict:
        return JudgeVerdict(approved=True, feedback="")

    monkeypatch.setattr(orchestrator, "_call_agent", _fake_call_agent)
    monkeypatch.setattr(orchestrator, "_judge_answer", _fake_judge)

    request = RagChatRequest(prompt="What?", review_enabled=True)
    result, events = await orchestrator.collect_evidence(session_id="s1", request=request)

    assert isinstance(result, RetrievalResult)
    assert isinstance(events, list)
    # Events: 1 search + 1 review (approved)
    assert len(events) == 2
    assert isinstance(events[0], SearchEvent)
    assert events[0].tool == "bm25_search"
    assert events[1].event == "review"


@pytest.mark.asyncio
async def test_collect_evidence_forwards_events_to_live_sink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """collect_evidence forwards emitted events to the optional async event_sink."""
    from synextra.schemas.rag_chat import SearchEvent

    orchestrator = _orchestrator()

    async def _fake_run_retrieval(**kwargs: Any) -> Any:
        event_collector = kwargs.get("event_collector")
        event_sink = kwargs.get("event_sink")
        event = SearchEvent(
            event="search",
            tool="bm25_search",
            query="sink-test",
            timestamp="2024-01-01T00:00:00+00:00",
        )
        if event_collector is not None:
            event_collector.append(event)
        if event_sink is not None:
            await event_sink(event)
        return type(
            "_Result",
            (),
            {
                "answer": "Answer.",
                "evidence": [_chunk(chunk_id="c1", text="Evidence.")],
                "citations": orchestrator._build_citations(
                    [_chunk(chunk_id="c1", text="Evidence.")]
                ),
                "tools_used": ["bm25_search"],
            },
        )()

    monkeypatch.setattr(orchestrator, "_run_retrieval", _fake_run_retrieval)

    sink_events: list[Any] = []

    async def _event_sink(event: Any) -> None:
        sink_events.append(event)

    request = RagChatRequest(prompt="What?", review_enabled=False)
    _result, events = await orchestrator.collect_evidence(
        session_id="s1",
        request=request,
        event_sink=_event_sink,
    )

    assert len(events) == 1
    assert events[0].event == "search"
    assert len(sink_events) == 1
    assert sink_events[0].event == "search"
    assert sink_events[0].query == "sink-test"


@pytest.mark.asyncio
async def test_collect_evidence_returns_empty_events_on_no_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """collect_evidence returns only review event when no tool events were emitted."""
    from synextra.services.rag_agent_orchestrator import JudgeVerdict

    orchestrator = _orchestrator()

    async def _fake_call_agent(**_kwargs: Any) -> AgentCallResult:
        return AgentCallResult(
            output_text="Answer.",
            evidence=[_chunk(chunk_id="c1", text="Evidence.")],
            tools_used=[],
        )

    async def _fake_judge(**_kwargs: Any) -> JudgeVerdict:
        return JudgeVerdict(approved=True, feedback="")

    monkeypatch.setattr(orchestrator, "_call_agent", _fake_call_agent)
    monkeypatch.setattr(orchestrator, "_judge_answer", _fake_judge)

    request = RagChatRequest(prompt="What?", review_enabled=True)
    _result, events = await orchestrator.collect_evidence(session_id="s1", request=request)

    assert isinstance(events, list)
    # Only the review event (no search events since agent didn't emit any)
    assert len(events) == 1
    assert events[0].event == "review"


def test_search_event_serializes_correctly() -> None:
    """SearchEvent model serializes to the expected JSON format."""
    from synextra.schemas.rag_chat import SearchEvent

    event = SearchEvent(
        event="search",
        tool="bm25_search",
        query="test query",
        timestamp="2024-01-01T00:00:00+00:00",
    )

    data = json.loads(event.model_dump_json())
    assert data["event"] == "search"
    assert data["tool"] == "bm25_search"
    assert data["query"] == "test query"
    assert data["timestamp"] == "2024-01-01T00:00:00+00:00"


def test_review_event_serializes_correctly() -> None:
    """ReviewEvent model serializes to the expected JSON format."""
    from synextra.schemas.rag_chat import ReviewEvent

    event = ReviewEvent(
        event="review",
        iteration=1,
        verdict="rejected",
        feedback="Need more evidence on X.",
        timestamp="2024-01-01T00:00:00+00:00",
    )

    data = json.loads(event.model_dump_json())
    assert data["event"] == "review"
    assert data["iteration"] == 1
    assert data["verdict"] == "rejected"
    assert data["feedback"] == "Need more evidence on X."


def test_reasoning_event_serializes_correctly() -> None:
    """ReasoningEvent model serializes to the expected JSON format."""
    from synextra.schemas.rag_chat import ReasoningEvent

    event = ReasoningEvent(
        event="reasoning",
        content="Analyzing evidence for key claims.",
        timestamp="2024-01-01T00:00:00+00:00",
    )

    data = json.loads(event.model_dump_json())
    assert data["event"] == "reasoning"
    assert data["content"] == "Analyzing evidence for key claims."
