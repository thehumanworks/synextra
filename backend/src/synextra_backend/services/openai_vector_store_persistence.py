from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from typing import Any, cast

from openai import OpenAI

from synextra_backend.repositories.rag_document_repository import (
    ChunkRecord,
    RagDocumentRepository,
    VectorStorePersistenceRecord,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VectorStoreInspection:
    signature: str
    existing: VectorStorePersistenceRecord | None


class OpenAIVectorStorePersistence:
    """Persist chunk files to an OpenAI vector store."""

    def __init__(
        self,
        *,
        repository: RagDocumentRepository,
        vector_store_name_prefix: str = "synextra",
        max_parallel_uploads: int = 6,
        inflight_ttl_seconds: int = 900,
    ) -> None:
        self._repository = repository
        self._vector_store_name_prefix = vector_store_name_prefix
        self._max_parallel_uploads = max(1, max_parallel_uploads)
        self._inflight_ttl_seconds = max(1, inflight_ttl_seconds)
        self._inflight_lock = threading.RLock()
        self._inflight_documents: set[str] = set()
        self._inflight_started_at: dict[str, float] = {}

    @staticmethod
    def _signature_for_chunks(chunk_ids: list[str]) -> str:
        joined = "|".join(chunk_ids)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    @staticmethod
    def _idempotency_key(*parts: str) -> str:
        raw = "|".join(parts)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"synextra-{digest}"

    def inspect(self, *, document_id: str) -> VectorStoreInspection:
        chunks = self._repository.list_chunks(document_id)
        signature = self._signature_for_chunks([chunk.chunk_id for chunk in chunks])
        existing = self._repository.get_vector_store_persistence(document_id)
        if existing and existing.signature == signature:
            return VectorStoreInspection(signature=signature, existing=existing)
        return VectorStoreInspection(signature=signature, existing=None)

    def try_acquire_inflight(self, *, document_id: str) -> bool:
        with self._inflight_lock:
            now = time.monotonic()
            self._expire_stale_inflight_locked(document_id=document_id, now=now)
            if document_id in self._inflight_documents:
                return False
            self._inflight_documents.add(document_id)
            self._inflight_started_at[document_id] = now
            return True

    def release_inflight(self, *, document_id: str) -> None:
        with self._inflight_lock:
            self._inflight_documents.discard(document_id)
            self._inflight_started_at.pop(document_id, None)

    def is_inflight(self, *, document_id: str) -> bool:
        with self._inflight_lock:
            self._expire_stale_inflight_locked(document_id=document_id, now=time.monotonic())
            return document_id in self._inflight_documents

    def _expire_stale_inflight_locked(self, *, document_id: str, now: float) -> None:
        started_at = self._inflight_started_at.get(document_id)
        if started_at is None:
            return
        if now - started_at <= self._inflight_ttl_seconds:
            return
        self._inflight_documents.discard(document_id)
        self._inflight_started_at.pop(document_id, None)

    def persist_in_background(self, *, document_id: str) -> None:
        try:
            self.persist(document_id=document_id)
        except Exception:
            logger.exception(
                "Background vector-store persistence failed for document_id=%s",
                document_id,
            )
        finally:
            self.release_inflight(document_id=document_id)

    def _upload_chunk(
        self,
        *,
        client: OpenAI,
        document_id: str,
        signature: str,
        chunk: ChunkRecord,
    ) -> tuple[str, dict[str, object]]:
        # Store each chunk as its own plain-text file so attributes can map
        # directly back to a chunk_id + page.
        handle = BytesIO(chunk.text.encode("utf-8"))
        handle.name = f"{document_id}-{chunk.chunk_index}.txt"
        try:
            uploaded = client.files.create(
                file=handle,
                purpose="assistants",
                extra_headers={
                    "Idempotency-Key": self._idempotency_key(
                        "files-create",
                        document_id,
                        signature,
                        chunk.chunk_id,
                    )
                },
            )
        finally:
            handle.close()

        file_id = str(uploaded.id)
        return file_id, {
            "file_id": file_id,
            "attributes": {
                "document_id": chunk.document_id,
                "page_number": int(chunk.page_number),
                "chunk_id": chunk.chunk_id,
            },
        }

    def persist(self, *, document_id: str) -> tuple[int, str, str, list[str]]:
        """Persist a document into an OpenAI vector store.

        Returns
        -------
        duration_ms, signature, vector_store_id, file_ids
        """

        start = time.perf_counter()
        chunks = self._repository.list_chunks(document_id)
        inspection = self.inspect(document_id=document_id)
        signature = inspection.signature
        existing = inspection.existing
        if existing is not None:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return duration_ms, signature, existing.vector_store_id, list(existing.file_ids)

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        vector_store = client.vector_stores.create(
            name=f"{self._vector_store_name_prefix}-{document_id}",
            extra_headers={
                "Idempotency-Key": self._idempotency_key(
                    "vector-store-create",
                    document_id,
                    signature,
                )
            },
        )
        vector_store_id = str(vector_store.id)

        file_ids: list[str] = []
        file_objects: list[dict[str, object]] = []
        if chunks:
            max_workers = min(self._max_parallel_uploads, len(chunks))
            uploaded_chunks: list[tuple[str, dict[str, object]]] = []
            if max_workers == 1:
                uploaded_chunks = [
                    self._upload_chunk(
                        client=client,
                        document_id=document_id,
                        signature=signature,
                        chunk=chunk,
                    )
                    for chunk in chunks
                ]
            else:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    uploaded_chunks = list(
                        executor.map(
                            lambda chunk: self._upload_chunk(
                                client=client,
                                document_id=document_id,
                                signature=signature,
                                chunk=chunk,
                            ),
                            chunks,
                        )
                    )

            for file_id, file_object in uploaded_chunks:
                file_ids.append(file_id)
                file_objects.append(file_object)

            batch = client.vector_stores.file_batches.create(
                vector_store_id=vector_store_id,
                files=cast(Any, file_objects),
                extra_headers={
                    "Idempotency-Key": self._idempotency_key(
                        "file-batch-create",
                        document_id,
                        signature,
                    )
                },
            )
            client.vector_stores.file_batches.poll(
                str(batch.id),
                vector_store_id=vector_store_id,
            )

        self._repository.mark_vector_store_persisted(
            document_id=document_id,
            vector_store_id=vector_store_id,
            file_ids=file_ids,
            signature=signature,
        )

        duration_ms = int((time.perf_counter() - start) * 1000)
        return duration_ms, signature, vector_store_id, file_ids
