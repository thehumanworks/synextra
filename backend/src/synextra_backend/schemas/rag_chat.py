from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RetrievalMode = Literal["embedded", "vector", "hybrid"]
ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]


class RagCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    chunk_id: str
    page_number: int | None = Field(default=None, ge=0)
    supporting_quote: str
    source_tool: str
    score: float | None = None


class RagAgentEvent(BaseModel):
    """Optional forward-compatible agent metadata."""

    model_config = ConfigDict(extra="allow")

    type: str
    timestamp: datetime | None = None


class RagChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1)
    retrieval_mode: RetrievalMode = "hybrid"
    reasoning_effort: ReasoningEffort = "medium"


class RagChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    mode: RetrievalMode
    answer: str
    tools_used: list[str]
    citations: list[RagCitation]
    agent_events: list[RagAgentEvent] = Field(default_factory=list)
