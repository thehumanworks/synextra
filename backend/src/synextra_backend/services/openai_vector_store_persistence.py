from __future__ import annotations

import hashlib
import os
import time
from io import BytesIO

from openai import OpenAI

from synextra_backend.repositories.rag_document_repository import RagDocumentRepository


class OpenAIVectorStorePersistence:
    """Persist chunk files to an OpenAI vector store."""

    def __init__(
        self,
        *,
        repository: RagDocumentRepository,
        vector_store_name_prefix: str = "synextra",
    ) -> None:
        self._repository = repository
        self._vector_store_name_prefix = vector_store_name_prefix

    @staticmethod
    def _signature_for_chunks(chunk_ids: list[str]) -> str:
        joined = "|".join(chunk_ids)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def persist(self, *, document_id: str) -> tuple[int, str, str, list[str]]:
        """Persist a document into an OpenAI vector store.

        Returns
        -------
        duration_ms, signature, vector_store_id, file_ids
        """

        start = time.perf_counter()
        chunks = self._repository.list_chunks(document_id)
        signature = self._signature_for_chunks([chunk.chunk_id for chunk in chunks])

        existing = self._repository.get_vector_store_persistence(document_id)
        if existing and existing.signature == signature:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return duration_ms, signature, existing.vector_store_id, list(existing.file_ids)

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        vector_store = client.vector_stores.create(
            name=f"{self._vector_store_name_prefix}-{document_id}",
        )
        vector_store_id = str(vector_store.id)

        file_ids: list[str] = []
        file_objects: list[dict[str, object]] = []

        for chunk in chunks:
            content = chunk.text
            # Store each chunk as its own plain-text file so attributes can map
            # directly back to a chunk_id + page.
            handle = BytesIO(content.encode("utf-8"))
            handle.name = f"{document_id}-{chunk.chunk_index}.txt"  # type: ignore[attr-defined]
            uploaded = client.files.create(file=handle, purpose="assistants")
            file_id = str(uploaded.id)
            file_ids.append(file_id)
            file_objects.append(
                {
                    "file_id": file_id,
                    "attributes": {
                        "document_id": chunk.document_id,
                        "page_number": int(chunk.page_number),
                        "chunk_id": chunk.chunk_id,
                    },
                }
            )

        client.vector_stores.file_batches.create_and_poll(
            vector_store_id=vector_store_id,
            files=file_objects,
        )

        self._repository.mark_vector_store_persisted(
            document_id=document_id,
            vector_store_id=vector_store_id,
            file_ids=file_ids,
            signature=signature,
        )

        duration_ms = int((time.perf_counter() - start) * 1000)
        return duration_ms, signature, vector_store_id, file_ids
