from __future__ import annotations

from pathlib import Path

from synextra_backend.services.pdf_ingestion import extract_pdf_blocks


def test_extract_pdf_blocks_reads_fixture() -> None:
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "1706.03762v7.pdf"
    data = fixture.read_bytes()

    result = extract_pdf_blocks(data)

    assert result.page_count > 0
    assert result.checksum_sha256
    assert len(result.blocks) > 0

    sample = result.blocks[0]
    assert sample.page_number >= 0
    assert sample.block_no >= 0
    assert len(sample.bounding_box) == 4
    assert sample.text
