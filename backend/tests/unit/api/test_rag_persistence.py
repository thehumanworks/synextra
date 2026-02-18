from __future__ import annotations

import types
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import BackgroundTasks, FastAPI
from httpx import ASGITransport, AsyncClient

from synextra_backend.api.rag_persistence import build_rag_persistence_router
from synextra_backend.repositories.rag_document_repository import (
    ChunkRecord,
    InMemoryRagDocumentRepository,
    VectorStorePersistenceRecord,
)


class _FakeEmbeddedPersistence:
    def persist(self, *, document_id: str) -> tuple[int, str, int]:
        return 1, f"sig-{document_id}", 1


class _FakeVectorPersistence:
    def __init__(
        self,
        *,
        existing: VectorStorePersistenceRecord | None,
        can_acquire: bool,
        inflight: bool = False,
    ) -> None:
        self._existing = existing
        self._can_acquire = can_acquire
        self._inflight = inflight
        self.acquire_calls = 0
        self.background_calls: list[str] = []
        self.release_calls: list[str] = []

    def inspect(self, *, document_id: str) -> Any:
        return types.SimpleNamespace(signature=f"sig-{document_id}", existing=self._existing)

    def try_acquire_inflight(self, *, document_id: str) -> bool:
        self.acquire_calls += 1
        if not self._can_acquire:
            return False
        self._inflight = True
        return True

    def persist_in_background(self, *, document_id: str) -> None:
        self.background_calls.append(document_id)
        self._inflight = False

    def release_inflight(self, *, document_id: str) -> None:
        self.release_calls.append(document_id)
        self._inflight = False

    def is_inflight(self, *, document_id: str) -> bool:
        _ = document_id
        return self._inflight


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
    vector_persistence: _FakeVectorPersistence,
) -> FastAPI:
    app = FastAPI()
    app.state.rag_repository = repository
    app.state.embedded_store_persistence = _FakeEmbeddedPersistence()
    app.state.vector_store_persistence = vector_persistence
    app.include_router(build_rag_persistence_router())
    return app


@pytest.mark.asyncio
async def test_vector_persistence_endpoint_queues_background_work() -> None:
    repository = _repository_with_document()
    vector_persistence = _FakeVectorPersistence(existing=None, can_acquire=True)
    app = _build_app(repository=repository, vector_persistence=vector_persistence)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/v1/rag/documents/doc-hash/persist/vector-store")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == "doc-hash"
    assert body["store"] == "vector-store"
    assert body["status"] == "queued"
    assert vector_persistence.acquire_calls == 1
    assert vector_persistence.background_calls == ["doc-hash"]


@pytest.mark.asyncio
async def test_vector_persistence_endpoint_is_noop_when_already_persisted() -> None:
    repository = _repository_with_document()
    existing = VectorStorePersistenceRecord(
        document_id="doc-hash",
        vector_store_id="vs_existing",
        file_ids=["file_existing"],
        signature="sig-doc-hash",
        persisted_at=datetime.now(UTC),
    )
    vector_persistence = _FakeVectorPersistence(existing=existing, can_acquire=True)
    app = _build_app(repository=repository, vector_persistence=vector_persistence)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/v1/rag/documents/doc-hash/persist/vector-store")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == "doc-hash"
    assert body["store"] == "vector-store"
    assert body["status"] == "ok"
    assert body["vector_store_id"] == "vs_existing"
    assert body["file_ids"] == ["file_existing"]
    assert vector_persistence.acquire_calls == 0
    assert vector_persistence.background_calls == []


@pytest.mark.asyncio
async def test_vector_persistence_endpoint_noops_when_job_is_already_inflight() -> None:
    repository = _repository_with_document()
    vector_persistence = _FakeVectorPersistence(existing=None, can_acquire=False)
    app = _build_app(repository=repository, vector_persistence=vector_persistence)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/v1/rag/documents/doc-hash/persist/vector-store")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert vector_persistence.acquire_calls == 1
    assert vector_persistence.background_calls == []


@pytest.mark.asyncio
async def test_vector_persistence_endpoint_returns_404_for_unknown_document() -> None:
    repository = InMemoryRagDocumentRepository()
    vector_persistence = _FakeVectorPersistence(existing=None, can_acquire=True)
    app = _build_app(repository=repository, vector_persistence=vector_persistence)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/v1/rag/documents/missing/persist/vector-store")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "document_not_found"


@pytest.mark.asyncio
async def test_vector_persistence_endpoint_releases_inflight_when_queue_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository_with_document()
    vector_persistence = _FakeVectorPersistence(existing=None, can_acquire=True)
    app = _build_app(repository=repository, vector_persistence=vector_persistence)

    def _raise_on_add_task(self: BackgroundTasks, func: Any, *args: Any, **kwargs: Any) -> None:
        _ = (self, func, args, kwargs)
        raise RuntimeError("queue-failed")

    monkeypatch.setattr(BackgroundTasks, "add_task", _raise_on_add_task)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/v1/rag/documents/doc-hash/persist/vector-store")

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "vector_store_queue_failed"
    assert vector_persistence.release_calls == ["doc-hash"]


@pytest.mark.asyncio
async def test_vector_persistence_status_endpoint_returns_ok_when_persisted() -> None:
    repository = _repository_with_document()
    existing = VectorStorePersistenceRecord(
        document_id="doc-hash",
        vector_store_id="vs_existing",
        file_ids=["file_existing"],
        signature="sig-doc-hash",
        persisted_at=datetime.now(UTC),
    )
    vector_persistence = _FakeVectorPersistence(existing=existing, can_acquire=True)
    app = _build_app(repository=repository, vector_persistence=vector_persistence)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/v1/rag/documents/doc-hash/persist/vector-store")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["vector_store_id"] == "vs_existing"


@pytest.mark.asyncio
async def test_vector_persistence_status_endpoint_returns_queued_when_inflight() -> None:
    repository = _repository_with_document()
    vector_persistence = _FakeVectorPersistence(existing=None, can_acquire=False, inflight=True)
    app = _build_app(repository=repository, vector_persistence=vector_persistence)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/v1/rag/documents/doc-hash/persist/vector-store")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"


@pytest.mark.asyncio
async def test_vector_persistence_status_endpoint_returns_not_persisted_when_idle() -> None:
    repository = _repository_with_document()
    vector_persistence = _FakeVectorPersistence(existing=None, can_acquire=False, inflight=False)
    app = _build_app(repository=repository, vector_persistence=vector_persistence)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/v1/rag/documents/doc-hash/persist/vector-store")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "vector_store_not_persisted"
