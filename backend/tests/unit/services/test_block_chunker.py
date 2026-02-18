from __future__ import annotations

from synextra_backend.services.block_chunker import chunk_pdf_blocks
from synextra_backend.services.pdf_ingestion import PdfTextBlock


def _block(page: int, block_no: int, text: str) -> PdfTextBlock:
    return PdfTextBlock(
        page_number=page,
        block_no=block_no,
        bounding_box=[0.0, float(block_no), 10.0, float(block_no + 1)],
        text=text,
    )


def test_chunker_splits_and_overlaps_blocks() -> None:
    blocks = [
        _block(0, 0, "Sentence one. Sentence two. Sentence three."),
        _block(0, 1, "Sentence four. Sentence five. Sentence six."),
        _block(0, 2, "Sentence seven. Sentence eight. Sentence nine."),
    ]

    # token_target must leave room for overlap + at least one new segment.
    # With cl100k_base each block is ~9 tokens, so target=20 allows
    # overlap (9 tokens) + next segment (9 tokens) = 18 ≤ 20.
    chunks = chunk_pdf_blocks(
        document_id="doc",
        blocks=blocks,
        token_target=20,
        overlap_tokens=4,
        preview_char_limit=120,
    )

    assert len(chunks) >= 2
    assert all(chunk.token_count <= 20 for chunk in chunks)

    # Overlap should repeat at least one sentence.
    assert chunks[0].text.split(". ")[-1].split(".")[0] in chunks[1].text


def test_chunk_ids_are_deterministic() -> None:
    blocks = [_block(0, 0, "Alpha beta gamma."), _block(0, 1, "Delta epsilon zeta.")]

    first = chunk_pdf_blocks(document_id="doc", blocks=blocks, token_target=8, overlap_tokens=2)
    second = chunk_pdf_blocks(document_id="doc", blocks=blocks, token_target=8, overlap_tokens=2)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
