from __future__ import annotations

from pathlib import Path

from synextra import Synextra


def test_ingest_text_document(tmp_path: Path) -> None:
    document = tmp_path / "notes.txt"
    document.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    client = Synextra(openai_api_key=None)
    result = client.ingest(document)

    assert result.document_id
    assert result.page_count >= 1
    assert result.chunk_count >= 1

    docs = client.list_documents()
    assert len(docs) == 1
    assert docs[0]["document_id"] == result.document_id
