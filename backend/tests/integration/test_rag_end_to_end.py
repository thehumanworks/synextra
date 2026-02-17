from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rag_ingestion_persistence_and_chat(client: AsyncClient) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "1706.03762v7.pdf"
    data = fixture.read_bytes()

    ingest = await client.post(
        "/v1/rag/pdfs",
        files={"file": ("paper.pdf", data, "application/pdf")},
    )

    assert ingest.status_code == 201
    body = ingest.json()
    assert body["document_id"]
    assert body["page_count"] > 0
    assert body["chunk_count"] > 0
    assert len(body["chunks"]) == body["chunk_count"]

    document_id = body["document_id"]

    persist = await client.post(f"/v1/rag/documents/{document_id}/persist/embedded")
    assert persist.status_code == 200
    persist_body = persist.json()
    assert persist_body["store"] == "embedded"
    assert persist_body["indexed_chunk_count"] == body["chunk_count"]

    chat = await client.post(
        f"/v1/rag/sessions/test-session/messages",
        json={"prompt": "What is the Transformer model described in the paper?", "retrieval_mode": "hybrid"},
    )

    assert chat.status_code == 200
    chat_body = chat.json()
    assert chat_body["session_id"] == "test-session"
    assert chat_body["mode"] == "hybrid"
    assert isinstance(chat_body["answer"], str)
    assert isinstance(chat_body["citations"], list)

    # The embedded store should produce at least one citation for a general query.
    assert len(chat_body["citations"]) >= 1
    first = chat_body["citations"][0]
    assert first["document_id"] == document_id
    assert first["chunk_id"]
    assert first["supporting_quote"]


@pytest.mark.asyncio
async def test_ingestion_rejects_non_pdf(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/rag/pdfs",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "unsupported_media_type"
