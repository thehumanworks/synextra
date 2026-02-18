from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RagChunk(BaseModel):
    """Metadata for a chunk produced during document ingestion."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    page_number: int = Field(..., ge=0, description="0-based page index")
    chunk_index: int = Field(..., ge=0, description="0-based chunk index within the document")
    token_count: int = Field(..., ge=0)
    citation_span: str = Field(
        ..., description="Human-friendly span description used for citations"
    )
    preview_text: str = Field(..., description="Truncated preview of chunk text")
    bounding_box: list[float] = Field(
        ..., min_length=4, max_length=4, description="Union bbox for the chunk"
    )


class RagIngestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    mime_type: str
    checksum_sha256: str
    page_count: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)
    chunks: list[RagChunk]
