from __future__ import annotations

import os
import re
from dataclasses import dataclass

import anyio

from synextra_backend.repositories.rag_document_repository import RagDocumentRepository
from synextra_backend.retrieval.bm25_search import Bm25IndexStore
from synextra_backend.retrieval.evidence_merger import reciprocal_rank_fusion
from synextra_backend.retrieval.openai_file_search import OpenAIFileSearch
from synextra_backend.retrieval.types import EvidenceChunk
from synextra_backend.schemas.rag_chat import RagChatRequest, RagChatResponse, RagCitation, RetrievalMode
from synextra_backend.services.citation_validator import CitationValidator
from synextra_backend.services.session_memory import SessionMemory


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


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
    return cleaned[: limit].rstrip() + "…"


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
        return "I couldn't find relevant information in the indexed documents to answer that question."

    return " ".join(sentences)


@dataclass(frozen=True)
class OrchestratorResult:
    answer: str
    tools_used: list[str]
    citations: list[RagCitation]
    evidence: list[EvidenceChunk]


class RagAgentOrchestrator:
    """Coordinates retrieval and response synthesis for chat requests."""

    def __init__(
        self,
        *,
        repository: RagDocumentRepository,
        bm25_store: Bm25IndexStore,
        session_memory: SessionMemory,
        citation_validator: CitationValidator | None = None,
    ) -> None:
        self._repository = repository
        self._bm25_store = bm25_store
        self._session_memory = session_memory
        self._citation_validator = citation_validator or CitationValidator()

    async def handle_message(
        self, *, session_id: str, request: RagChatRequest
    ) -> RagChatResponse:
        prompt = request.prompt.strip()
        mode = request.retrieval_mode

        # Record user turn.
        self._session_memory.append_turn(
            session_id=session_id,
            role="user",
            content=prompt,
            mode=mode,
        )

        result = await self._run_retrieval(prompt=prompt, mode=mode)

        # Record assistant turn.
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

    async def _run_retrieval(self, *, prompt: str, mode: RetrievalMode) -> OrchestratorResult:
        tools_used: list[str] = []

        async def run_bm25() -> list[EvidenceChunk]:
            return self._bm25_store.search(query=prompt, top_k=8)

        async def run_vector() -> list[EvidenceChunk]:
            vector_store_ids = self._repository.list_vector_store_ids()
            if not vector_store_ids:
                return []
            file_search = OpenAIFileSearch()
            return file_search.search(vector_store_ids=vector_store_ids, query=prompt, top_k=8)

        bm25_evidence: list[EvidenceChunk] = []
        vector_evidence: list[EvidenceChunk] = []

        if mode == "embedded":
            tools_used.append("bm25_search")
            bm25_evidence = await run_bm25()
            evidence = bm25_evidence
        elif mode == "vector":
            tools_used.append("openai_vector_store_search")
            try:
                vector_evidence = await run_vector()
            except Exception:
                # Graceful degradation when OpenAI is unavailable.
                tools_used.append("bm25_search_fallback")
                bm25_evidence = await run_bm25()
                vector_evidence = []
                evidence = bm25_evidence
            else:
                evidence = vector_evidence
        else:
            # hybrid
            tools_used.extend(["bm25_search", "openai_vector_store_search"])
            try:
                async with anyio.create_task_group() as tg:
                    bm25_holder: dict[str, list[EvidenceChunk]] = {}
                    vector_holder: dict[str, list[EvidenceChunk]] = {}

                    async def run_b() -> None:
                        bm25_holder["value"] = await run_bm25()

                    async def run_v() -> None:
                        vector_holder["value"] = await run_vector()

                    tg.start_soon(run_b)
                    tg.start_soon(run_v)

                bm25_evidence = bm25_holder.get("value", [])
                vector_evidence = vector_holder.get("value", [])
            except Exception:
                bm25_evidence = await run_bm25()
                vector_evidence = []
                tools_used.append("openai_vector_store_search_failed")

            evidence = reciprocal_rank_fusion([bm25_evidence, vector_evidence], top_k=8)

        citations = self._build_citations(evidence)
        validation = self._citation_validator.validate(citations)
        if not validation.ok:
            # Keep citations, but annotate tool usage to aid debugging.
            tools_used.append("citation_validation_failed")

        answer = await self._synthesize_answer(prompt=prompt, evidence=evidence, citations=citations)
        return OrchestratorResult(answer=answer, tools_used=tools_used, citations=citations, evidence=evidence)

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

    async def _synthesize_answer(
        self, *, prompt: str, evidence: list[EvidenceChunk], citations: list[RagCitation]
    ) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return _simple_summary(evidence)

        try:
            from openai import OpenAI  # type: ignore
        except Exception:
            return _simple_summary(evidence)

        client = OpenAI()
        model = os.getenv("SYNEXTRA_CHAT_MODEL", "gpt-5.2")

        context_lines: list[str] = []
        for idx, citation in enumerate(citations, start=1):
            context_lines.append(
                f"[{idx}] doc={citation.document_id} page={citation.page_number} chunk={citation.chunk_id}: {citation.supporting_quote}"
            )

        system = (
            "You are a retrieval-augmented assistant. Answer the user's question using only the provided evidence. "
            "If the evidence is insufficient, say you don't know. Keep the answer concise."
        )

        user = f"Question: {prompt}\n\nEvidence:\n" + "\n".join(context_lines)

        try:
            response = client.responses.create(
                model=model,
                instructions=system,
                input=user,
            )
            # The SDK returns a list of output items; we only need the first text.
            output_text = getattr(response, "output_text", None)
            if isinstance(output_text, str) and output_text.strip():
                return output_text.strip()
        except Exception:
            return _simple_summary(evidence)

        return _simple_summary(evidence)
