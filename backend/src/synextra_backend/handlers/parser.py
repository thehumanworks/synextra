"""Legacy PDF parsing helpers.

This module originally contained a small script snippet used during early
experiments. The runtime snippet has been removed to avoid import-time side
effects during application startup and test collection.

The backend RAG implementation uses :mod:`synextra.services` instead.
These helpers remain as a lightweight reference.
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterator
from typing import Any

import pymupdf


def _open_pdf(pdf_path: pathlib.Path) -> Any:
    """Open a PDF with PyMuPDF.

    PyMuPDF currently ships partial typing support; use a local ``Any`` bridge
    to avoid typing false-positives.
    """

    pymupdf_module: Any = pymupdf
    return pymupdf_module.open(pdf_path)


def extract_pdf_text(pdf_path: str | pathlib.Path, *, sort: bool = True) -> str:
    """Extract full text from a PDF as page-separated text."""

    pdf_path = pathlib.Path(pdf_path)

    with _open_pdf(pdf_path) as doc:
        pages = []
        for page in doc:
            pages.append(page.get_text("text", sort=sort))
        return "\f".join(pages)


def extract_blocks(
    pdf_path: str | pathlib.Path, *, sort: bool = True
) -> Iterator[dict[str, object]]:
    """Yield normalized text blocks with bounding boxes."""

    pdf_path = pathlib.Path(pdf_path)

    with _open_pdf(pdf_path) as doc:
        for page in doc:
            for x0, y0, x1, y1, text, block_no, block_type in page.get_text("blocks", sort=sort):
                # pymupdf defines a text block as type "0"
                # ignore all other blocks
                if block_type != 0:
                    continue

                cleaned = " ".join(str(text).split())
                if not cleaned:
                    continue

                yield {
                    "page": page.number,  # 0-based
                    "bounding_box": [x0, y0, x1, y1],  # PDF coordinates
                    "block_no": block_no,
                    "text": cleaned,
                }
