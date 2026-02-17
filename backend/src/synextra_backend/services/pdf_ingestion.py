from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import pymupdf


class PdfIngestionError(RuntimeError):
    """Base exception for PDF ingestion failures."""


class PdfEncryptedError(PdfIngestionError):
    """Raised when an uploaded PDF is encrypted or requires a password."""


@dataclass(frozen=True)
class PdfTextBlock:
    page_number: int
    block_no: int
    bounding_box: list[float]
    text: str


@dataclass(frozen=True)
class PdfIngestionResult:
    page_count: int
    checksum_sha256: str
    blocks: list[PdfTextBlock]


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _open_pdf(pdf_bytes: bytes) -> Any:
    # PyMuPDF typing is partial.
    pymupdf_module: Any = pymupdf
    return pymupdf_module.open(stream=pdf_bytes, filetype="pdf")


def extract_pdf_blocks(pdf_bytes: bytes, *, sort: bool = True) -> PdfIngestionResult:
    """Extract text blocks from a PDF.

    The block geometry is preserved to support downstream citations.

    Notes
    -----
    * Pages are 0-based.
    * Blocks are sorted using PyMuPDF's ordering when ``sort=True``.
    * Non-text blocks are ignored.
    """

    checksum = sha256_hex(pdf_bytes)

    try:
        with _open_pdf(pdf_bytes) as doc:
            # Both flags are present across PyMuPDF versions.
            if getattr(doc, "is_encrypted", False) or getattr(doc, "needs_pass", False):
                raise PdfEncryptedError("PDF is encrypted or requires a password")

            blocks: list[PdfTextBlock] = []
            for page in doc:
                page_number = int(getattr(page, "number", 0))
                for x0, y0, x1, y1, text, block_no, block_type in page.get_text(
                    "blocks", sort=sort
                ):
                    # Text blocks use type 0.
                    if block_type != 0:
                        continue

                    cleaned = " ".join(str(text).split())
                    if not cleaned:
                        continue

                    blocks.append(
                        PdfTextBlock(
                            page_number=page_number,
                            block_no=int(block_no),
                            bounding_box=[float(x0), float(y0), float(x1), float(y1)],
                            text=cleaned,
                        )
                    )

            return PdfIngestionResult(
                page_count=int(getattr(doc, "page_count", len(doc))),
                checksum_sha256=checksum,
                blocks=blocks,
            )
    except PdfIngestionError:
        raise
    except Exception as exc:  # pragma: no cover
        raise PdfIngestionError("Failed to parse PDF") from exc
