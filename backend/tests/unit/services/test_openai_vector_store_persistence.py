from __future__ import annotations

import types
from typing import Any

import pytest

from synextra_backend.repositories.rag_document_repository import (
    ChunkRecord,
    InMemoryRagDocumentRepository,
)
from synextra_backend.services.openai_vector_store_persistence import (
    OpenAIVectorStorePersistence,
)


def _seed_repository(
    *,
    document_id: str = "doc-hash-1",
) -> tuple[InMemoryRagDocumentRepository, str]:
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
                token_count=8,
                citation_span="p1",
                text="chunk zero text",
                bounding_box=[0.0, 0.0, 1.0, 1.0],
            ),
            ChunkRecord(
                chunk_id=f"{document_id}::1::1",
                document_id=document_id,
                page_number=1,
                chunk_index=1,
                token_count=9,
                citation_span="p1",
                text="chunk one text",
                bounding_box=[0.0, 0.0, 1.0, 1.0],
            ),
        ],
    )
    return repository, document_id


def test_persist_is_noop_when_signature_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    repository, document_id = _seed_repository()
    persistence = OpenAIVectorStorePersistence(repository=repository)
    signature = persistence._signature_for_chunks(
        [chunk.chunk_id for chunk in repository.list_chunks(document_id)]
    )
    repository.mark_vector_store_persisted(
        document_id=document_id,
        vector_store_id="vs_existing",
        file_ids=["file_existing"],
        signature=signature,
    )

    class _UnexpectedOpenAI:
        def __init__(self, *, api_key: str) -> None:
            raise AssertionError(f"OpenAI should not be called, api_key={api_key}")

    monkeypatch.setattr(
        "synextra_backend.services.openai_vector_store_persistence.OpenAI",
        _UnexpectedOpenAI,
    )

    _duration_ms, persisted_signature, vector_store_id, file_ids = persistence.persist(
        document_id=document_id
    )

    assert persisted_signature == signature
    assert vector_store_id == "vs_existing"
    assert file_ids == ["file_existing"]


def test_persist_uses_create_then_poll_and_idempotency_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, document_id = _seed_repository(document_id="doc-hash-2")
    persistence = OpenAIVectorStorePersistence(repository=repository, max_parallel_uploads=4)
    captured: dict[str, Any] = {}

    class _FakeFiles:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def create(
            self,
            *,
            file: Any,
            purpose: str,
            extra_headers: dict[str, str] | None = None,
        ) -> Any:
            self.calls.append(
                {
                    "filename": getattr(file, "name", ""),
                    "body": file.read().decode("utf-8"),
                    "purpose": purpose,
                    "extra_headers": extra_headers,
                }
            )
            return types.SimpleNamespace(id=f"file_{len(self.calls)}")

    class _FakeFileBatches:
        def __init__(self) -> None:
            self.create_calls: list[dict[str, Any]] = []
            self.poll_calls: list[dict[str, Any]] = []

        def create(
            self,
            *,
            vector_store_id: str,
            files: list[dict[str, object]],
            extra_headers: dict[str, str] | None = None,
        ) -> Any:
            self.create_calls.append(
                {
                    "vector_store_id": vector_store_id,
                    "files": files,
                    "extra_headers": extra_headers,
                }
            )
            return types.SimpleNamespace(id="batch_123")

        def poll(
            self,
            batch_id: str,
            *,
            vector_store_id: str,
            poll_interval_ms: int | None = None,
        ) -> Any:
            self.poll_calls.append(
                {
                    "batch_id": batch_id,
                    "vector_store_id": vector_store_id,
                    "poll_interval_ms": poll_interval_ms,
                }
            )
            return types.SimpleNamespace(id=batch_id)

    class _FakeVectorStores:
        def __init__(self) -> None:
            self.create_calls: list[dict[str, Any]] = []
            self.file_batches = _FakeFileBatches()

        def create(
            self,
            *,
            name: str,
            extra_headers: dict[str, str] | None = None,
        ) -> Any:
            self.create_calls.append({"name": name, "extra_headers": extra_headers})
            return types.SimpleNamespace(id="vs_new")

    class _FakeClient:
        def __init__(self) -> None:
            self.files = _FakeFiles()
            self.vector_stores = _FakeVectorStores()

    fake_client = _FakeClient()

    def _fake_openai(*, api_key: str) -> _FakeClient:
        captured["api_key"] = api_key
        return fake_client

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "synextra_backend.services.openai_vector_store_persistence.OpenAI",
        _fake_openai,
    )

    _duration_ms, signature, vector_store_id, file_ids = persistence.persist(
        document_id=document_id
    )

    assert captured["api_key"] == "test-key"
    assert vector_store_id == "vs_new"
    assert file_ids == ["file_1", "file_2"]
    assert signature

    assert len(fake_client.vector_stores.create_calls) == 1
    vector_create_headers = fake_client.vector_stores.create_calls[0]["extra_headers"]
    assert vector_create_headers is not None
    assert "Idempotency-Key" in vector_create_headers

    assert len(fake_client.files.calls) == 2
    for call in fake_client.files.calls:
        assert call["purpose"] == "assistants"
        assert call["body"]
        assert call["filename"].startswith(f"{document_id}-")
        assert call["extra_headers"] is not None
        assert "Idempotency-Key" in call["extra_headers"]

    assert len(fake_client.vector_stores.file_batches.create_calls) == 1
    batch_create_call = fake_client.vector_stores.file_batches.create_calls[0]
    assert batch_create_call["vector_store_id"] == "vs_new"
    assert len(batch_create_call["files"]) == 2
    assert batch_create_call["extra_headers"] is not None
    assert "Idempotency-Key" in batch_create_call["extra_headers"]

    assert fake_client.vector_stores.file_batches.poll_calls == [
        {
            "batch_id": "batch_123",
            "vector_store_id": "vs_new",
            "poll_interval_ms": None,
        }
    ]

    persisted = repository.get_vector_store_persistence(document_id)
    assert persisted is not None
    assert persisted.signature == signature
    assert persisted.vector_store_id == "vs_new"
    assert persisted.file_ids == ["file_1", "file_2"]


def test_try_acquire_inflight_is_idempotent_for_same_document() -> None:
    repository, document_id = _seed_repository(document_id="doc-hash-3")
    persistence = OpenAIVectorStorePersistence(repository=repository)

    assert persistence.try_acquire_inflight(document_id=document_id) is True
    assert persistence.is_inflight(document_id=document_id) is True
    assert persistence.try_acquire_inflight(document_id=document_id) is False

    persistence.release_inflight(document_id=document_id)
    assert persistence.is_inflight(document_id=document_id) is False

    assert persistence.try_acquire_inflight(document_id=document_id) is True
    persistence.release_inflight(document_id=document_id)


def test_persist_in_background_releases_inflight_when_persist_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, document_id = _seed_repository(document_id="doc-hash-4")
    persistence = OpenAIVectorStorePersistence(repository=repository)
    assert persistence.try_acquire_inflight(document_id=document_id) is True

    def _boom(*, document_id: str) -> tuple[int, str, str, list[str]]:
        raise RuntimeError(f"boom-{document_id}")

    monkeypatch.setattr(persistence, "persist", _boom)

    persistence.persist_in_background(document_id=document_id)

    assert persistence.try_acquire_inflight(document_id=document_id) is True
    persistence.release_inflight(document_id=document_id)


def test_inflight_entries_expire_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    repository, document_id = _seed_repository(document_id="doc-hash-ttl")
    persistence = OpenAIVectorStorePersistence(
        repository=repository,
        inflight_ttl_seconds=2,
    )
    current_time = {"value": 100.0}

    def _fake_monotonic() -> float:
        return current_time["value"]

    monkeypatch.setattr(
        "synextra_backend.services.openai_vector_store_persistence.time.monotonic",
        _fake_monotonic,
    )

    assert persistence.try_acquire_inflight(document_id=document_id) is True
    assert persistence.is_inflight(document_id=document_id) is True

    current_time["value"] = 103.5
    assert persistence.is_inflight(document_id=document_id) is False
    assert persistence.try_acquire_inflight(document_id=document_id) is True
    persistence.release_inflight(document_id=document_id)
