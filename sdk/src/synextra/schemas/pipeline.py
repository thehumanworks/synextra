from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]
AgentToolType = Literal["bm25_search", "read_document", "parallel_search"]
PipelineNodeType = Literal[
    "ingest",
    "bm25_search",
    "read_document",
    "parallel_search",
    "agent",
    "output",
]


class PipelineDocumentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    page_count: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)


class PipelineEvidenceChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    chunk_id: str
    page_number: int | None = Field(default=None, ge=0)
    text: str
    score: float = 0.0
    source_tool: str


class PipelineCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    chunk_id: str
    page_number: int | None = Field(default=None, ge=0)
    supporting_quote: str
    source_tool: str
    score: float | None = None


class PipelineAgentOutputEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[PipelineCitation] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    evidence: list[PipelineEvidenceChunk] = Field(default_factory=list)
    upstream_answers: list[str] = Field(default_factory=list)


class IngestNodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Bm25SearchNodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_template: str = "{query}"
    top_k: int = Field(default=8, ge=1, le=50)
    document_ids: list[str] | None = None


class ReadDocumentNodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=0, ge=0)
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    document_id: str | None = None


class ParallelBm25SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["bm25_search"] = "bm25_search"
    query_template: str = "{query}"
    top_k: int = Field(default=8, ge=1, le=50)
    document_ids: list[str] | None = None


class ParallelReadDocumentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["read_document"] = "read_document"
    page: int = Field(..., ge=0)
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    document_id: str | None = None


PipelineParallelQuery = Annotated[
    ParallelBm25SearchQuery | ParallelReadDocumentQuery,
    Field(discriminator="type"),
]


class ParallelSearchNodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: list[PipelineParallelQuery] = Field(default_factory=list)


class AgentNodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_template: str = "{query}"
    reasoning_effort: ReasoningEffort = "medium"
    review_enabled: bool = False
    tools: list[AgentToolType] = Field(default_factory=list)


class OutputNodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestNodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["ingest"] = "ingest"
    label: str = "Ingest"
    config: IngestNodeConfig = Field(default_factory=IngestNodeConfig)


class Bm25SearchNodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["bm25_search"] = "bm25_search"
    label: str = "BM25 Search"
    config: Bm25SearchNodeConfig = Field(default_factory=Bm25SearchNodeConfig)


class ReadDocumentNodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["read_document"] = "read_document"
    label: str = "Read Document"
    config: ReadDocumentNodeConfig = Field(default_factory=ReadDocumentNodeConfig)


class ParallelSearchNodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["parallel_search"] = "parallel_search"
    label: str = "Parallel Search"
    config: ParallelSearchNodeConfig = Field(default_factory=ParallelSearchNodeConfig)


class AgentNodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["agent"] = "agent"
    label: str = "Agent"
    config: AgentNodeConfig = Field(default_factory=AgentNodeConfig)


class OutputNodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["output"] = "output"
    label: str = "Output"
    config: OutputNodeConfig = Field(default_factory=OutputNodeConfig)


PipelineNodeSpec = Annotated[
    IngestNodeSpec
    | Bm25SearchNodeSpec
    | ReadDocumentNodeSpec
    | ParallelSearchNodeSpec
    | AgentNodeSpec
    | OutputNodeSpec,
    Field(discriminator="type"),
]


class PipelineEdgeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str


class PipelineRunSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[PipelineNodeSpec]
    edges: list[PipelineEdgeSpec]
    query: str = Field(..., min_length=1)
    session_id: str | None = None


class PipelineBm25SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)
    document_ids: list[str] | None = None


class PipelineReadDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(..., ge=0)
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    document_id: str | None = None


class PipelineParallelSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1)
    queries: list[PipelineParallelQuery]


class PipelineEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: list[PipelineEvidenceChunk]


class PipelineAgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1)
    reasoning_effort: ReasoningEffort = "medium"
    review_enabled: bool = False
    tools: list[AgentToolType] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    evidence: list[PipelineEvidenceChunk] = Field(default_factory=list)
    upstream_outputs: list[PipelineAgentOutputEnvelope] = Field(default_factory=list)


class PipelineRunStartedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["run_started"] = "run_started"
    run_id: str
    timestamp: str


class PipelineNodeStartedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["node_started"] = "node_started"
    run_id: str
    node_id: str
    node_type: PipelineNodeType
    timestamp: str


class PipelineNodeTokenEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["node_token"] = "node_token"
    run_id: str
    node_id: str
    node_type: Literal["agent"]
    token: str
    timestamp: str


class PipelineNodeCompletedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["node_completed"] = "node_completed"
    run_id: str
    node_id: str
    node_type: PipelineNodeType
    output: dict[str, object]
    timestamp: str


class PipelineNodeFailedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["node_failed"] = "node_failed"
    run_id: str
    node_id: str
    node_type: PipelineNodeType
    error: str
    timestamp: str


class PipelineRunCompletedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["run_completed"] = "run_completed"
    run_id: str
    outputs: dict[str, object]
    timestamp: str


class PipelineRunFailedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["run_failed"] = "run_failed"
    run_id: str
    error: str
    timestamp: str


PipelineRunEvent = (
    PipelineRunStartedEvent
    | PipelineNodeStartedEvent
    | PipelineNodeTokenEvent
    | PipelineNodeCompletedEvent
    | PipelineNodeFailedEvent
    | PipelineRunCompletedEvent
    | PipelineRunFailedEvent
)
