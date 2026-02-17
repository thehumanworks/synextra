from __future__ import annotations

import hashlib
import time

from synextra_backend.repositories.rag_document_repository import RagDocumentRepository
from synextra_backend.retrieval.bm25_search import Bm25IndexStore


def _signature_for_chunks(chunk_ids: list[str]) -> str:
    joined = "|".join(chunk_ids)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class EmbeddedStorePersistence:
    """Persist chunks into the local embedded (BM25) store."""

    def __init__(self, *, repository: RagDocumentRepository, index_store: Bm25IndexStore) -> None:
        self._repository = repository
        self._index_store = index_store

    def persist(self, *, document_id: str) -> tuple[int, str, int]:
        """Persist a document into the embedded store.

        Returns
        -------
        duration_ms, signature, indexed_chunk_count
        """

        start = time.perf_counter()
        chunks = self._repository.list_chunks(document_id)
        signature = _signature_for_chunks([chunk.chunk_id for chunk in chunks])

        existing = self._repository.get_embedded_persistence(document_id)
        if existing and existing.signature == signature and self._index_store.has_document(document_id):
            duration_ms = int((time.perf_counter() - start) * 1000)
            return duration_ms, signature, existing.indexed_chunk_count

        self._index_store.upsert(document_id=document_id, chunks=chunks, signature=signature)
        record = self._repository.mark_embedded_persisted(
            document_id=document_id,
            indexed_chunk_count=len(chunks),
            signature=signature,
        )

        duration_ms = int((time.perf_counter() - start) * 1000)
        return duration_ms, signature, record.indexed_chunk_count
