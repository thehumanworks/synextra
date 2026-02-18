from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RagPersistenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    store: Literal["embedded"]
    status: Literal["ok"]
    indexed_chunk_count: int | None = Field(
        default=None,
        description="Number of chunks indexed in embedded store, when applicable",
    )
    duration_ms: int = Field(..., ge=0)
