from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from synextra_backend.services.pdf_ingestion import PdfTextBlock


@dataclass(frozen=True)
class ChunkedText:
    chunk_id: str
    page_number: int
    chunk_index: int
    token_count: int
    citation_span: str
    preview_text: str
    bounding_box: list[float]
    text: str


class _Tokenizer:
    def __init__(self) -> None:
        self._encoding = None
        try:
            import tiktoken  # type: ignore

            self._encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:  # pragma: no cover
            self._encoding = None

    def encode(self, text: str) -> list[int] | list[str]:
        if self._encoding is None:
            return [token for token in text.split() if token]
        return list(self._encoding.encode(text))

    def decode(self, tokens: list[int] | list[str]) -> str:
        if self._encoding is None:
            return " ".join(str(token) for token in tokens)
        return str(self._encoding.decode(tokens))


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class _BlockSegment:
    page_number: int
    block_no: int
    segment_index: int
    bounding_box: list[float]
    text: str
    token_count: int


def _sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _union_bbox(boxes: list[list[float]]) -> list[float]:
    x0 = min(box[0] for box in boxes)
    y0 = min(box[1] for box in boxes)
    x1 = max(box[2] for box in boxes)
    y1 = max(box[3] for box in boxes)
    return [float(x0), float(y0), float(x1), float(y1)]


def _split_oversized_block(
    block: PdfTextBlock, *, tokenizer: _Tokenizer, token_target: int
) -> list[_BlockSegment]:
    tokens = tokenizer.encode(block.text)
    if len(tokens) <= token_target:
        return [
            _BlockSegment(
                page_number=block.page_number,
                block_no=block.block_no,
                segment_index=0,
                bounding_box=block.bounding_box,
                text=block.text,
                token_count=len(tokens),
            )
        ]

    # Try sentence-first splitting.
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(block.text) if s.strip()]
    if not sentences:
        sentences = [block.text]

    segments: list[_BlockSegment] = []
    current: list[str] = []
    current_tokens: int = 0
    segment_index = 0

    def flush() -> None:
        nonlocal segment_index, current, current_tokens
        if not current:
            return
        text = " ".join(current).strip()
        if not text:
            return
        segments.append(
            _BlockSegment(
                page_number=block.page_number,
                block_no=block.block_no,
                segment_index=segment_index,
                bounding_box=block.bounding_box,
                text=text,
                token_count=current_tokens,
            )
        )
        segment_index += 1
        current = []
        current_tokens = 0

    for sentence in sentences:
        sentence_tokens = tokenizer.encode(sentence)
        if len(sentence_tokens) > token_target:
            # Hard split overly long sentences.
            flush()
            for offset in range(0, len(sentence_tokens), token_target):
                chunk_tokens = sentence_tokens[offset : offset + token_target]
                text = tokenizer.decode(chunk_tokens).strip()
                if not text:
                    continue
                segments.append(
                    _BlockSegment(
                        page_number=block.page_number,
                        block_no=block.block_no,
                        segment_index=segment_index,
                        bounding_box=block.bounding_box,
                        text=text,
                        token_count=len(chunk_tokens),
                    )
                )
                segment_index += 1
            continue

        if current_tokens + len(sentence_tokens) > token_target and current:
            flush()

        current.append(sentence)
        current_tokens += len(sentence_tokens)

    flush()
    return segments


def chunk_pdf_blocks(
    *,
    document_id: str,
    blocks: list[PdfTextBlock],
    token_target: int = 700,
    overlap_tokens: int = 120,
    preview_char_limit: int = 240,
) -> list[ChunkedText]:
    """Chunk PDF blocks into retrieval-friendly passages.

    Chunks are created per-page with deterministic ordering. Oversized blocks are
    split by sentence boundaries first.

    Parameters
    ----------
    document_id:
        Stable identifier used to derive chunk ids.
    blocks:
        Blocks extracted from :func:`synextra_backend.services.pdf_ingestion.extract_pdf_blocks`.
    token_target:
        Maximum tokens per chunk.
    overlap_tokens:
        Target tokens to overlap between consecutive chunks.
    """

    tokenizer = _Tokenizer()

    blocks_by_page: dict[int, list[PdfTextBlock]] = {}
    for block in blocks:
        blocks_by_page.setdefault(block.page_number, []).append(block)

    chunks: list[ChunkedText] = []
    chunk_index = 0

    for page_number in sorted(blocks_by_page.keys()):
        page_blocks = blocks_by_page[page_number]
        # Sort by vertical position then horizontal position then block number.
        page_blocks.sort(
            key=lambda b: (
                float(b.bounding_box[1]),
                float(b.bounding_box[0]),
                int(b.block_no),
            )
        )

        segments: list[_BlockSegment] = []
        for block in page_blocks:
            segments.extend(
                _split_oversized_block(block, tokenizer=tokenizer, token_target=token_target)
            )

        current_segments: list[_BlockSegment] = []
        current_tokens = 0

        def finalize_current() -> None:
            nonlocal chunk_index, current_segments, current_tokens
            if not current_segments:
                return

            text = "\n".join(seg.text for seg in current_segments).strip()
            if not text:
                current_segments = []
                current_tokens = 0
                return

            start_block = min(seg.block_no for seg in current_segments)
            end_block = max(seg.block_no for seg in current_segments)
            citation_span = f"p{page_number}:b{start_block}-{end_block}"
            bbox = _union_bbox([seg.bounding_box for seg in current_segments])
            preview_text = text[:preview_char_limit].rstrip()
            if len(text) > preview_char_limit:
                preview_text = preview_text + "…"

            chunk_id = _sha256_hex(f"{document_id}:{page_number}:{chunk_index}:{text}")

            chunks.append(
                ChunkedText(
                    chunk_id=chunk_id,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    token_count=current_tokens,
                    citation_span=citation_span,
                    preview_text=preview_text,
                    bounding_box=bbox,
                    text=text,
                )
            )
            chunk_index += 1

            # Build overlap for next chunk.
            overlap: list[_BlockSegment] = []
            overlap_token_count = 0
            for seg in reversed(current_segments):
                overlap.insert(0, seg)
                overlap_token_count += seg.token_count
                if overlap_token_count >= overlap_tokens:
                    break

            current_segments = overlap
            current_tokens = sum(seg.token_count for seg in current_segments)

        for seg in segments:
            if current_segments and current_tokens + seg.token_count > token_target:
                finalize_current()

            # If overlap alone leaves insufficient room for the next segment,
            # drop the overlap to keep chunks within token_target.
            if current_segments and current_tokens + seg.token_count > token_target:
                current_segments = []
                current_tokens = 0

            current_segments.append(seg)
            current_tokens += seg.token_count

        finalize_current()

        # Avoid carrying overlap across pages.
        current_segments = []
        current_tokens = 0

    return chunks
