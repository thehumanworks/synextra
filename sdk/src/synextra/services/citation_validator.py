from __future__ import annotations

from dataclasses import dataclass

from synextra.schemas.rag_chat import RagCitation


@dataclass(frozen=True)
class CitationValidationResult:
    ok: bool
    issues: list[str]


class CitationValidator:
    """Lightweight validation for citation payloads.

    The goal is not perfect attribution, but to prevent obviously broken
    references from reaching the client.
    """

    def validate(self, citations: list[RagCitation]) -> CitationValidationResult:
        issues: list[str] = []
        for idx, citation in enumerate(citations):
            if not citation.document_id:
                issues.append(f"citation[{idx}] missing document_id")
            if not citation.chunk_id:
                issues.append(f"citation[{idx}] missing chunk_id")
            if not citation.supporting_quote.strip():
                issues.append(f"citation[{idx}] missing supporting_quote")
            if not citation.source_tool:
                issues.append(f"citation[{idx}] missing source_tool")
        return CitationValidationResult(ok=not issues, issues=issues)
