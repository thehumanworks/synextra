from __future__ import annotations

from synextra.services.document_store import (
    DocumentStore,
    PageText,
    _format_numbered_lines,
    build_page_texts_from_blocks,
)
from synextra.services.pdf_ingestion import PdfTextBlock


def test_format_numbered_lines_basic() -> None:
    lines = ["Hello", "World"]
    result = _format_numbered_lines(lines, start=1)
    assert result == "  1 | Hello\n  2 | World"


def test_format_numbered_lines_offset_start() -> None:
    lines = ["Alpha", "Beta"]
    result = _format_numbered_lines(lines, start=10)
    assert result == " 10 | Alpha\n 11 | Beta"


def test_build_page_texts_from_blocks_groups_by_page() -> None:
    blocks = [
        PdfTextBlock(page_number=0, block_no=0, bounding_box=[0, 0, 100, 20], text="First block"),
        PdfTextBlock(page_number=0, block_no=1, bounding_box=[0, 20, 100, 40], text="Second block"),
        PdfTextBlock(page_number=1, block_no=0, bounding_box=[0, 0, 100, 20], text="Page two"),
    ]
    pages = build_page_texts_from_blocks(blocks, page_count=2)

    assert len(pages) == 2
    assert pages[0].page_number == 0
    assert pages[0].lines == ["First block", "Second block"]
    assert pages[0].line_count == 2
    assert pages[1].page_number == 1
    assert pages[1].lines == ["Page two"]
    assert pages[1].line_count == 1


def test_build_page_texts_from_blocks_empty_page() -> None:
    """Pages with no blocks should still exist with zero lines."""
    blocks = [
        PdfTextBlock(
            page_number=1, block_no=0, bounding_box=[0, 0, 100, 20], text="Only on page 1"
        ),
    ]
    pages = build_page_texts_from_blocks(blocks, page_count=3)

    assert len(pages) == 3
    assert pages[0].line_count == 0
    assert pages[1].lines == ["Only on page 1"]
    assert pages[2].line_count == 0


class TestDocumentStore:
    def _store_with_doc(self) -> DocumentStore:
        store = DocumentStore()
        store.store_pages(
            document_id="doc1",
            filename="test.pdf",
            pages=[
                PageText(
                    page_number=0,
                    lines=["Line one.", "Line two.", "Line three."],
                    line_count=3,
                ),
                PageText(page_number=1, lines=["Page two line one."], line_count=1),
            ],
        )
        return store

    def test_has_document(self) -> None:
        store = self._store_with_doc()
        assert store.has_document("doc1")
        assert not store.has_document("missing")

    def test_list_documents(self) -> None:
        store = self._store_with_doc()
        docs = store.list_documents()
        assert len(docs) == 1
        assert docs[0].document_id == "doc1"
        assert docs[0].filename == "test.pdf"
        assert docs[0].page_count == 2

    def test_get_page_count(self) -> None:
        store = self._store_with_doc()
        assert store.get_page_count("doc1") == 2
        assert store.get_page_count("missing") == 0

    def test_read_full_page(self) -> None:
        store = self._store_with_doc()
        result = store.read_page("doc1", 0)
        assert result is not None
        assert "Page 0 (3 lines):" in result
        assert "1 | Line one." in result
        assert "2 | Line two." in result
        assert "3 | Line three." in result

    def test_read_page_with_line_range(self) -> None:
        store = self._store_with_doc()
        result = store.read_page("doc1", 0, start_line=2, end_line=3)
        assert result is not None
        assert "lines 2-3 of 3" in result
        assert "2 | Line two." in result
        assert "3 | Line three." in result
        assert "Line one" not in result

    def test_read_page_nonexistent_document(self) -> None:
        store = self._store_with_doc()
        assert store.read_page("missing", 0) is None

    def test_read_page_nonexistent_page(self) -> None:
        store = self._store_with_doc()
        assert store.read_page("doc1", 99) is None

    def test_read_page_out_of_range_start_line(self) -> None:
        store = self._store_with_doc()
        result = store.read_page("doc1", 0, start_line=100)
        assert result is not None
        assert "out of range" in result

    def test_read_page_clamps_end_line(self) -> None:
        store = self._store_with_doc()
        result = store.read_page("doc1", 0, start_line=2, end_line=999)
        assert result is not None
        assert "2 | Line two." in result
        assert "3 | Line three." in result
