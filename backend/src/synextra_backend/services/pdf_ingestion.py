"""Compatibility wrapper for PDF ingestion helpers."""

from synextra.services.pdf_ingestion import (
    PdfEncryptedError,
    PdfIngestionError,
    PdfIngestionResult,
    PdfTextBlock,
    extract_pdf_blocks,
    sha256_hex,
)

__all__ = [
    "PdfEncryptedError",
    "PdfIngestionError",
    "PdfIngestionResult",
    "PdfTextBlock",
    "extract_pdf_blocks",
    "sha256_hex",
]
