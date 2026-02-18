from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any

import anyio
from openai import OpenAI, pydantic_function_tool
from pydantic import BaseModel

from synextra_backend.repositories.rag_document_repository import RagDocumentRepository
from synextra_backend.retrieval.bm25_search import Bm25IndexStore
from synextra_backend.retrieval.evidence_merger import reciprocal_rank_fusion
from synextra_backend.retrieval.openai_file_search import OpenAIFileSearch
from synextra_backend.retrieval.types import EvidenceChunk
from synextra_backend.schemas.rag_chat import (
    RagChatRequest,
    RagChatResponse,
    RagCitation,
    ReasoningEffort,
    RetrievalMode,
)
from synextra_backend.services.citation_validator import CitationValidator
from synextra_backend.services.session_memory import SessionMemory

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class Bm25RetrievalTool(BaseModel):
    query: str
    top_k: int = 8


class VectorRetrievalTool(BaseModel):
    query: str
    top_k: int = 8


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
        self._openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def handle_message(self, *, session_id: str, request: RagChatRequest) -> RagChatResponse:
        prompt = request.prompt.strip()
        mode = request.retrieval_mode
        reasoning_effort = request.reasoning_effort

        # Record user turn.
        self._session_memory.append_turn(
            session_id=session_id,
            role="user",
            content=prompt,
            mode=mode,
        )

        result = await self._run_retrieval(
            prompt=prompt,
            mode=mode,
            reasoning_effort=reasoning_effort,
        )

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

    def run_bm25(self, *, prompt: str, top_k: int = 8) -> list[EvidenceChunk]:
        return self._bm25_store.search(query=prompt, top_k=top_k)

    def run_vector(self, *, prompt: str, top_k: int = 8) -> list[EvidenceChunk]:
        vector_store_ids = self._repository.list_vector_store_ids()
        if not vector_store_ids:
            return []
        file_search = OpenAIFileSearch()
        return file_search.search(vector_store_ids=vector_store_ids, query=prompt, top_k=top_k)

    def _dispatch_tool_call(self, *, tool_name: str, args: str) -> Any:
        parsed = json.loads(args) if args else {}
        query = str(parsed.get("query", "")).strip()
        top_k_raw = parsed.get("top_k", 8)
        top_k = int(top_k_raw) if isinstance(top_k_raw, int | str) else 8
        top_k = max(1, top_k)

        if not query:
            raise ValueError("Tool call is missing query")

        match tool_name:
            case "bm25_search":
                return self.run_bm25(prompt=query, top_k=top_k)
            case "vector_search":
                return self.run_vector(prompt=query, top_k=top_k)
            case _:
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

    def _tools_for_mode(self, mode: RetrievalMode) -> list[Any]:
        if mode == "embedded":
            return [pydantic_function_tool(Bm25RetrievalTool, name="bm25_search")]
        if mode == "vector":
            return [pydantic_function_tool(VectorRetrievalTool, name="vector_search")]
        return [
            pydantic_function_tool(Bm25RetrievalTool, name="bm25_search"),
            pydantic_function_tool(VectorRetrievalTool, name="vector_search"),
        ]

    def _agent_instructions_for_mode(self, mode: RetrievalMode) -> str:
        base = (
            "You are a retrieval-augmented assistant. "
            "Always call the provided retrieval tool(s) before you answer. "
            "Use top_k=8 unless the user asks for a different scope. "
            "Answer only using retrieved evidence and be concise."
        )
        if mode == "hybrid":
            return base + " In hybrid mode, call bm25_search and vector_search once each."
        if mode == "vector":
            return base + " In vector mode, use vector_search."
        return base + " In embedded mode, use bm25_search."

    async def _run_retrieval(
        self,
        *,
        prompt: str,
        mode: RetrievalMode,
        reasoning_effort: ReasoningEffort,
    ) -> OrchestratorResult:
        tools_used: list[str] = []

        agent_result: AgentCallResult | None = None
        try:
            model = os.getenv("SYNEXTRA_CHAT_MODEL", "gpt-5.2")
            agent_result = self._call_agent(
                client=self._openai_client,
                model=model,
                instructions=self._agent_instructions_for_mode(mode),
                input=f"Question: {prompt}",
                reasoning_effort=reasoning_effort,
                tools=self._tools_for_mode(mode),
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

        evidence, fallback_tools = await self._run_manual_retrieval(prompt=prompt, mode=mode)
        for tool in fallback_tools:
            self._append_unique(tools_used, tool)

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

    async def _run_manual_retrieval(
        self,
        *,
        prompt: str,
        mode: RetrievalMode,
    ) -> tuple[list[EvidenceChunk], list[str]]:
        tools_used: list[str] = []
        bm25_evidence: list[EvidenceChunk] = []
        vector_evidence: list[EvidenceChunk] = []

        if mode == "embedded":
            tools_used.append("bm25_search")
            return self.run_bm25(prompt=prompt, top_k=8), tools_used

        if mode == "vector":
            tools_used.append("openai_vector_store_search")
            try:
                return self.run_vector(prompt=prompt, top_k=8), tools_used
            except Exception:
                tools_used.append("bm25_search_fallback")
                return self.run_bm25(prompt=prompt, top_k=8), tools_used

        tools_used.extend(["bm25_search", "openai_vector_store_search"])
        try:
            async with anyio.create_task_group() as tg:
                bm25_holder: dict[str, list[EvidenceChunk]] = {}
                vector_holder: dict[str, list[EvidenceChunk]] = {}

                async def run_b() -> None:
                    bm25_holder["value"] = self.run_bm25(prompt=prompt, top_k=8)

                async def run_v() -> None:
                    vector_holder["value"] = self.run_vector(prompt=prompt, top_k=8)

                tg.start_soon(run_b)
                tg.start_soon(run_v)

            bm25_evidence = bm25_holder.get("value", [])
            vector_evidence = vector_holder.get("value", [])
        except Exception:
            bm25_evidence = self.run_bm25(prompt=prompt, top_k=8)
            vector_evidence = []
            tools_used.append("openai_vector_store_search_failed")

        return reciprocal_rank_fusion([bm25_evidence, vector_evidence], top_k=8), tools_used

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
                f"[{idx}] doc={citation.document_id} page={citation.page_number}"
                f"chunk={citation.chunk_id}: {citation.supporting_quote}"
            )

        system = (
            "You are a retrieval-augmented assistant."
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
