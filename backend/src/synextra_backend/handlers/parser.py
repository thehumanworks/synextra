from __future__ import annotations

import json
import pathlib

import pymupdf


def extract_pdf_text(pdf_path: str | pathlib.Path, *, sort: bool = True) -> str:
    pdf_path = pathlib.Path(pdf_path)

    with pymupdf.open(pdf_path) as doc:
        pages = []
        for page in doc:
            pages.append(page.get_text("text", sort=sort))
        return "\f".join(pages)


def extract_blocks(pdf_path: str | pathlib.Path, *, sort: bool = True):
    pdf_path = pathlib.Path(pdf_path)

    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            for x0, y0, x1, y1, text, block_no, block_type in page.get_text("blocks", sort=sort):
                # pymupdf defines a text block as type "0"
                # ignore all other blocks
                if block_type != 0:
                    continue

                cleaned = " ".join(text.split())
                if not cleaned:
                    continue

                yield {
                    "page": page.number,  # 0-based
                    "bounding_box": [x0, y0, x1, y1],  # PDF coordinates
                    "block_no": block_no,
                    "text": cleaned,
                }


pdf = "/content/1706.03762v7.pdf"
out = "/content/attention.txt"
out_json = "/content/attention.jsonl"
# text = extract_pdf_text(pdf, sort=True)
# pathlib.Path(out).write_text(text, encoding="utf-8")
# print(f"Wrote: {out}")
blocks = list(extract_blocks(pdf))
pathlib.Path(out_json).write_text(json.dumps(blocks), encoding="utf-8")
print(f"Wrote: {out_json}")
