from __future__ import annotations

from collections import defaultdict

from synextra_backend.retrieval.types import EvidenceChunk


def reciprocal_rank_fusion(
    evidence_lists: list[list[EvidenceChunk]],
    *,
    k: int = 60,
    tool_weights: dict[str, float] | None = None,
    top_k: int = 8,
) -> list[EvidenceChunk]:
    """Merge and rerank evidence using reciprocal rank fusion (RRF)."""

    weights = tool_weights or {}
    fused_scores: dict[tuple[str, str], float] = defaultdict(float)
    exemplar: dict[tuple[str, str], EvidenceChunk] = {}

    for evidence in evidence_lists:
        for rank, chunk in enumerate(evidence, start=1):
            key = (chunk.document_id, chunk.chunk_id)
            weight = float(weights.get(chunk.source_tool, 1.0))
            fused_scores[key] += weight / (k + rank)
            exemplar.setdefault(key, chunk)

    merged: list[EvidenceChunk] = []
    for key, score in fused_scores.items():
        base = exemplar[key]
        merged.append(
            EvidenceChunk(
                document_id=base.document_id,
                chunk_id=base.chunk_id,
                page_number=base.page_number,
                text=base.text,
                score=float(score),
                source_tool=base.source_tool,
            )
        )

    merged.sort(key=lambda chunk: (-chunk.score, chunk.chunk_id))
    return merged[: max(1, top_k)]
