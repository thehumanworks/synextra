"""Compatibility wrapper for in-memory document store helpers."""

from synextra.services.document_store import (
    DocumentInfo,
    DocumentStore,
    PageText,
    _format_numbered_lines,
    build_page_texts_from_blocks,
    extract_page_texts,
)

__all__ = [
    "DocumentInfo",
    "DocumentStore",
    "PageText",
    "_format_numbered_lines",
    "build_page_texts_from_blocks",
    "extract_page_texts",
]
