from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import pymupdf

from synextra_backend.services.pdf_ingestion import PdfTextBlock


@dataclass(frozen=True)
class PageText:
    page_number: int
    lines: list[str]
    line_count: int


@dataclass(frozen=True)
class DocumentInfo:
    document_id: str
    filename: str
    page_count: int


def extract_page_texts(pdf_bytes: bytes) -> list[PageText]:
    """Extract per-page text from a PDF, split into lines.

    Each page's text is obtained via PyMuPDF's ``get_text("text")``, which
    returns the full page content in reading order.  The result is split
    into individual lines so downstream consumers can reference them by
    1-based line number.
    """

    pymupdf_module: Any = pymupdf
    pages: list[PageText] = []

    with pymupdf_module.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            page_number = int(getattr(page, "number", 0))
            raw = page.get_text("text", sort=True)
            lines = raw.splitlines()

            # Strip trailing empty lines.
            while lines and not lines[-1].strip():
                lines.pop()

            pages.append(
                PageText(
                    page_number=page_number,
                    lines=lines,
                    line_count=len(lines),
                )
            )

    return pages


def build_page_texts_from_blocks(
    blocks: list[PdfTextBlock],
    page_count: int,
) -> list[PageText]:
    """Build per-page text from already-extracted blocks.

    This avoids a second PyMuPDF parse when blocks are already available.
    Blocks are grouped by page and joined in reading order.
    """

    blocks_by_page: dict[int, list[PdfTextBlock]] = {}
    for block in blocks:
        blocks_by_page.setdefault(block.page_number, []).append(block)

    pages: list[PageText] = []
    for page_number in range(page_count):
        page_blocks = blocks_by_page.get(page_number, [])
        page_blocks.sort(
            key=lambda b: (
                float(b.bounding_box[1]),
                float(b.bounding_box[0]),
                int(b.block_no),
            )
        )
        raw = "\n".join(b.text for b in page_blocks)
        lines = raw.splitlines()

        while lines and not lines[-1].strip():
            lines.pop()

        pages.append(
            PageText(
                page_number=page_number,
                lines=lines,
                line_count=len(lines),
            )
        )

    return pages


def _format_numbered_lines(lines: list[str], start: int = 1) -> str:
    """Format lines with right-aligned line numbers and a pipe separator.

    ``start`` is the 1-based number for the first line.
    """

    end = start + len(lines) - 1
    width = max(len(str(end)), 3)
    numbered: list[str] = []
    for i, line in enumerate(lines, start=start):
        numbered.append(f"{i:>{width}} | {line}")
    return "\n".join(numbered)


class DocumentStore:
    """Thread-safe in-memory store for page-level document text."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pages: dict[str, list[PageText]] = {}
        self._info: dict[str, DocumentInfo] = {}

    def store_pages(
        self,
        *,
        document_id: str,
        filename: str,
        pages: list[PageText],
    ) -> None:
        with self._lock:
            self._pages[document_id] = list(pages)
            self._info[document_id] = DocumentInfo(
                document_id=document_id,
                filename=filename,
                page_count=len(pages),
            )

    def has_document(self, document_id: str) -> bool:
        with self._lock:
            return document_id in self._pages

    def list_documents(self) -> list[DocumentInfo]:
        with self._lock:
            return list(self._info.values())

    def get_page_count(self, document_id: str) -> int:
        with self._lock:
            info = self._info.get(document_id)
            return info.page_count if info else 0

    def read_page(
        self,
        document_id: str,
        page_number: int,
        *,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str | None:
        """Read a page or line range, formatted with line numbers.

        Parameters
        ----------
        document_id:
            Document to read from.
        page_number:
            0-based page index.
        start_line:
            1-based inclusive start.  ``None`` means from the beginning.
        end_line:
            1-based inclusive end.  ``None`` means to the end.

        Returns ``None`` when the document or page does not exist.
        """

        with self._lock:
            pages = self._pages.get(document_id)
            if pages is None:
                return None

            page = next((p for p in pages if p.page_number == page_number), None)
            if page is None:
                return None

            lines = page.lines
            total = page.line_count

            actual_start = max(1, start_line) if start_line is not None else 1
            actual_end = min(total, end_line) if end_line is not None else total

            if actual_start > total:
                return f"Page {page_number} has {total} lines. Requested start_line {actual_start} is out of range."

            selected = lines[actual_start - 1 : actual_end]
            header = f"Page {page_number}"
            if start_line is not None or end_line is not None:
                header += f" (lines {actual_start}-{actual_end} of {total})"
            else:
                header += f" ({total} lines)"

            body = _format_numbered_lines(selected, start=actual_start)
            return f"{header}:\n{body}"
