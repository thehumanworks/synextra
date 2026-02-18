from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from synextra_backend.api.rag_persistence import build_rag_persistence_router
from synextra_backend.repositories.rag_document_repository import (
    ChunkRecord,
    InMemoryRagDocumentRepository,
)


class _FakeEmbeddedPersistence:
    def persist(self, *, document_id: str) -> tuple[int, str, int]:
        return 1, f"sig-{document_id}", 1


def _repository_with_document(document_id: str = "doc-hash") -> InMemoryRagDocumentRepository:
    repository = InMemoryRagDocumentRepository()
    repository.upsert_document(
        document_id=document_id,
        filename="paper.pdf",
        mime_type="application/pdf",
        checksum_sha256=document_id,
        page_count=1,
    )
    repository.replace_chunks(
        document_id,
        [
            ChunkRecord(
                chunk_id=f"{document_id}::1::0",
                document_id=document_id,
                page_number=1,
                chunk_index=0,
                token_count=6,
                citation_span="p1",
                text="test chunk",
                bounding_box=[0.0, 0.0, 1.0, 1.0],
            )
        ],
    )
    return repository


def _build_app(
    *,
    repository: InMemoryRagDocumentRepository,
) -> FastAPI:
    app = FastAPI()
    app.state.rag_repository = repository
    app.state.embedded_store_persistence = _FakeEmbeddedPersistence()
    app.include_router(build_rag_persistence_router())
    return app


@pytest.mark.asyncio
async def test_embedded_persistence_endpoint_returns_ok() -> None:
    repository = _repository_with_document()
    app = _build_app(repository=repository)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/v1/rag/documents/doc-hash/persist/embedded")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == "doc-hash"
    assert body["store"] == "embedded"
    assert body["status"] == "ok"
    assert body["indexed_chunk_count"] == 1


@pytest.mark.asyncio
async def test_embedded_persistence_endpoint_returns_404_for_unknown_document() -> None:
    repository = InMemoryRagDocumentRepository()
    app = _build_app(repository=repository)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/v1/rag/documents/missing/persist/embedded")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "document_not_found"
