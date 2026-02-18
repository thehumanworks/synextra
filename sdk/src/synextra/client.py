from __future__ import annotations

import asyncio
import mimetypes
import os
import threading
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

from synextra.repositories.rag_document_repository import (
    ChunkRecord,
    InMemoryRagDocumentRepository,
    RagDocumentRepository,
)
from synextra.retrieval.bm25_search import Bm25IndexStore
from synextra.schemas.rag_chat import (
    RagChatRequest,
    RagCitation,
    RetrievalMode,
    ReviewEvent,
    StreamEvent,
)
from synextra.services.citation_validator import CitationValidator
from synextra.services.document_ingestion import (
    DocumentParseError,
    UnsupportedDocumentTypeError,
    parse_document,
)
from synextra.services.document_store import DocumentStore
from synextra.services.embedded_store_persistence import EmbeddedStorePersistence
from synextra.services.pdf_ingestion import PdfEncryptedError, sha256_hex
from synextra.services.rag_agent_orchestrator import RagAgentOrchestrator, RetrievalResult
from synextra.services.session_memory import SessionMemory


class SynextraError(RuntimeError):
    """Base error for the Synextra SDK."""


class SynextraConfigurationError(SynextraError):
    """Raised when the SDK is misconfigured (e.g., missing API key)."""


class SynextraIngestionError(SynextraError):
    """Raised when ingestion fails."""


class SynextraUnsupportedMediaTypeError(SynextraIngestionError):
    """Raised when an uploaded document type is not supported."""


class SynextraDocumentParseError(SynextraIngestionError):
    """Raised when a supported document cannot be parsed."""


class SynextraDocumentEncryptedError(SynextraIngestionError):
    """Raised when an encrypted/password-protected document is uploaded."""


class SynextraQueryError(SynextraError):
    """Raised when querying fails."""


@dataclass(frozen=True)
class IngestionResult:
    document_id: str
    filename: str
    mime_type: str
    checksum_sha256: str
    page_count: int
    chunk_count: int
    indexed_chunk_count: int


@dataclass(frozen=True)
class ResearchResult:
    session_id: str
    prompt: str
    mode: RetrievalMode
    retrieval: RetrievalResult
    events: list[StreamEvent]

    @property
    def citations(self) -> list[RagCitation]:
        return list(self.retrieval.citations)

    @property
    def tools_used(self) -> list[str]:
        return list(self.retrieval.tools_used)


ReviewVerdict = Literal["approved", "rejected", "unknown"]


@dataclass(frozen=True)
class ReviewResult:
    verdict: ReviewVerdict
    iterations: int
    feedback: str | None
    citation_ok: bool
    citation_issues: list[str]


@dataclass(frozen=True)
class SynthesisResult:
    session_id: str
    prompt: str
    mode: RetrievalMode
    answer: str
    citations: list[RagCitation]
    tools_used: list[str]


@dataclass(frozen=True)
class QueryResult:
    session_id: str
    prompt: str
    mode: RetrievalMode
    answer: str
    citations: list[RagCitation]
    tools_used: list[str]
    review: ReviewResult


T = TypeVar("T")


def _run_awaitable[T](factory: Callable[[], Awaitable[T]]) -> T:
    """Run an awaitable factory from sync code.

    If an event loop is already running in the current thread (e.g., Jupyter),
    the coroutine is executed in a dedicated thread via asyncio.run.
    """

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
        raise RuntimeError("Async execution failed without an exception")

    return result["value"]


class Synextra:
    """Synextra SDK facade.

    The SDK maintains an in-memory document repository + BM25 index store +
    page-level document store and exposes:

    - ``ingest``: document -> pages/chunks -> repository + document store -> BM25 index
    - ``query``: research -> optional review -> synthesize

    Parameters
    ----------
    openai_api_key:
        If provided, sets ``OPENAI_API_KEY`` for the process (used by ``openai-agents``).
        If omitted, the SDK will read it from the environment.
    model:
        Optional override for the chat model used by the orchestrator.
        Sets ``SYNEXTRA_CHAT_MODEL``.
    repository:
        Optional custom repository implementation. Defaults to in-memory.
    """

    def __init__(
        self,
        openai_api_key: str | None = None,
        *,
        model: str | None = None,
        repository: RagDocumentRepository | None = None,
    ) -> None:
        if openai_api_key is not None:
            os.environ["OPENAI_API_KEY"] = openai_api_key

        if model is not None:
            os.environ["SYNEXTRA_CHAT_MODEL"] = model

        self._repository: RagDocumentRepository = repository or InMemoryRagDocumentRepository()
        self._bm25_store = Bm25IndexStore()
        self._session_memory = SessionMemory()
        self._document_store = DocumentStore()
        self._embedded_store_persistence = EmbeddedStorePersistence(
            repository=self._repository,
            index_store=self._bm25_store,
        )
        self._citation_validator = CitationValidator()

        self._orchestrator = RagAgentOrchestrator(
            repository=self._repository,
            bm25_store=self._bm25_store,
            session_memory=self._session_memory,
            document_store=self._document_store,
        )

    @property
    def repository(self) -> RagDocumentRepository:
        return self._repository

    @property
    def bm25_store(self) -> Bm25IndexStore:
        return self._bm25_store

    @property
    def session_memory(self) -> SessionMemory:
        return self._session_memory

    @property
    def document_store(self) -> DocumentStore:
        return self._document_store

    @property
    def embedded_store_persistence(self) -> EmbeddedStorePersistence:
        return self._embedded_store_persistence

    @property
    def orchestrator(self) -> RagAgentOrchestrator:
        return self._orchestrator

    def _ensure_openai_key(self) -> None:
        if os.getenv("OPENAI_API_KEY"):
            return
        raise SynextraConfigurationError(
            "Missing OPENAI_API_KEY. Provide Synextra(openai_api_key=...) "
            "or set the environment variable."
        )

    def ingest(
        self,
        document: str | Path | bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> IngestionResult:
        """Ingest a supported document into the in-memory stores and BM25 index."""

        if isinstance(document, (str, Path)):
            path = Path(document)
            data = path.read_bytes()
            resolved_filename = filename or path.name
            resolved_content_type = content_type or mimetypes.guess_type(resolved_filename)[0]
        else:
            data = document
            resolved_filename = filename or "document"
            resolved_content_type = content_type

        checksum = sha256_hex(data)

        existing = self._repository.get_document_by_checksum(checksum)
        if existing is not None:
            if not self._document_store.has_document(existing.document_id):
                try:
                    parsed = parse_document(
                        data=data,
                        filename=resolved_filename,
                        content_type=resolved_content_type,
                        document_id=existing.document_id,
                    )
                except PdfEncryptedError as exc:
                    raise SynextraDocumentEncryptedError(
                        "PDF is encrypted or requires a password"
                    ) from exc
                except UnsupportedDocumentTypeError as exc:
                    raise SynextraUnsupportedMediaTypeError(str(exc)) from exc
                except DocumentParseError as exc:
                    raise SynextraDocumentParseError(str(exc)) from exc

                self._document_store.store_pages(
                    document_id=existing.document_id,
                    filename=existing.filename,
                    pages=parsed.pages,
                )

            _duration_ms, _sig, indexed_chunk_count = self._embedded_store_persistence.persist(
                document_id=existing.document_id
            )
            chunks = self._repository.list_chunks(existing.document_id)

            return IngestionResult(
                document_id=existing.document_id,
                filename=existing.filename,
                mime_type=existing.mime_type,
                checksum_sha256=existing.checksum_sha256,
                page_count=existing.page_count,
                chunk_count=len(chunks),
                indexed_chunk_count=indexed_chunk_count,
            )

        document_id = checksum

        try:
            parsed = parse_document(
                data=data,
                filename=resolved_filename,
                content_type=resolved_content_type,
                document_id=document_id,
            )
        except PdfEncryptedError as exc:
            raise SynextraDocumentEncryptedError("PDF is encrypted or requires a password") from exc
        except UnsupportedDocumentTypeError as exc:
            raise SynextraUnsupportedMediaTypeError(str(exc)) from exc
        except DocumentParseError as exc:
            raise SynextraDocumentParseError(str(exc)) from exc

        document_record = self._repository.upsert_document(
            document_id=document_id,
            filename=resolved_filename,
            mime_type=parsed.mime_type,
            checksum_sha256=checksum,
            page_count=parsed.page_count,
        )

        chunk_records: list[ChunkRecord] = []
        for chunk in parsed.chunks:
            chunk_records.append(
                ChunkRecord(
                    chunk_id=chunk.chunk_id,
                    document_id=document_record.document_id,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    token_count=chunk.token_count,
                    citation_span=chunk.citation_span,
                    text=chunk.text,
                    bounding_box=chunk.bounding_box,
                )
            )

        self._repository.replace_chunks(document_record.document_id, chunk_records)
        self._document_store.store_pages(
            document_id=document_record.document_id,
            filename=document_record.filename,
            pages=parsed.pages,
        )

        _duration_ms, _sig, indexed_chunk_count = self._embedded_store_persistence.persist(
            document_id=document_record.document_id
        )

        return IngestionResult(
            document_id=document_record.document_id,
            filename=document_record.filename,
            mime_type=document_record.mime_type,
            checksum_sha256=document_record.checksum_sha256,
            page_count=document_record.page_count,
            chunk_count=len(chunk_records),
            indexed_chunk_count=indexed_chunk_count,
        )

    def persist_embedded(self, *, document_id: str) -> tuple[int, str, int]:
        """Persist an already-ingested document into the embedded BM25 store."""

        return self._embedded_store_persistence.persist(document_id=document_id)

    def research(
        self,
        prompt: str,
        *,
        session_id: str = "default",
        mode: RetrievalMode = "hybrid",
        reasoning_effort: str = "medium",
        review_enabled: bool = False,
    ) -> ResearchResult:
        """Run the retrieval phase."""

        self._ensure_openai_key()

        request = RagChatRequest(
            prompt=prompt,
            retrieval_mode=mode,
            reasoning_effort=reasoning_effort,  # type: ignore[arg-type]
            review_enabled=review_enabled,
        )

        def _factory() -> Any:
            return self._orchestrator.collect_evidence(session_id=session_id, request=request)

        retrieval, events = _run_awaitable(_factory)
        return ResearchResult(
            session_id=session_id,
            prompt=prompt,
            mode=mode,
            retrieval=retrieval,
            events=list(events),
        )

    def review(self, research: ResearchResult) -> ReviewResult:
        """Summarize the judge/citation review outcome for a research run."""

        last_review: ReviewEvent | None = None
        iterations = 0
        for event in research.events:
            if isinstance(event, ReviewEvent):
                last_review = event
                iterations += 1

        verdict: ReviewVerdict
        feedback: str | None
        if last_review is None:
            verdict = "unknown"
            feedback = None
        else:
            verdict = last_review.verdict
            feedback = last_review.feedback

        citation_validation = self._citation_validator.validate(research.citations)
        return ReviewResult(
            verdict=verdict,
            iterations=iterations,
            feedback=feedback,
            citation_ok=citation_validation.ok,
            citation_issues=list(citation_validation.issues),
        )

    def synthesize(
        self,
        prompt: str,
        research: ResearchResult,
        *,
        reasoning_effort: str = "medium",
    ) -> SynthesisResult:
        """Run the synthesis phase to generate a final answer from evidence."""

        self._ensure_openai_key()

        async def _run() -> str:
            parts: list[str] = []
            async for token in self._orchestrator.stream_synthesis(
                prompt=prompt,
                retrieval=research.retrieval,
                reasoning_effort=reasoning_effort,  # type: ignore[arg-type]
            ):
                parts.append(token)
            return "".join(parts)

        def _factory() -> Any:
            return _run()

        answer = str(_run_awaitable(_factory))
        return SynthesisResult(
            session_id=research.session_id,
            prompt=prompt,
            mode=research.mode,
            answer=answer,
            citations=list(research.citations),
            tools_used=list(research.tools_used),
        )

    def query(
        self,
        prompt: str,
        *,
        session_id: str = "default",
        mode: RetrievalMode = "hybrid",
        reasoning_effort: str = "medium",
        review_enabled: bool = False,
    ) -> QueryResult:
        """Convenience wrapper: research -> optional review -> synthesize."""

        research = self.research(
            prompt,
            session_id=session_id,
            mode=mode,
            reasoning_effort=reasoning_effort,
            review_enabled=review_enabled,
        )
        review = self.review(research)
        synthesis = self.synthesize(prompt, research, reasoning_effort=reasoning_effort)

        self._session_memory.append_turn(
            session_id=session_id,
            role="assistant",
            content=synthesis.answer,
            mode=mode,
            citations=synthesis.citations,
            tools_used=synthesis.tools_used,
        )

        return QueryResult(
            session_id=session_id,
            prompt=prompt,
            mode=mode,
            answer=synthesis.answer,
            citations=synthesis.citations,
            tools_used=synthesis.tools_used,
            review=review,
        )

    def list_documents(self) -> list[dict[str, Any]]:
        """Return lightweight metadata for documents in the document store."""

        return [
            {
                "document_id": doc.document_id,
                "filename": doc.filename,
                "page_count": doc.page_count,
            }
            for doc in self._document_store.list_documents()
        ]
