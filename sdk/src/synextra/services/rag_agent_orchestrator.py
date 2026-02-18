from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from agents import Agent, Runner, function_tool
from agents.model_settings import ModelSettings
from openai.types.shared import Reasoning
from pydantic import BaseModel, ConfigDict

from synextra.repositories.rag_document_repository import RagDocumentRepository
from synextra.retrieval.bm25_search import Bm25IndexStore
from synextra.retrieval.types import EvidenceChunk
from synextra.schemas.rag_chat import (
    RagChatRequest,
    RagChatResponse,
    RagCitation,
    ReasoningEffort,
    ReviewEvent,
    SearchEvent,
    StreamEvent,
)
from synextra.services.citation_validator import CitationValidator
from synextra.services.document_store import DocumentStore
from synextra.services.session_memory import SessionMemory

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_STREAM_CHUNK_RE = re.compile(r"\S+\s*")

_DEFAULT_CHAT_MODEL = "gpt-5.2"

_MAX_JUDGE_ITERATIONS = 3

_FALLBACK_ANSWER = "I could not find reliable information to answer your question."


class Bm25ParallelQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["bm25_search"]
    query: str
    top_k: int = 8


class ReadDocumentParallelQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["read_document"]
    page: int
    start_line: int | None = None
    end_line: int | None = None
    document_id: str | None = None


ParallelQuery = Bm25ParallelQuery | ReadDocumentParallelQuery


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _normalize_inline_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()


def _quote_fingerprint(text: str, *, prefix_len: int = 160) -> str:
    normalized = _normalize_inline_whitespace(text).lower()
    if len(normalized) <= prefix_len:
        return normalized
    return normalized[:prefix_len]


def _truncate_quote(text: str, limit: int = 240) -> str:
    cleaned = _normalize_inline_whitespace(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "\u2026"


def _simple_summary(evidence: list[EvidenceChunk], *, max_sentences: int = 4) -> str:
    sentences: list[str] = []
    for chunk in evidence:
        for sentence in _SENTENCE_RE.split(chunk.text):
            sentence = _normalize_inline_whitespace(sentence)
            if not sentence:
                continue
            sentences.append(sentence)
            if len(sentences) >= max_sentences:
                break
        if len(sentences) >= max_sentences:
            break

    if not sentences:
        return (
            "I couldn't find relevant information in the indexed documents to answer that question."
        )

    return " ".join(sentences)


def _stream_chunks(text: str) -> list[str]:
    chunks = _STREAM_CHUNK_RE.findall(text)
    if chunks:
        return chunks
    return [text] if text else []


def _chat_model() -> str:
    return os.getenv("SYNEXTRA_CHAT_MODEL", _DEFAULT_CHAT_MODEL)


@dataclass(frozen=True)
class OrchestratorResult:
    answer: str
    tools_used: list[str]
    citations: list[RagCitation]
    evidence: list[EvidenceChunk]


@dataclass(frozen=True)
class AgentCallResult:
    output_text: str
    evidence: list[EvidenceChunk]
    tools_used: list[str]


@dataclass(frozen=True)
class RetrievalResult:
    answer: str
    evidence: list[EvidenceChunk]
    citations: list[RagCitation]
    tools_used: list[str]


@dataclass(frozen=True)
class JudgeVerdict:
    approved: bool
    feedback: str


class RagAgentOrchestrator:
    """Coordinates retrieval and response synthesis for chat requests."""

    def __init__(
        self,
        *,
        repository: RagDocumentRepository,
        bm25_store: Bm25IndexStore,
        session_memory: SessionMemory,
        document_store: DocumentStore,
        citation_validator: CitationValidator | None = None,
    ) -> None:
        self._repository = repository
        self._bm25_store = bm25_store
        self._session_memory = session_memory
        self._document_store = document_store
        self._citation_validator = citation_validator or CitationValidator()

    async def handle_message(self, *, session_id: str, request: RagChatRequest) -> RagChatResponse:
        prompt = request.prompt.strip()
        mode = request.retrieval_mode
        reasoning_effort = request.reasoning_effort

        self._session_memory.append_turn(
            session_id=session_id,
            role="user",
            content=prompt,
            mode=mode,
        )

        result = await self._run_retrieval(
            prompt=prompt,
            reasoning_effort=reasoning_effort,
            review_enabled=request.review_enabled,
        )

        self._session_memory.append_turn(
            session_id=session_id,
            role="assistant",
            content=result.answer,
            mode=mode,
            citations=result.citations,
            tools_used=result.tools_used,
        )

        return RagChatResponse(
            session_id=session_id,
            mode=mode,
            answer=result.answer,
            tools_used=result.tools_used,
            citations=result.citations,
            agent_events=[],
        )

    def run_bm25(self, *, prompt: str, top_k: int = 8) -> list[EvidenceChunk]:
        """Direct BM25 search (used as fallback when the agent loop fails)."""
        return self._bm25_store.search(query=prompt, top_k=top_k)

    def run_read_document(
        self,
        *,
        document_id: str,
        page: int,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> list[EvidenceChunk]:
        text = self._document_store.read_page(
            document_id,
            page,
            start_line=start_line,
            end_line=end_line,
        )
        if text is None:
            available = [d.document_id for d in self._document_store.list_documents()]
            raise ValueError(
                f"Document {document_id!r} page {page} not found. Available documents: {available}"
            )

        chunk_id = f"{document_id}:page:{page}"
        if start_line is not None or end_line is not None:
            chunk_id += f":lines:{start_line or 1}-{end_line or 'end'}"

        return [
            EvidenceChunk(
                document_id=document_id,
                chunk_id=chunk_id,
                page_number=page,
                text=text,
                score=1.0,
                source_tool="read_document",
            )
        ]

    @staticmethod
    def _append_unique(target: list[str], value: str) -> None:
        if value and value not in target:
            target.append(value)

    def _agent_instructions(self) -> str:
        docs = self._document_store.list_documents()
        if docs:
            doc_lines: list[str] = []
            for doc in docs:
                last_page = doc.page_count - 1
                doc_lines.append(
                    f'  - id={doc.document_id} "{doc.filename}" '
                    f"(pages 0\u2013{last_page}, {doc.page_count} total)"
                )
            doc_section = "Available documents:\n" + "\n".join(doc_lines)
        else:
            doc_section = "No documents have been ingested yet."

        return f"""You are a document Q&A assistant.
Answer questions using only the provided documents.

## Values:
- thorough: an initial search across the document store does not yield sufficient evidence,
run additional tool calls to gather more evidence.
- unbiased: generate diverse queries (inline with question scope) to cover different aspects
of the question's domain.
- factual: you never fabricate or infer information.
  * if the information is present in the document, you use it and cite it.
  * if the information is not present in the document, you state you can't reliably answer.

## Context (pre-retrieval - may be blank):
```md
{doc_section}
```

## Tools:
Use the tools below to extract additional evidence from the documents.
- call the tools in parallel to minimize latency.
- you MUST use both `bm25_search` AND `read_document` before producing your final answer.
- run at least 2 rounds of tool calls before answering the user.

### `bm25_search(query, top_k)`
- keyword search across document chunks.
  * Returns matching excerpts with page numbers and relevance scores.

### `read_document(document_id?, page, start_line?, end_line?)`
- read a specific page or line range.
  * Provide document_id when multiple documents are available.
  * Pages are 0-indexed.
  * Lines are 1-based.
  * Omit start_line/end_line to read the full page.

### `parallel_search(queries)`
- run multiple bm25_search and/or read_document calls concurrently.
  * Each item must specify "type": "bm25_search" or "type": "read_document".
  * For bm25_search: include "query" and optionally "top_k".
  * For read_document: include "page" and optionally "start_line"/"end_line"/"document_id".
  * Returns a list of results corresponding to each query.

## Strategy (MANDATORY):
1. ALWAYS start with `bm25_search` using at least 2 diverse queries to locate relevant pages.
2. ALWAYS follow up with `read_document` on the most promising pages returned by bm25_search.
3. Use `read_document` with `start_line`/`end_line` to zoom into specific sections when needed.
4. You MUST call both `bm25_search` AND `read_document` at least once before answering.
   Skipping either tool is NOT allowed.
5. Answer only using evidence from the document. Cite page numbers and line numbers.
6. Produce the final user answer directly after your retrieval steps.
   There is no separate synthesis pass to fix or expand unsupported claims.

**CRITICAL: Answer only to the scope of the question asked.**"""

    def _create_agent_tools(
        self,
        evidence_collector: list[EvidenceChunk],
        event_collector: list[StreamEvent] | None = None,
    ) -> list[Any]:
        """Build async @function_tool closures that capture dependencies and collect evidence.

        Tools are async so the SDK runs them on the event loop (not a thread
        pool), which keeps ``evidence_collector`` mutations single-threaded.
        """
        bm25_store = self._bm25_store
        document_store = self._document_store

        @function_tool(name_override="bm25_search")
        async def bm25_search(query: str, top_k: int = 8) -> str:
            """Keyword search across document chunks.

            Returns matching excerpts with page numbers and relevance scores.
            """
            if event_collector is not None:
                event_collector.append(
                    SearchEvent(
                        event="search", tool="bm25_search", query=query, timestamp=_now_iso()
                    )
                )
            results = bm25_store.search(query=query, top_k=max(1, top_k))
            evidence_collector.extend(results)
            return json.dumps([asdict(r) for r in results])

        @function_tool(name_override="read_document")
        async def read_document(
            page: int,
            start_line: int | None = None,
            end_line: int | None = None,
            document_id: str | None = None,
        ) -> str:
            """Read text from a document page.

            Pages are 0-indexed. Lines are 1-based.
            Omit start_line/end_line to read the full page.
            """
            if event_collector is not None:
                event_collector.append(
                    SearchEvent(
                        event="search", tool="read_document", page=page, timestamp=_now_iso()
                    )
                )
            docs = document_store.list_documents()
            if not docs:
                return json.dumps({"error": "No documents have been ingested yet"})

            resolved_document_id = document_id
            if not resolved_document_id:
                resolved_document_id = docs[0].document_id

            if not document_store.has_document(resolved_document_id):
                available_ids = [d.document_id for d in docs]
                return json.dumps(
                    {
                        "error": (
                            f"Document {resolved_document_id!r} not found. "
                            f"Available documents: {available_ids}"
                        )
                    }
                )

            text = document_store.read_page(
                resolved_document_id,
                page,
                start_line=start_line,
                end_line=end_line,
            )
            if text is None:
                available = document_store.get_page_count(resolved_document_id)
                return json.dumps(
                    {"error": f"Page {page} not found. Available pages: 0-{available - 1}"}
                )

            chunk_id = f"{resolved_document_id}:page:{page}"
            if start_line is not None or end_line is not None:
                chunk_id += f":lines:{start_line or 1}-{end_line or 'end'}"

            chunk = EvidenceChunk(
                document_id=resolved_document_id,
                chunk_id=chunk_id,
                page_number=page,
                text=text,
                score=1.0,
                source_tool="read_document",
            )
            evidence_collector.append(chunk)
            return json.dumps(asdict(chunk))

        @function_tool(name_override="parallel_search")
        async def parallel_search(queries: list[ParallelQuery] | str) -> str:
            """Run multiple bm25_search and/or read_document calls concurrently.

            ``queries`` may be either:
              - a JSON array string, or
              - a parsed list of typed query objects.

            Each element must have a "type" field
            ("bm25_search" or "read_document") plus the relevant parameters:
              - bm25_search: {"type": "bm25_search", "query": "...", "top_k": 8}
              - read_document: {"type": "read_document", "page": 0,
                                "start_line": null, "end_line": null,
                                "document_id": null}

            Returns a JSON array of results in the same order as the input.
            """
            query_list: list[dict[str, Any]]
            if isinstance(queries, str):
                try:
                    parsed = json.loads(queries)
                except json.JSONDecodeError as exc:
                    return json.dumps({"error": f"Invalid JSON in queries: {exc}"})
                if not isinstance(parsed, list):
                    return json.dumps({"error": "queries must decode to a JSON array"})
                query_list = []
                for item in parsed:
                    if not isinstance(item, dict):
                        return json.dumps({"error": "queries items must be JSON objects"})
                    query_list.append(item)
            elif isinstance(queries, list):
                query_list = []
                for item in queries:
                    if isinstance(item, BaseModel):
                        query_list.append(item.model_dump())
                        continue
                    if isinstance(item, dict):
                        query_list.append(item)
                        continue
                    return json.dumps({"error": "queries items must be dictionaries"})
            else:
                return json.dumps({"error": "queries must be either a JSON array string or list"})

            async def _run_single(item: dict[str, Any]) -> Any:
                item_type = item.get("type")
                if item_type == "bm25_search":
                    query_str = str(item.get("query", ""))
                    top_k_val = int(item.get("top_k", 8))
                    if event_collector is not None:
                        event_collector.append(
                            SearchEvent(
                                event="search",
                                tool="bm25_search",
                                query=query_str,
                                timestamp=_now_iso(),
                            )
                        )
                    results = bm25_store.search(query=query_str, top_k=max(1, top_k_val))
                    evidence_collector.extend(results)
                    return [asdict(r) for r in results]
                if item_type == "read_document":
                    page_val = int(item.get("page", 0))
                    start_line_val: int | None = item.get("start_line")
                    end_line_val: int | None = item.get("end_line")
                    document_id_val: str | None = item.get("document_id")
                    if event_collector is not None:
                        event_collector.append(
                            SearchEvent(
                                event="search",
                                tool="read_document",
                                page=page_val,
                                timestamp=_now_iso(),
                            )
                        )
                    docs = document_store.list_documents()
                    if not docs:
                        return {"error": "No documents have been ingested yet"}

                    resolved_document_id = document_id_val
                    if not resolved_document_id:
                        resolved_document_id = docs[0].document_id

                    if not document_store.has_document(resolved_document_id):
                        available_ids = [d.document_id for d in docs]
                        return {
                            "error": (
                                f"Document {resolved_document_id!r} not found. "
                                f"Available documents: {available_ids}"
                            )
                        }
                    text = document_store.read_page(
                        resolved_document_id,
                        page_val,
                        start_line=start_line_val,
                        end_line=end_line_val,
                    )
                    if text is None:
                        available = document_store.get_page_count(resolved_document_id)
                        return {
                            "error": (
                                f"Page {page_val} not found. Available pages: 0-{available - 1}"
                            )
                        }

                    chunk_id = f"{resolved_document_id}:page:{page_val}"
                    if start_line_val is not None or end_line_val is not None:
                        chunk_id += f":lines:{start_line_val or 1}-{end_line_val or 'end'}"
                    chunk = EvidenceChunk(
                        document_id=resolved_document_id,
                        chunk_id=chunk_id,
                        page_number=page_val,
                        text=text,
                        score=1.0,
                        source_tool="read_document",
                    )
                    evidence_collector.append(chunk)
                    return asdict(chunk)
                return {
                    "error": (
                        f"Unknown query type: {item_type!r}. Use 'bm25_search' or 'read_document'."
                    )
                }

            results_list = await asyncio.gather(*[_run_single(item) for item in query_list])
            return json.dumps(results_list)

        return [bm25_search, read_document, parallel_search]

    async def _run_retrieval(
        self,
        *,
        prompt: str,
        reasoning_effort: ReasoningEffort,
        review_enabled: bool = False,
        event_collector: list[StreamEvent] | None = None,
    ) -> OrchestratorResult:
        """Run retrieval once or with judge review, based on review_enabled."""
        if review_enabled:
            return await self._run_retrieval_with_review(
                prompt=prompt,
                reasoning_effort=reasoning_effort,
                event_collector=event_collector,
            )
        return await self._run_retrieval_once(
            prompt=prompt,
            reasoning_effort=reasoning_effort,
            event_collector=event_collector,
        )

    async def _run_retrieval_once(
        self,
        *,
        prompt: str,
        reasoning_effort: ReasoningEffort,
        event_collector: list[StreamEvent] | None = None,
    ) -> OrchestratorResult:
        """Run retrieval in a single pass without judge review."""
        tools_used: list[str] = []
        agent_result: AgentCallResult | None = None

        try:
            agent_result = await self._call_agent(
                prompt=prompt,
                reasoning_effort=reasoning_effort,
                event_collector=event_collector,
            )
            for tool in agent_result.tools_used:
                self._append_unique(tools_used, tool)
        except Exception:
            self._append_unique(tools_used, "agent_retrieval_failed")

        if agent_result is not None and agent_result.evidence:
            citations = self._build_citations(agent_result.evidence)
            validation = self._citation_validator.validate(citations)
            if not validation.ok:
                self._append_unique(tools_used, "citation_validation_failed")

            answer = agent_result.output_text.strip() or _simple_summary(agent_result.evidence)
            return OrchestratorResult(
                answer=answer,
                tools_used=tools_used,
                citations=citations,
                evidence=agent_result.evidence,
            )

        fallback_evidence = self.run_bm25(prompt=prompt, top_k=8)
        if fallback_evidence:
            self._append_unique(tools_used, "bm25_search_fallback")
            fallback_citations = self._build_citations(fallback_evidence)
            return OrchestratorResult(
                answer=_FALLBACK_ANSWER,
                tools_used=tools_used,
                citations=fallback_citations,
                evidence=fallback_evidence,
            )

        return OrchestratorResult(
            answer=_FALLBACK_ANSWER,
            tools_used=tools_used,
            citations=[],
            evidence=[],
        )

    def _build_citations(self, evidence: list[EvidenceChunk]) -> list[RagCitation]:
        citations: list[RagCitation] = []
        seen_chunks: set[tuple[str, str]] = set()
        seen_quotes: set[tuple[str, str]] = set()
        for chunk in evidence:
            key = (chunk.document_id, chunk.chunk_id)
            if key in seen_chunks:
                continue
            seen_chunks.add(key)

            supporting_quote = _truncate_quote(chunk.text)
            if not supporting_quote:
                continue

            quote_key = (chunk.document_id, _quote_fingerprint(supporting_quote))
            if quote_key in seen_quotes:
                continue
            seen_quotes.add(quote_key)

            citations.append(
                RagCitation(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    page_number=chunk.page_number,
                    supporting_quote=supporting_quote,
                    source_tool=chunk.source_tool,
                    score=chunk.score,
                )
            )
        return citations

    async def _call_agent(
        self,
        *,
        prompt: str,
        reasoning_effort: ReasoningEffort,
        event_collector: list[StreamEvent] | None = None,
    ) -> AgentCallResult:
        """Run the retrieval agent via the OpenAI Agents SDK.

        Creates an Agent with bm25_search, read_document and parallel_search
        tools, executes it via Runner.run_streamed, and collects evidence +
        tool usage from the streamed events.
        """
        collected_evidence: list[EvidenceChunk] = []
        tools = self._create_agent_tools(collected_evidence, event_collector)

        agent: Agent = Agent(
            name="synextra_ai",
            tools=tools,
            instructions=self._agent_instructions(),
            model=_chat_model(),
            model_settings=ModelSettings(
                reasoning=Reasoning(effort=reasoning_effort, summary="concise"),
            ),
        )

        streamed = Runner.run_streamed(
            agent,
            input=f"Question: {prompt}",
            max_turns=10,
            auto_previous_response_id=True,
        )

        used_tools: list[str] = []
        async for event in streamed.stream_events():
            if event.type == "run_item_stream_event" and event.item.type == "tool_call_item":
                tool_name = getattr(event.item.raw_item, "name", "unknown")
                self._append_unique(used_tools, tool_name)

        output_text = str(streamed.final_output) if streamed.final_output else ""

        return AgentCallResult(
            output_text=output_text.strip(),
            evidence=collected_evidence,
            tools_used=used_tools,
        )

    async def _judge_answer(
        self,
        *,
        prompt: str,
        answer: str,
        evidence: list[EvidenceChunk],
        citations: list[RagCitation],
    ) -> JudgeVerdict:
        """Run a judge agent to validate the answer against its cited evidence.

        Returns a JudgeVerdict indicating whether the answer is approved or
        rejected, along with feedback for the next iteration.
        """
        evidence_lines: list[str] = []
        for idx, chunk in enumerate(evidence[:24], start=1):
            evidence_lines.append(
                f"[{idx}] doc={chunk.document_id} page={chunk.page_number} "
                f"chunk={chunk.chunk_id} tool={chunk.source_tool}: "
                f"{_truncate_quote(chunk.text, limit=900)}"
            )
        evidence_text = "\n".join(evidence_lines) if evidence_lines else "(no evidence)"

        citation_lines: list[str] = []
        for idx, citation in enumerate(citations, start=1):
            citation_lines.append(
                f"[{idx}] doc={citation.document_id} page={citation.page_number} "
                f"chunk={citation.chunk_id}"
            )
        citation_text = "\n".join(citation_lines) if citation_lines else "(no citations)"

        judge_instructions = (
            "You are a strict fact-checking judge. "
            "Your task is to evaluate whether a given answer is fully "
            "supported by the provided evidence. "
            "Check: (1) every factual claim in the answer is grounded in the evidence, "
            "(2) citations referenced actually exist in the evidence, "
            "(3) no information is fabricated or inferred beyond what the evidence states. "
            "Respond with a JSON object ONLY (no prose) in this exact format:\n"
            '{"approved": true} if the answer is acceptable, or\n'
            '{"approved": false, "feedback": "specific reason why it was rejected"} if not.'
        )

        judge_input = (
            "Question: "
            f"{prompt}\n\nEvidence chunks:\n{evidence_text}\n\nCitations listed by the assistant:\n"
            f"{citation_text}\n\nAnswer to evaluate:\n{answer}"
        )

        judge_agent = Agent(
            name="synextra_judge",
            instructions=judge_instructions,
            model=_chat_model(),
        )

        try:
            result = await Runner.run(judge_agent, input=judge_input)
            output = str(result.final_output).strip() if result.final_output else ""

            # Extract JSON from response (may be wrapped in code fences)
            json_match = re.search(r"\{.*\}", output, re.DOTALL)
            if json_match:
                verdict_data: dict[str, Any] = json.loads(json_match.group())
                approved = bool(verdict_data.get("approved", False))
                feedback = str(verdict_data.get("feedback", "")) if not approved else ""
                return JudgeVerdict(approved=approved, feedback=feedback)
        except Exception:
            pass

        # If the judge fails, approve to avoid blocking the response
        return JudgeVerdict(approved=True, feedback="")

    async def _run_retrieval_with_review(
        self,
        *,
        prompt: str,
        reasoning_effort: ReasoningEffort,
        event_collector: list[StreamEvent] | None = None,
    ) -> OrchestratorResult:
        """Run retrieval + judge loop with up to _MAX_JUDGE_ITERATIONS attempts."""
        tools_used: list[str] = []
        current_prompt = prompt

        for iteration in range(1, _MAX_JUDGE_ITERATIONS + 1):
            agent_result: AgentCallResult | None = None
            try:
                agent_result = await self._call_agent(
                    prompt=current_prompt,
                    reasoning_effort=reasoning_effort,
                    event_collector=event_collector,
                )
                for tool in agent_result.tools_used:
                    self._append_unique(tools_used, tool)
            except Exception:
                self._append_unique(tools_used, "agent_retrieval_failed")

            if agent_result is None or not agent_result.evidence:
                # No evidence — skip judging, fall through to fallback
                break

            evidence = agent_result.evidence
            citations = self._build_citations(evidence)

            verdict = await self._judge_answer(
                prompt=prompt,
                answer=agent_result.output_text,
                evidence=evidence,
                citations=citations,
            )

            if event_collector is not None:
                event_collector.append(
                    ReviewEvent(
                        event="review",
                        iteration=iteration,
                        verdict="approved" if verdict.approved else "rejected",
                        feedback=verdict.feedback if not verdict.approved else None,
                        timestamp=_now_iso(),
                    )
                )

            if verdict.approved:
                validation = self._citation_validator.validate(citations)
                if not validation.ok:
                    self._append_unique(tools_used, "citation_validation_failed")

                answer = agent_result.output_text.strip() or _simple_summary(evidence)
                return OrchestratorResult(
                    answer=answer,
                    tools_used=tools_used,
                    citations=citations,
                    evidence=evidence,
                )

            # Rejected — give feedback to agent for next round
            current_prompt = f"{prompt}\n\nPrevious answer was rejected: {verdict.feedback}"

        # All iterations exhausted or no evidence found — try BM25 fallback then give up
        # If we have evidence from the last failed iteration, use the fallback answer
        fallback_evidence = self.run_bm25(prompt=prompt, top_k=8)
        if fallback_evidence:
            self._append_unique(tools_used, "bm25_search_fallback")
            fallback_citations = self._build_citations(fallback_evidence)
            return OrchestratorResult(
                answer=_FALLBACK_ANSWER,
                tools_used=tools_used,
                citations=fallback_citations,
                evidence=fallback_evidence,
            )

        return OrchestratorResult(
            answer=_FALLBACK_ANSWER,
            tools_used=tools_used,
            citations=[],
            evidence=[],
        )

    async def _synthesize_answer(
        self,
        *,
        prompt: str,
        evidence: list[EvidenceChunk],
        citations: list[RagCitation],
        reasoning_effort: ReasoningEffort,
    ) -> str:
        """Programmatic synthesis helper kept for backward compatibility."""
        _ = prompt
        _ = citations
        _ = reasoning_effort
        if not evidence:
            return (
                "I couldn't find relevant information in the indexed "
                "documents to answer that question."
            )
        return _simple_summary(evidence)

    async def collect_evidence(
        self,
        *,
        session_id: str,
        request: RagChatRequest,
    ) -> tuple[RetrievalResult, list[StreamEvent]]:
        """Run retrieval (with optional judge review). Returns evidence + events.

        Returns a (RetrievalResult, list[StreamEvent]) tuple where the events
        contain search/reasoning/review events emitted during evidence collection.
        """
        prompt = request.prompt.strip()
        mode = request.retrieval_mode
        reasoning_effort = request.reasoning_effort
        event_collector: list[StreamEvent] = []

        self._session_memory.append_turn(
            session_id=session_id,
            role="user",
            content=prompt,
            mode=mode,
        )

        result = await self._run_retrieval(
            prompt=prompt,
            reasoning_effort=reasoning_effort,
            review_enabled=request.review_enabled,
            event_collector=event_collector,
        )

        retrieval = RetrievalResult(
            answer=result.answer,
            evidence=result.evidence,
            citations=result.citations,
            tools_used=result.tools_used,
        )
        return retrieval, event_collector

    async def stream_synthesis(
        self,
        *,
        prompt: str,
        retrieval: RetrievalResult,
        reasoning_effort: ReasoningEffort,
    ) -> AsyncIterator[str]:
        """Stream answer chunks from retrieval output without an extra model call."""
        _ = prompt
        _ = reasoning_effort

        answer = retrieval.answer.strip()
        if not answer:
            if not retrieval.evidence:
                answer = (
                    "I couldn't find relevant information in the indexed "
                    "documents to answer that question."
                )
            else:
                answer = _simple_summary(retrieval.evidence)

        for chunk in _stream_chunks(answer):
            yield chunk
