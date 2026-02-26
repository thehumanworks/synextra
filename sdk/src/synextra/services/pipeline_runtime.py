from __future__ import annotations

import asyncio
import os
import re
import threading
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Sequence
from datetime import UTC, datetime
from typing import Any, TypeVar, cast
from uuid import uuid4

from agents import Agent, Runner
from agents.model_settings import ModelSettings
from openai.types.shared import Reasoning

from synextra.client import Synextra
from synextra.retrieval.types import EvidenceChunk
from synextra.schemas.pipeline import (
    AgentNodeSpec,
    Bm25SearchNodeSpec,
    IngestNodeSpec,
    InputNodeSpec,
    OutputNodeSpec,
    ParallelReadDocumentQuery,
    ParallelSearchNodeSpec,
    PipelineAgentOutputEnvelope,
    PipelineAgentRunRequest,
    PipelineCitation,
    PipelineDocumentRef,
    PipelineEdgeSpec,
    PipelineEvidenceChunk,
    PipelineNodeCompletedEvent,
    PipelineNodeFailedEvent,
    PipelineNodeSpec,
    PipelineNodeStartedEvent,
    PipelineNodeTokenEvent,
    PipelineParallelSearchRequest,
    PipelineReadDocumentRequest,
    PipelineRunCompletedEvent,
    PipelineRunEvent,
    PipelineRunFailedEvent,
    PipelineRunPausedEvent,
    PipelineRunResumedEvent,
    PipelineRunSpec,
    PipelineRunStartedEvent,
    ReadDocumentNodeSpec,
    ReasoningEffort,
)

_STREAM_CHUNK_RE = re.compile(r"\S+\s*")
_SEARCH_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_DEFAULT_PIPELINE_MODEL = "gpt-5.2"
_OPENAI_KEY_ENV_VARS = ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY")

T = TypeVar("T")


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _stream_chunks(text: str) -> list[str]:
    parts = _STREAM_CHUNK_RE.findall(text)
    if parts:
        return parts
    return [text] if text else []


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()


def _tokenize_search(text: str) -> set[str]:
    return {token.lower() for token in _SEARCH_TOKEN_RE.findall(text)}


def _truncate(text: str, limit: int = 240) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def _ordered_unique(items: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _extract_summary_points(
    chunks: list[PipelineEvidenceChunk], *, max_points: int = 4
) -> list[str]:
    points: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        for sentence in _SENTENCE_SPLIT_RE.split(chunk.text):
            normalized = _normalize_whitespace(sentence)
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            points.append(_truncate(normalized, limit=200))
            if len(points) >= max_points:
                return points
    return points


def _render_template(template: str, *, query: str) -> str:
    if "{query}" not in template:
        return template.strip() or query
    return template.replace("{query}", query).strip()


def _has_configured_openai_key() -> bool:
    for env_var in _OPENAI_KEY_ENV_VARS:
        value = os.getenv(env_var, "").strip()
        if value:
            return True
    return False


def _pipeline_chat_model() -> str:
    configured = os.getenv("SYNEXTRA_CHAT_MODEL", "").strip()
    if configured:
        return configured
    return _DEFAULT_PIPELINE_MODEL


def _run_awaitable[T](factory: Callable[[], Awaitable[T]]) -> T:
    """Run an awaitable from sync runtime code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(cast(Coroutine[Any, Any, T], factory()))

    if not loop.is_running():
        return loop.run_until_complete(factory())

    result: dict[str, T] = {}
    error: dict[str, BaseException] = {}

    def _target() -> None:
        try:
            result["value"] = asyncio.run(cast(Coroutine[Any, Any, T], factory()))
        except BaseException as exc:  # pragma: no cover
            error["exc"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()

    if "exc" in error:
        raise error["exc"]

    if "value" not in result:  # pragma: no cover
        raise RuntimeError("Async execution failed without returning a value")

    return result["value"]


def _classify_model_error(model_error: str) -> str:
    lowered = model_error.lower()
    if "insufficient_quota" in lowered:
        return "openai_quota_exhausted"
    if ("error code: 429" in lowered or "status code: 429" in lowered) and "quota" in lowered:
        return "openai_quota_exhausted"
    if model_error == "missing_openai_api_key":
        return "missing_openai_api_key"
    if model_error == "empty_model_output":
        return "empty_model_output"
    return "model_call_failed"


def _model_error_message(error_code: str) -> str:
    if error_code == "openai_quota_exhausted":
        return "OpenAI API quota is exhausted for the configured key."
    if error_code == "missing_openai_api_key":
        return "No OpenAI API key is configured for the backend."
    if error_code == "empty_model_output":
        return "The model returned an empty output."
    return "The model call failed before a response was produced."


def _dedupe_evidence(chunks: list[PipelineEvidenceChunk]) -> list[PipelineEvidenceChunk]:
    deduped: list[PipelineEvidenceChunk] = []
    seen: set[tuple[str, str]] = set()
    for chunk in chunks:
        key = (chunk.document_id, chunk.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return deduped


def _summarize_evidence(chunks: list[PipelineEvidenceChunk], *, max_items: int = 4) -> str:
    if not chunks:
        return ""
    snippets: list[str] = []
    for chunk in chunks[:max_items]:
        text = _truncate(chunk.text, limit=180)
        if text:
            snippets.append(text)
    return "\n".join(f"- {snippet}" for snippet in snippets)


class PipelineRuntime:
    """Executes composable pipeline DAGs against the Synextra runtime."""

    def __init__(self, *, synextra: Synextra) -> None:
        self._synextra = synextra

    @property
    def synextra(self) -> Synextra:
        return self._synextra

    def bm25_search(
        self,
        *,
        query: str,
        top_k: int = 8,
        document_ids: list[str] | None = None,
    ) -> list[PipelineEvidenceChunk]:
        prompt = query.strip()
        raw = self._synextra.orchestrator.run_bm25(prompt=prompt, top_k=top_k)
        evidence = [self._from_evidence_chunk(chunk) for chunk in raw]
        if document_ids:
            allow = set(document_ids)
            evidence = [chunk for chunk in evidence if chunk.document_id in allow]
        if evidence:
            return evidence
        if not prompt:
            return []
        return self._fallback_lexical_bm25(
            query=prompt,
            top_k=top_k,
            document_ids=document_ids,
        )

    def read_document(
        self,
        *,
        page: int,
        start_line: int | None = None,
        end_line: int | None = None,
        document_id: str | None = None,
    ) -> list[PipelineEvidenceChunk]:
        resolved_document_id = document_id or self._default_document_id()
        if resolved_document_id is None:
            return []
        raw = self._synextra.orchestrator.run_read_document(
            document_id=resolved_document_id,
            page=page,
            start_line=start_line,
            end_line=end_line,
        )
        return [self._from_evidence_chunk(chunk) for chunk in raw]

    async def parallel_search(
        self, request: PipelineParallelSearchRequest
    ) -> list[PipelineEvidenceChunk]:
        async def run_query(query: Any) -> list[PipelineEvidenceChunk]:
            if isinstance(query, ParallelReadDocumentQuery):
                return self.read_document(
                    page=query.page,
                    start_line=query.start_line,
                    end_line=query.end_line,
                    document_id=query.document_id,
                )
            rendered_query = _render_template(query.query_template, query=request.query)
            return self.bm25_search(
                query=rendered_query,
                top_k=query.top_k,
                document_ids=query.document_ids,
            )

        groups = await asyncio.gather(*[run_query(item) for item in request.queries])
        flattened = [chunk for group in groups for chunk in group]
        return _dedupe_evidence(flattened)

    def run_agent(self, request: PipelineAgentRunRequest) -> PipelineAgentOutputEnvelope:
        prompt = request.prompt.strip()
        tool_evidence, executed_tools = self._run_selected_tools(
            prompt=prompt,
            tools=request.tools,
            candidate_document_ids=request.document_ids,
            existing_evidence=request.evidence,
        )
        evidence = _dedupe_evidence([*request.evidence, *tool_evidence])
        upstream_answers = [
            output.answer.strip() for output in request.upstream_outputs if output.answer.strip()
        ]
        evidence_summary = _summarize_evidence(evidence)
        tools_used: list[str] = list(executed_tools)
        for chunk in evidence:
            if chunk.source_tool and chunk.source_tool not in tools_used:
                tools_used.append(chunk.source_tool)

        model_answer, model_error = self._generate_model_answer(
            prompt=prompt,
            reasoning_effort=request.reasoning_effort,
            upstream_answers=upstream_answers,
            evidence=evidence,
            system_instructions=request.system_instructions,
        )
        if model_answer:
            answer = model_answer
        else:
            fallback_answer = self._build_fallback_answer(
                prompt=prompt,
                upstream_answers=upstream_answers,
                evidence_summary=evidence_summary,
            )
            if model_error:
                model_error_code = _classify_model_error(model_error)
                if "agent_model_generation_failed" not in tools_used:
                    tools_used.append("agent_model_generation_failed")
                detailed_marker = f"agent_model_generation_failed:{model_error_code}"
                if detailed_marker not in tools_used:
                    tools_used.append(detailed_marker)
                answer = self._build_model_failure_answer(
                    prompt=prompt,
                    upstream_answers=upstream_answers,
                    evidence=evidence,
                    error_code=model_error_code,
                )
            else:
                answer = fallback_answer

        citations = self._build_citations(evidence)
        return PipelineAgentOutputEnvelope(
            answer=answer,
            citations=citations,
            tools_used=tools_used,
            evidence=evidence,
            upstream_answers=upstream_answers,
        )

    def _run_selected_tools(
        self,
        *,
        prompt: str,
        tools: Sequence[str],
        candidate_document_ids: Sequence[str],
        existing_evidence: list[PipelineEvidenceChunk],
    ) -> tuple[list[PipelineEvidenceChunk], list[str]]:
        selected = _ordered_unique([tool.strip() for tool in tools if tool.strip()])
        if not selected:
            return [], []

        run_doc_ids = _ordered_unique(
            [doc_id.strip() for doc_id in candidate_document_ids if doc_id]
        )
        existing_doc_ids = _ordered_unique(
            [chunk.document_id for chunk in existing_evidence if chunk.document_id]
        )
        scoped_doc_ids = run_doc_ids or existing_doc_ids
        search_doc_ids = scoped_doc_ids or None
        default_document_id = scoped_doc_ids[0] if scoped_doc_ids else None

        collected: list[PipelineEvidenceChunk] = []
        executed_tools: list[str] = []

        for tool in selected:
            if tool == "bm25_search":
                collected.extend(
                    self.bm25_search(
                        query=prompt,
                        top_k=8,
                        document_ids=search_doc_ids,
                    )
                )
                if default_document_id is None:
                    first_doc_id = next(
                        (chunk.document_id for chunk in collected if chunk.document_id),
                        None,
                    )
                    default_document_id = first_doc_id
                executed_tools.append(tool)
                continue

            if tool == "read_document":
                if default_document_id is not None:
                    collected.extend(
                        self.read_document(
                            page=0,
                            document_id=default_document_id,
                        )
                    )
                    executed_tools.append(tool)
                continue

            if tool == "parallel_search":
                # Run both retrieval styles for parity with the standalone parallel tool.
                parallel_evidence = self.bm25_search(
                    query=prompt,
                    top_k=8,
                    document_ids=search_doc_ids,
                )
                if default_document_id is not None:
                    parallel_evidence.extend(
                        self.read_document(
                            page=0,
                            document_id=default_document_id,
                        )
                    )
                collected.extend(_dedupe_evidence(parallel_evidence))
                if default_document_id is None:
                    first_doc_id = next(
                        (chunk.document_id for chunk in parallel_evidence if chunk.document_id),
                        None,
                    )
                    default_document_id = first_doc_id
                executed_tools.append(tool)

        return _dedupe_evidence(collected), executed_tools

    def _generate_model_answer(
        self,
        *,
        prompt: str,
        reasoning_effort: ReasoningEffort,
        upstream_answers: list[str],
        evidence: list[PipelineEvidenceChunk],
        system_instructions: str | None = None,
    ) -> tuple[str, str | None]:
        if not _has_configured_openai_key():
            return "", "missing_openai_api_key"

        synthesis_prompt = self._build_model_input(
            prompt=prompt,
            upstream_answers=upstream_answers,
            evidence=evidence,
        )

        default_instructions = (
            "You are a synthesis assistant. "
            "Use only the supplied evidence and upstream results. "
            "Do not invent facts. If evidence is insufficient, say so clearly."
        )

        async def _run() -> str:
            agent: Agent = Agent(
                name="synextra_pipeline_agent",
                instructions=system_instructions or default_instructions,
                model=_pipeline_chat_model(),
                model_settings=ModelSettings(
                    reasoning=Reasoning(effort=reasoning_effort, summary="concise"),
                ),
            )
            result = await Runner.run(agent, input=synthesis_prompt)
            if not result.final_output:
                return ""
            return str(result.final_output).strip()

        try:
            answer = _run_awaitable(_run)
            if answer:
                return answer, None
            return "", "empty_model_output"
        except Exception as exc:
            return "", str(exc) or "model_call_failed"

    @staticmethod
    def _build_model_input(
        *,
        prompt: str,
        upstream_answers: list[str],
        evidence: list[PipelineEvidenceChunk],
    ) -> str:
        sections = [f"Task:\n{prompt}"]
        if upstream_answers:
            upstream_lines = "\n".join(f"- {answer}" for answer in upstream_answers)
            sections.append("Upstream results:\n" + upstream_lines)

        if evidence:
            evidence_lines: list[str] = []
            for idx, chunk in enumerate(evidence[:16], start=1):
                page = chunk.page_number if chunk.page_number is not None else "unknown"
                evidence_lines.append(
                    f"[{idx}] doc={chunk.document_id} page={page} "
                    f"tool={chunk.source_tool}: {_truncate(chunk.text, limit=700)}"
                )
            sections.append("Evidence:\n" + "\n".join(evidence_lines))
        else:
            sections.append("Evidence:\n(no evidence provided)")

        sections.append(
            "Response requirements:\n"
            "- Keep the answer concise and directly address the task.\n"
            "- Use only provided evidence.\n"
            "- Explicitly state uncertainty if evidence is insufficient."
        )
        return "\n\n".join(sections)

    @staticmethod
    def _build_fallback_answer(
        *,
        prompt: str,
        upstream_answers: list[str],
        evidence_summary: str,
    ) -> str:
        answer_parts: list[str] = []
        if upstream_answers:
            upstream_list = "\n".join(f"- {text}" for text in upstream_answers)
            answer_parts.append("Upstream results:\n" + upstream_list)
        if evidence_summary:
            answer_parts.append("Supporting evidence:\n" + evidence_summary)
        if not answer_parts:
            answer_parts.append("No upstream outputs or evidence were available for this step.")
        answer_parts.append(f"Task: {prompt}")
        return "\n\n".join(answer_parts)

    @staticmethod
    def _build_model_failure_answer(
        *,
        prompt: str,
        upstream_answers: list[str],
        evidence: list[PipelineEvidenceChunk],
        error_code: str,
    ) -> str:
        summary_points = _extract_summary_points(evidence, max_points=4)
        sections: list[str] = [
            "Model generation unavailable.",
            f"Reason: {_model_error_message(error_code)}",
        ]
        if summary_points:
            bullet_points = "\n".join(f"- {point}" for point in summary_points)
            sections.append("Evidence-based summary:\n" + bullet_points)
        elif upstream_answers:
            upstream_list = "\n".join(f"- {text}" for text in upstream_answers)
            sections.append("Upstream results:\n" + upstream_list)
        else:
            sections.append("No evidence was available to build a fallback summary.")

        sections.append(f"Task: {prompt}")
        return "\n\n".join(sections)

    async def run_stream(
        self,
        *,
        spec: PipelineRunSpec,
        files_by_node: dict[str, tuple[str, str | None, bytes]],
        run_id: str | None = None,
        pause_event: asyncio.Event | None = None,
    ) -> AsyncIterator[PipelineRunEvent]:
        if run_id is None:
            run_id = uuid4().hex
        timestamp = _now_iso()
        yield PipelineRunStartedEvent(run_id=run_id, timestamp=timestamp)

        try:
            ordered_nodes = self._topological_order(spec.nodes, spec.edges)
        except ValueError as exc:
            fail = PipelineRunFailedEvent(
                run_id=run_id,
                error=str(exc),
                timestamp=_now_iso(),
            )
            yield fail
            return

        outputs: dict[str, dict[str, Any]] = {}
        incoming = self._incoming_sources(spec.edges)

        for node in ordered_nodes:
            if pause_event is not None and not pause_event.is_set():
                yield PipelineRunPausedEvent(run_id=run_id, timestamp=_now_iso())
                await pause_event.wait()
                yield PipelineRunResumedEvent(run_id=run_id, timestamp=_now_iso())
            yield PipelineNodeStartedEvent(
                run_id=run_id,
                node_id=node.id,
                node_type=node.type,
                timestamp=_now_iso(),
            )
            try:
                output = await self._execute_node(
                    node=node,
                    query=spec.query,
                    incoming_sources=incoming.get(node.id, []),
                    outputs=outputs,
                    files_by_node=files_by_node,
                )
                if node.type == "agent":
                    envelope = PipelineAgentOutputEnvelope.model_validate(output["agent_output"])
                    for token in _stream_chunks(envelope.answer):
                        yield PipelineNodeTokenEvent(
                            run_id=run_id,
                            node_id=node.id,
                            node_type="agent",
                            token=token,
                            timestamp=_now_iso(),
                        )
                yield PipelineNodeCompletedEvent(
                    run_id=run_id,
                    node_id=node.id,
                    node_type=node.type,
                    output=output,
                    timestamp=_now_iso(),
                )
                outputs[node.id] = output
            except Exception as exc:
                message = str(exc) or f"{node.id} execution failed"
                yield PipelineNodeFailedEvent(
                    run_id=run_id,
                    node_id=node.id,
                    node_type=node.type,
                    error=message,
                    timestamp=_now_iso(),
                )
                yield PipelineRunFailedEvent(
                    run_id=run_id,
                    error=message,
                    timestamp=_now_iso(),
                )
                return

        final_outputs: dict[str, object] = {}
        for node in spec.nodes:
            if node.type == "output" and node.id in outputs:
                final_outputs[node.id] = outputs[node.id]

        if not final_outputs:
            for node in reversed(ordered_nodes):
                if node.type == "agent" and node.id in outputs:
                    final_outputs[node.id] = outputs[node.id]
                    break

        yield PipelineRunCompletedEvent(
            run_id=run_id,
            outputs=final_outputs,
            timestamp=_now_iso(),
        )

    async def _execute_node(
        self,
        *,
        node: PipelineNodeSpec,
        query: str,
        incoming_sources: list[str],
        outputs: dict[str, dict[str, Any]],
        files_by_node: dict[str, tuple[str, str | None, bytes]],
    ) -> dict[str, Any]:
        upstream = [outputs[source_id] for source_id in incoming_sources if source_id in outputs]

        if isinstance(node, InputNodeSpec):
            result: dict[str, Any] = {"prompt_text": node.config.prompt_text}
            file_info = files_by_node.get(node.id)
            if file_info is not None:
                filename, content_type, payload = file_info
                ingest = self._synextra.ingest(
                    payload, filename=filename, content_type=content_type
                )
                doc = PipelineDocumentRef(
                    document_id=ingest.document_id,
                    filename=ingest.filename,
                    page_count=ingest.page_count,
                    chunk_count=ingest.chunk_count,
                )
                result["documents"] = [doc.model_dump()]
                result["indexed_chunk_count"] = ingest.indexed_chunk_count
            return result

        if isinstance(node, IngestNodeSpec):
            file_info = files_by_node.get(node.id)
            if file_info is None:
                raise ValueError(f"Missing uploaded file for ingest node {node.id}")
            filename, content_type, payload = file_info
            ingest = self._synextra.ingest(payload, filename=filename, content_type=content_type)
            doc = PipelineDocumentRef(
                document_id=ingest.document_id,
                filename=ingest.filename,
                page_count=ingest.page_count,
                chunk_count=ingest.chunk_count,
            )
            return {
                "documents": [doc.model_dump()],
                "indexed_chunk_count": ingest.indexed_chunk_count,
            }

        if isinstance(node, Bm25SearchNodeSpec):
            rendered_query = _render_template(node.config.query_template, query=query)
            evidence = self.bm25_search(
                query=rendered_query,
                top_k=node.config.top_k,
                document_ids=node.config.document_ids,
            )
            return {
                "query": rendered_query,
                "evidence": [chunk.model_dump() for chunk in evidence],
                "evidence_count": len(evidence),
            }

        if isinstance(node, ReadDocumentNodeSpec):
            doc_id = node.config.document_id or self._first_document_id(upstream)
            read_request = PipelineReadDocumentRequest(
                page=node.config.page,
                start_line=node.config.start_line,
                end_line=node.config.end_line,
                document_id=doc_id,
            )
            evidence = self.read_document(
                page=read_request.page,
                start_line=read_request.start_line,
                end_line=read_request.end_line,
                document_id=read_request.document_id,
            )
            return {
                "document_id": read_request.document_id,
                "page": read_request.page,
                "evidence": [chunk.model_dump() for chunk in evidence],
                "evidence_count": len(evidence),
            }

        if isinstance(node, ParallelSearchNodeSpec):
            parallel_request = PipelineParallelSearchRequest(
                query=query,
                queries=node.config.queries,
            )
            evidence = await self.parallel_search(parallel_request)
            return {
                "evidence": [chunk.model_dump() for chunk in evidence],
                "evidence_count": len(evidence),
            }

        if isinstance(node, AgentNodeSpec):
            evidence = self._collect_evidence(upstream)
            upstream_outputs = self._collect_upstream_agent_outputs(upstream)
            document_ids = self._collect_document_ids(upstream)
            agent_request = PipelineAgentRunRequest(
                prompt=_render_template(node.config.prompt_template, query=query),
                reasoning_effort=node.config.reasoning_effort,
                review_enabled=node.config.review_enabled,
                tools=node.config.tools,
                document_ids=document_ids,
                evidence=evidence,
                upstream_outputs=upstream_outputs,
                system_instructions=node.config.system_instructions,
            )
            envelope = self.run_agent(agent_request)
            return {
                "agent_output": envelope.model_dump(),
                "answer": envelope.answer,
                "citations": [citation.model_dump() for citation in envelope.citations],
                "tools_used": envelope.tools_used,
                "evidence_count": len(envelope.evidence),
            }

        if isinstance(node, OutputNodeSpec):
            for source_output in reversed(upstream):
                raw = source_output.get("agent_output")
                if isinstance(raw, dict):
                    envelope = PipelineAgentOutputEnvelope.model_validate(raw)
                    return {
                        "output": envelope.model_dump(),
                        "answer": envelope.answer,
                    }
            return {"output": None, "answer": ""}

        raise ValueError(f"Unsupported node type: {node.type}")

    @staticmethod
    def _incoming_sources(edges: list[PipelineEdgeSpec]) -> dict[str, list[str]]:
        incoming: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            incoming[edge.target].append(edge.source)
        return incoming

    def _topological_order(
        self,
        nodes: list[PipelineNodeSpec],
        edges: list[PipelineEdgeSpec],
    ) -> list[PipelineNodeSpec]:
        by_id = {node.id: node for node in nodes}
        if len(by_id) != len(nodes):
            raise ValueError("Pipeline nodes contain duplicate ids")

        indegree: dict[str, int] = {node.id: 0 for node in nodes}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for edge in edges:
            if edge.source not in by_id:
                raise ValueError(f"Unknown edge source node: {edge.source}")
            if edge.target not in by_id:
                raise ValueError(f"Unknown edge target node: {edge.target}")
            adjacency[edge.source].append(edge.target)
            indegree[edge.target] += 1

        queue: deque[str] = deque(sorted(node_id for node_id, deg in indegree.items() if deg == 0))
        ordered_ids: list[str] = []

        while queue:
            current = queue.popleft()
            ordered_ids.append(current)
            for nxt in adjacency.get(current, []):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)

        if len(ordered_ids) != len(nodes):
            raise ValueError("Pipeline graph contains a cycle")
        return [by_id[node_id] for node_id in ordered_ids]

    @staticmethod
    def _from_evidence_chunk(chunk: EvidenceChunk) -> PipelineEvidenceChunk:
        return PipelineEvidenceChunk(
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            page_number=chunk.page_number,
            text=chunk.text,
            score=chunk.score,
            source_tool=chunk.source_tool,
        )

    def _default_document_id(self) -> str | None:
        docs = self._synextra.document_store.list_documents()
        if not docs:
            return None
        return docs[0].document_id

    @staticmethod
    def _first_document_id(upstream: list[dict[str, Any]]) -> str | None:
        for item in upstream:
            docs = item.get("documents")
            if not isinstance(docs, list):
                continue
            for doc in docs:
                if isinstance(doc, dict):
                    document_id = doc.get("document_id")
                    if isinstance(document_id, str):
                        return document_id
        return None

    @staticmethod
    def _collect_evidence(upstream: list[dict[str, Any]]) -> list[PipelineEvidenceChunk]:
        evidence: list[PipelineEvidenceChunk] = []
        for item in upstream:
            raw_evidence = item.get("evidence")
            if isinstance(raw_evidence, list):
                for chunk in raw_evidence:
                    evidence.append(PipelineEvidenceChunk.model_validate(chunk))

            raw_output = item.get("agent_output")
            if isinstance(raw_output, dict):
                envelope = PipelineAgentOutputEnvelope.model_validate(raw_output)
                evidence.extend(envelope.evidence)
        return _dedupe_evidence(evidence)

    @staticmethod
    def _collect_upstream_agent_outputs(
        upstream: list[dict[str, Any]],
    ) -> list[PipelineAgentOutputEnvelope]:
        collected: list[PipelineAgentOutputEnvelope] = []
        for item in upstream:
            raw = item.get("agent_output")
            if isinstance(raw, dict):
                collected.append(PipelineAgentOutputEnvelope.model_validate(raw))
        return collected

    @staticmethod
    def _collect_document_ids(upstream: list[dict[str, Any]]) -> list[str]:
        document_ids: list[str] = []
        seen: set[str] = set()

        def add(document_id: str | None) -> None:
            if not document_id or document_id in seen:
                return
            seen.add(document_id)
            document_ids.append(document_id)

        for item in upstream:
            raw_documents = item.get("documents")
            if isinstance(raw_documents, list):
                for raw_document in raw_documents:
                    if isinstance(raw_document, dict):
                        maybe_document_id = raw_document.get("document_id")
                        if isinstance(maybe_document_id, str):
                            add(maybe_document_id)

            raw_evidence = item.get("evidence")
            if isinstance(raw_evidence, list):
                for raw_chunk in raw_evidence:
                    if isinstance(raw_chunk, dict):
                        maybe_document_id = raw_chunk.get("document_id")
                        if isinstance(maybe_document_id, str):
                            add(maybe_document_id)

            raw_output = item.get("agent_output")
            if isinstance(raw_output, dict):
                envelope = PipelineAgentOutputEnvelope.model_validate(raw_output)
                for chunk in envelope.evidence:
                    add(chunk.document_id)
                for citation in envelope.citations:
                    add(citation.document_id)

        return document_ids

    @staticmethod
    def _build_citations(chunks: list[PipelineEvidenceChunk]) -> list[PipelineCitation]:
        citations: list[PipelineCitation] = []
        seen: set[tuple[str, str]] = set()
        for chunk in chunks:
            key = (chunk.document_id, chunk.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            quote = _truncate(chunk.text, limit=240)
            if not quote:
                continue
            citations.append(
                PipelineCitation(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    page_number=chunk.page_number,
                    supporting_quote=quote,
                    source_tool=chunk.source_tool,
                    score=chunk.score,
                )
            )
        return citations

    def _fallback_lexical_bm25(
        self,
        *,
        query: str,
        top_k: int,
        document_ids: list[str] | None,
    ) -> list[PipelineEvidenceChunk]:
        query_tokens = _tokenize_search(query)
        if not query_tokens:
            return []

        if document_ids:
            candidate_ids = document_ids
        else:
            candidate_ids = [
                document.document_id for document in self._synextra.document_store.list_documents()
            ]

        scored_chunks: list[tuple[int, PipelineEvidenceChunk]] = []
        for document_id in candidate_ids:
            for chunk in self._synextra.repository.list_chunks(document_id):
                chunk_tokens = _tokenize_search(chunk.text)
                overlap = len(query_tokens.intersection(chunk_tokens))
                if overlap <= 0:
                    continue
                scored_chunks.append(
                    (
                        overlap,
                        PipelineEvidenceChunk(
                            document_id=chunk.document_id,
                            chunk_id=chunk.chunk_id,
                            page_number=chunk.page_number,
                            text=chunk.text,
                            score=float(overlap),
                            source_tool="bm25_search",
                        ),
                    )
                )

        scored_chunks.sort(
            key=lambda item: (
                -item[0],
                item[1].document_id,
                item[1].page_number if item[1].page_number is not None else -1,
                item[1].chunk_id,
            )
        )
        return [chunk for _, chunk in scored_chunks[: max(1, top_k)]]
