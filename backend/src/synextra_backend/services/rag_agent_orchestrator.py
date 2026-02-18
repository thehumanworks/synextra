from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from typing import Any

from openai import AsyncOpenAI, OpenAI, pydantic_function_tool
from pydantic import BaseModel

from synextra_backend.repositories.rag_document_repository import RagDocumentRepository
from synextra_backend.retrieval.bm25_search import Bm25IndexStore
from synextra_backend.retrieval.types import EvidenceChunk
from synextra_backend.schemas.rag_chat import (
    RagChatRequest,
    RagChatResponse,
    RagCitation,
    ReasoningEffort,
)
from synextra_backend.services.citation_validator import CitationValidator
from synextra_backend.services.document_store import DocumentStore
from synextra_backend.services.session_memory import SessionMemory

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class Bm25RetrievalTool(BaseModel):
    query: str
    top_k: int = 8


class ReadDocumentTool(BaseModel):
    """Read text from a document page. Omit start_line and end_line to read the full page."""

    page: int
    start_line: int | None = None
    end_line: int | None = None


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
    return cleaned[:limit].rstrip() + "…"


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
    evidence: list[EvidenceChunk]
    citations: list[RagCitation]
    tools_used: list[str]


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
        self._openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._async_openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

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
            raise ValueError(
                f"Document {document_id!r} page {page} not found. "
                f"Available documents: {[d.document_id for d in self._document_store.list_documents()]}"
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

    def _dispatch_tool_call(self, *, tool_name: str, args: str) -> Any:
        parsed = json.loads(args) if args else {}

        if tool_name == "bm25_search":
            query = str(parsed.get("query", "")).strip()
            if not query:
                raise ValueError("Tool call is missing query")
            top_k_raw = parsed.get("top_k", 8)
            top_k = int(top_k_raw) if isinstance(top_k_raw, int | str) else 8
            top_k = max(1, top_k)
            return self.run_bm25(prompt=query, top_k=top_k)

        if tool_name == "read_document":
            page = parsed.get("page")
            if page is None:
                raise ValueError("read_document requires a page number")
            page = int(page)
            start_line = parsed.get("start_line")
            end_line = parsed.get("end_line")
            if start_line is not None:
                start_line = int(start_line)
            if end_line is not None:
                end_line = int(end_line)

            # Resolve the document_id: use the first (and usually only) document.
            docs = self._document_store.list_documents()
            if not docs:
                raise ValueError("No documents have been ingested yet")
            document_id = docs[0].document_id

            return self.run_read_document(
                document_id=document_id,
                page=page,
                start_line=start_line,
                end_line=end_line,
            )

        raise ValueError(f"Unknown tool name: {tool_name}")

    @staticmethod
    def _serialize_tool_output(result: Any) -> str:
        if isinstance(result, list) and all(isinstance(item, EvidenceChunk) for item in result):
            payload = [asdict(item) for item in result]
        else:
            payload = result

        try:
            return json.dumps(payload)
        except TypeError:
            return json.dumps({"value": str(payload)})

    @staticmethod
    def _append_unique(target: list[str], value: str) -> None:
        if value and value not in target:
            target.append(value)

    def _tools(self) -> list[Any]:
        return [
            pydantic_function_tool(Bm25RetrievalTool, name="bm25_search"),
            pydantic_function_tool(ReadDocumentTool, name="read_document"),
        ]

    def _agent_instructions(self) -> str:
        docs = self._document_store.list_documents()
        if docs:
            doc_lines: list[str] = []
            for doc in docs:
                last_page = doc.page_count - 1
                doc_lines.append(
                    f"  - \"{doc.filename}\" (pages 0–{last_page}, {doc.page_count} total)"
                )
            doc_section = "Available documents:\n" + "\n".join(doc_lines)
        else:
            doc_section = "No documents have been ingested yet."

        return (
            "You are a document Q&A assistant. "
            "Answer questions using only the provided documents.\n\n"
            f"{doc_section}\n\n"
            "Tools:\n"
            "- bm25_search(query, top_k): keyword search across document chunks. "
            "Returns matching excerpts with page numbers and relevance scores.\n"
            "- read_document(page, start_line?, end_line?): read a specific page or "
            "line range. Pages are 0-indexed. Lines are 1-based. Omit start_line/end_line "
            "to read the full page.\n\n"
            "Strategy:\n"
            "1. Use bm25_search to locate relevant pages.\n"
            "2. Use read_document to read promising pages in full.\n"
            "3. Use read_document with start_line/end_line to focus on specific sections.\n"
            "4. Answer only using evidence from the document. "
            "Cite page numbers and line numbers. Be concise."
        )

    async def _run_retrieval(
        self,
        *,
        prompt: str,
        reasoning_effort: ReasoningEffort,
    ) -> OrchestratorResult:
        tools_used: list[str] = []

        agent_result: AgentCallResult | None = None
        try:
            model = os.getenv("SYNEXTRA_CHAT_MODEL", "gpt-5.2")
            agent_result = self._call_agent(
                client=self._openai_client,
                model=model,
                instructions=self._agent_instructions(),
                input=f"Question: {prompt}",
                reasoning_effort=reasoning_effort,
                tools=self._tools(),
            )
            tools_used.extend(agent_result.tools_used)
        except Exception:
            self._append_unique(tools_used, "agent_retrieval_failed")

        if agent_result is not None and agent_result.evidence:
            evidence = agent_result.evidence
            citations = self._build_citations(evidence)
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

        # Fallback: direct BM25 search.
        evidence = self.run_bm25(prompt=prompt, top_k=8)
        self._append_unique(tools_used, "bm25_search_fallback")

        citations = self._build_citations(evidence)
        validation = self._citation_validator.validate(citations)
        if not validation.ok:
            self._append_unique(tools_used, "citation_validation_failed")

        answer = await self._synthesize_answer(
            prompt=prompt,
            evidence=evidence,
            citations=citations,
            reasoning_effort=reasoning_effort,
        )
        return OrchestratorResult(
            answer=answer,
            tools_used=tools_used,
            citations=citations,
            evidence=evidence,
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

    def _call_agent(
        self,
        client: Any,
        model: str,
        instructions: str,
        input: str,
        reasoning_effort: str,
        tools: list[Any],
    ) -> AgentCallResult:
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=input,
            tools=tools,
            tool_choice="required",
            reasoning={"effort": reasoning_effort},
        )
        collected_evidence: list[EvidenceChunk] = []
        used_tools: list[str] = []

        tool_calls = [item for item in response.output if item.type == "function_call"]
        while tool_calls:
            tool_outputs = []
            for item in tool_calls:
                name = str(item.name)
                self._append_unique(used_tools, name)

                try:
                    result = self._dispatch_tool_call(tool_name=name, args=item.arguments)
                except Exception as exc:
                    self._append_unique(used_tools, f"{name}_failed")
                    output = json.dumps({"error": str(exc) or "Tool execution failed"})
                    tool_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": item.call_id,
                            "output": output,
                        }
                    )
                    continue

                if isinstance(result, list):
                    for chunk in result:
                        if isinstance(chunk, EvidenceChunk):
                            collected_evidence.append(chunk)

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": self._serialize_tool_output(result),
                    }
                )
            response = client.responses.create(
                model=model,
                previous_response_id=response.id,
                input=tool_outputs,
                tools=tools,
                tool_choice="auto",
                reasoning={"effort": reasoning_effort},
            )
            tool_calls = [item for item in response.output if item.type == "function_call"]

        output_text = getattr(response, "output_text", None)
        text = output_text.strip() if isinstance(output_text, str) else ""
        return AgentCallResult(
            output_text=text,
            evidence=collected_evidence,
            tools_used=used_tools,
        )

    async def _synthesize_answer(
        self,
        *,
        prompt: str,
        evidence: list[EvidenceChunk],
        citations: list[RagCitation],
        reasoning_effort: ReasoningEffort,
    ) -> str:
        client = self._openai_client
        model = os.getenv("SYNEXTRA_CHAT_MODEL", "gpt-5.2")

        context_lines: list[str] = []
        for idx, citation in enumerate(citations, start=1):
            context_lines.append(
                f"[{idx}] doc={citation.document_id} page={citation.page_number} "
                f"chunk={citation.chunk_id}: {citation.supporting_quote}"
            )

        system = (
            "You are a document Q&A assistant. "
            "Answer the user's question using only the provided evidence. "
            "If the evidence is insufficient, say you don't know. Keep the answer concise."
        )

        user = f"Question: {prompt}\n\nEvidence:\n" + "\n".join(context_lines)

        try:
            response = client.responses.create(
                model=model,
                instructions=system,
                input=user,
                reasoning={"effort": reasoning_effort},
            )
            output_text = getattr(response, "output_text", None)
            if isinstance(output_text, str) and output_text.strip():
                return output_text.strip()
        except Exception:
            return _simple_summary(evidence)

        return _simple_summary(evidence)

    async def collect_evidence(
        self,
        *,
        session_id: str,
        request: RagChatRequest,
    ) -> RetrievalResult:
        """Run retrieval only (no answer synthesis). Returns evidence + citations."""
        prompt = request.prompt.strip()
        mode = request.retrieval_mode
        reasoning_effort = request.reasoning_effort
        tools_used: list[str] = []

        self._session_memory.append_turn(
            session_id=session_id,
            role="user",
            content=prompt,
            mode=mode,
        )

        agent_result: AgentCallResult | None = None
        try:
            model = os.getenv("SYNEXTRA_CHAT_MODEL", "gpt-5.2")
            agent_result = self._call_agent(
                client=self._openai_client,
                model=model,
                instructions=self._agent_instructions(),
                input=f"Question: {prompt}",
                reasoning_effort=reasoning_effort,
                tools=self._tools(),
            )
            tools_used.extend(agent_result.tools_used)
        except Exception:
            self._append_unique(tools_used, "agent_retrieval_failed")

        if agent_result is not None and agent_result.evidence:
            evidence = agent_result.evidence
        else:
            evidence = self.run_bm25(prompt=prompt, top_k=8)
            self._append_unique(tools_used, "bm25_search_fallback")

        citations = self._build_citations(evidence)
        validation = self._citation_validator.validate(citations)
        if not validation.ok:
            self._append_unique(tools_used, "citation_validation_failed")

        return RetrievalResult(
            evidence=evidence,
            citations=citations,
            tools_used=tools_used,
        )

    def _synthesis_context(
        self,
        *,
        prompt: str,
        citations: list[RagCitation],
    ) -> tuple[str, str]:
        """Build system + user prompts for synthesis. Shared by sync and streaming paths."""
        context_lines: list[str] = []
        for idx, citation in enumerate(citations, start=1):
            context_lines.append(
                f"[{idx}] doc={citation.document_id} page={citation.page_number} "
                f"chunk={citation.chunk_id}: {citation.supporting_quote}"
            )

        system = (
            "You are a document Q&A assistant. "
            "Answer the user's question using only the provided evidence. "
            "If the evidence is insufficient, say you don't know. Keep the answer concise."
        )
        user = f"Question: {prompt}\n\nEvidence:\n" + "\n".join(context_lines)
        return system, user

    async def stream_synthesis(
        self,
        *,
        prompt: str,
        retrieval: RetrievalResult,
        reasoning_effort: ReasoningEffort,
    ) -> AsyncIterator[str]:
        """Stream answer tokens from OpenAI. Falls back to simple summary on error."""
        if not retrieval.evidence:
            yield (
                "I couldn't find relevant information in the indexed "
                "documents to answer that question."
            )
            return

        model = os.getenv("SYNEXTRA_CHAT_MODEL", "gpt-5.2")
        system, user = self._synthesis_context(
            prompt=prompt, citations=retrieval.citations,
        )

        try:
            stream = await self._async_openai_client.responses.create(
                model=model,
                instructions=system,
                input=user,
                reasoning={"effort": reasoning_effort},
                stream=True,
            )
            async for event in stream:
                if event.type == "response.output_text.delta":
                    yield event.delta
        except Exception:
            yield _simple_summary(retrieval.evidence)
