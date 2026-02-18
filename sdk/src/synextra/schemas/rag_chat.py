from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Retrieval is currently fixed to hybrid mode.
RetrievalMode = Literal["hybrid"]
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
    reasoning_effort: ReasoningEffort = "medium"
    review_enabled: bool = False

    @model_validator(mode="before")
    @classmethod
    def _strip_legacy_retrieval_mode(cls, value: object) -> object:
        # Keep backward compatibility for clients still sending retrieval_mode.
        if isinstance(value, dict) and "retrieval_mode" in value:
            copied = dict(value)
            copied.pop("retrieval_mode", None)
            return copied
        return value


class RagChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    mode: RetrievalMode
    answer: str
    tools_used: list[str]
    citations: list[RagCitation]
    agent_events: list[RagAgentEvent] = Field(default_factory=list)
