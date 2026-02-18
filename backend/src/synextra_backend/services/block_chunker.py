"""Compatibility wrapper for text chunking helpers."""

from synextra.services.block_chunker import ChunkedText, chunk_pdf_blocks, chunk_text_pages

__all__ = ["ChunkedText", "chunk_pdf_blocks", "chunk_text_pages"]
