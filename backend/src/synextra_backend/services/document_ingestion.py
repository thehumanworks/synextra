"""Compatibility wrapper for document parsing and chunking."""

from synextra.services.document_ingestion import (
    DocumentIngestionError,
    DocumentKind,
    DocumentParseError,
    ParsedDocument,
    UnsupportedDocumentTypeError,
    detect_document_kind,
    parse_document,
)

__all__ = [
    "DocumentIngestionError",
    "DocumentKind",
    "DocumentParseError",
    "ParsedDocument",
    "UnsupportedDocumentTypeError",
    "detect_document_kind",
    "parse_document",
]
