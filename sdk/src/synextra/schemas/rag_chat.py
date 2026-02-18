from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RetrievalMode = Literal["embedded", "hybrid"]
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


class SearchEvent(BaseModel):
    """Emitted when the agent calls a search tool."""

    model_config = ConfigDict(extra="forbid")

    event: Literal["search"] = "search"
    tool: str
    query: str | None = None
    page: int | None = None
    timestamp: str


class ReasoningEvent(BaseModel):
    """Emitted when the agent produces a reasoning step."""

    model_config = ConfigDict(extra="forbid")

    event: Literal["reasoning"] = "reasoning"
    content: str
    timestamp: str


class ReviewEvent(BaseModel):
    """Emitted when the judge agent evaluates a draft answer."""

    model_config = ConfigDict(extra="forbid")

    event: Literal["review"] = "review"
    iteration: int
    verdict: Literal["approved", "rejected"]
    feedback: str | None = None
    timestamp: str


# Union type for all streaming events
StreamEvent = SearchEvent | ReasoningEvent | ReviewEvent


class RagChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1)
    retrieval_mode: RetrievalMode = "hybrid"
    reasoning_effort: ReasoningEffort = "medium"
    review_enabled: bool = False


class RagChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    mode: RetrievalMode
    answer: str
    tools_used: list[str]
    citations: list[RagCitation]
    agent_events: list[RagAgentEvent] = Field(default_factory=list)
