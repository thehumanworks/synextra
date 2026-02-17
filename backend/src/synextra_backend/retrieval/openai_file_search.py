from __future__ import annotations

import os

from synextra_backend.retrieval.types import EvidenceChunk


class OpenAIFileSearch:
    """Vector-store semantic search using OpenAI's Retrieval API."""

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("OpenAI SDK is not installed") from exc

        self._client = OpenAI()

    def search(
        self,
        *,
        vector_store_ids: list[str],
        query: str,
        top_k: int = 6,
    ) -> list[EvidenceChunk]:
        """Search a set of vector stores for relevant content."""

        if not vector_store_ids:
            return []

        evidence: list[EvidenceChunk] = []
        for vector_store_id in vector_store_ids:
            results = self._client.vector_stores.search(
                vector_store_id=vector_store_id,
                query=query,
                max_num_results=max(1, top_k),
            )

            for item in getattr(results, "data", []):
                score = float(getattr(item, "score", 0.0))
                attributes = getattr(item, "attributes", {}) or {}

                document_id = str(attributes.get("document_id") or "")
                chunk_id = str(attributes.get("chunk_id") or getattr(item, "file_id", ""))
                page_number = attributes.get("page_number")
                if page_number is not None:
                    try:
                        page_number = int(page_number)
                    except Exception:
                        page_number = None

                # Prefer the first text content chunk.
                content_segments = getattr(item, "content", []) or []
                text = ""
                for segment in content_segments:
                    segment_text = None
                    if isinstance(segment, dict):
                        segment_text = segment.get("text")
                    else:
                        segment_text = getattr(segment, "text", None)
                    if segment_text:
                        text = str(segment_text)
                        break

                evidence.append(
                    EvidenceChunk(
                        document_id=document_id,
                        chunk_id=chunk_id,
                        page_number=page_number,
                        text=text,
                        score=score,
                        source_tool="openai_vector_store_search",
                    )
                )

        evidence.sort(key=lambda chunk: (-chunk.score, chunk.chunk_id))
        return evidence[: max(1, top_k)]
