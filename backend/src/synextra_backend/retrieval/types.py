from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceChunk:
    document_id: str
    chunk_id: str
    page_number: int | None
    text: str
    score: float
    source_tool: str
