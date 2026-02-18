from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    filename: str
    mime_type: str
    checksum_sha256: str
    page_count: int
    created_at: datetime


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    document_id: str
    page_number: int
    chunk_index: int
    token_count: int
    citation_span: str
    text: str
    bounding_box: list[float]


@dataclass(frozen=True)
class EmbeddedPersistenceRecord:
    document_id: str
    indexed_chunk_count: int
    signature: str
    persisted_at: datetime


class RagDocumentRepository:
    """Repository interface for RAG documents and chunks."""

    def get_document(self, document_id: str) -> DocumentRecord | None:  # pragma: no cover
        raise NotImplementedError

    def get_document_by_checksum(self, checksum_sha256: str) -> DocumentRecord | None:  # pragma: no cover
        raise NotImplementedError

    def upsert_document(
        self,
        *,
        document_id: str,
        filename: str,
        mime_type: str,
        checksum_sha256: str,
        page_count: int,
    ) -> DocumentRecord:  # pragma: no cover
        raise NotImplementedError

    def replace_chunks(self, document_id: str, chunks: list[ChunkRecord]) -> None:  # pragma: no cover
        raise NotImplementedError

    def list_chunks(self, document_id: str) -> list[ChunkRecord]:  # pragma: no cover
        raise NotImplementedError

    def mark_embedded_persisted(
        self, *, document_id: str, indexed_chunk_count: int, signature: str
    ) -> EmbeddedPersistenceRecord:  # pragma: no cover
        raise NotImplementedError

    def get_embedded_persistence(
        self, document_id: str
    ) -> EmbeddedPersistenceRecord | None:  # pragma: no cover
        raise NotImplementedError

class InMemoryRagDocumentRepository(RagDocumentRepository):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._documents: dict[str, DocumentRecord] = {}
        self._documents_by_checksum: dict[str, str] = {}
        self._chunks_by_document: dict[str, list[ChunkRecord]] = {}
        self._embedded_persistence: dict[str, EmbeddedPersistenceRecord] = {}

    def get_document(self, document_id: str) -> DocumentRecord | None:
        with self._lock:
            return self._documents.get(document_id)

    def get_document_by_checksum(self, checksum_sha256: str) -> DocumentRecord | None:
        with self._lock:
            document_id = self._documents_by_checksum.get(checksum_sha256)
            if not document_id:
                return None
            return self._documents.get(document_id)

    def upsert_document(
        self,
        *,
        document_id: str,
        filename: str,
        mime_type: str,
        checksum_sha256: str,
        page_count: int,
    ) -> DocumentRecord:
        with self._lock:
            now = datetime.now(timezone.utc)
            record = DocumentRecord(
                document_id=document_id,
                filename=filename,
                mime_type=mime_type,
                checksum_sha256=checksum_sha256,
                page_count=page_count,
                created_at=now,
            )
            self._documents[document_id] = record
            self._documents_by_checksum[checksum_sha256] = document_id
            return record

    def replace_chunks(self, document_id: str, chunks: list[ChunkRecord]) -> None:
        with self._lock:
            self._chunks_by_document[document_id] = list(chunks)

    def list_chunks(self, document_id: str) -> list[ChunkRecord]:
        with self._lock:
            return list(self._chunks_by_document.get(document_id, []))

    def mark_embedded_persisted(
        self, *, document_id: str, indexed_chunk_count: int, signature: str
    ) -> EmbeddedPersistenceRecord:
        with self._lock:
            record = EmbeddedPersistenceRecord(
                document_id=document_id,
                indexed_chunk_count=indexed_chunk_count,
                signature=signature,
                persisted_at=datetime.now(timezone.utc),
            )
            self._embedded_persistence[document_id] = record
            return record

    def get_embedded_persistence(
        self, document_id: str
    ) -> EmbeddedPersistenceRecord | None:
        with self._lock:
            return self._embedded_persistence.get(document_id)
