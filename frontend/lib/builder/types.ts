import type { BuiltInNode, Edge, Node } from "@xyflow/react";

export type NodeStatus = "idle" | "running" | "streaming" | "done" | "error";
export type ReasoningEffort = "none" | "low" | "medium" | "high" | "xhigh";
export type AgentToolType = "bm25_search" | "read_document" | "parallel_search";

export const AGENT_TOOL_OPTIONS: { value: AgentToolType; label: string }[] = [
  { value: "bm25_search", label: "BM25 Search" },
  { value: "read_document", label: "Read Document" },
  { value: "parallel_search", label: "Parallel Search" },
];

export type PipelineNodeType =
  | "ingest"
  | "bm25_search"
  | "read_document"
  | "parallel_search"
  | "agent"
  | "output";

export type PipelineDocumentRef = {
  document_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
};

export type PipelineEvidenceChunk = {
  document_id: string;
  chunk_id: string;
  page_number?: number | null;
  text: string;
  score?: number;
  source_tool: string;
};

export type PipelineCitation = {
  document_id: string;
  chunk_id: string;
  page_number?: number | null;
  supporting_quote: string;
  source_tool: string;
  score?: number | null;
};

export type ParallelSearchQuery =
  | {
      type: "bm25_search";
      query_template: string;
      top_k: number;
      document_ids?: string[];
    }
  | {
      type: "read_document";
      page: number;
      start_line?: number;
      end_line?: number;
      document_id?: string;
    };

type BaseNodeData = {
  label: string;
  status: NodeStatus;
  error?: string;
};

export type IngestNodeData = BaseNodeData & {
  filename?: string;
  documents?: PipelineDocumentRef[];
  indexedChunkCount?: number;
};

export type Bm25SearchNodeData = BaseNodeData & {
  queryTemplate: string;
  topK: number;
  documentIds?: string[];
  lastQuery?: string;
  evidenceCount?: number;
};

export type ReadDocumentNodeData = BaseNodeData & {
  page: number;
  startLine?: number;
  endLine?: number;
  documentId?: string;
  evidenceCount?: number;
};

export type ParallelSearchNodeData = BaseNodeData & {
  queries: ParallelSearchQuery[];
  evidenceCount?: number;
};

export type AgentNodeData = BaseNodeData & {
  promptTemplate: string;
  reasoningEffort: ReasoningEffort;
  reviewEnabled: boolean;
  tools: AgentToolType[];
  systemInstructions?: string;
  output?: string;
  citations?: PipelineCitation[];
  toolsUsed?: string[];
  evidenceCount?: number;
};

export type OutputNodeData = BaseNodeData & {
  output?: string;
  sourceNodeId?: string;
};

export type IngestNode = Node<IngestNodeData, "ingest">;
export type Bm25SearchNode = Node<Bm25SearchNodeData, "bm25_search">;
export type ReadDocumentNode = Node<ReadDocumentNodeData, "read_document">;
export type ParallelSearchNode = Node<ParallelSearchNodeData, "parallel_search">;
export type AgentNode = Node<AgentNodeData, "agent">;
export type OutputNode = Node<OutputNodeData, "output">;

export type PipelineNode =
  | IngestNode
  | Bm25SearchNode
  | ReadDocumentNode
  | ParallelSearchNode
  | AgentNode
  | OutputNode;

export type AppNode = BuiltInNode | PipelineNode;
export type AppEdge = Edge;

export const PIPELINE_NODE_DEFAULTS: Record<PipelineNodeType, () => PipelineNode["data"]> = {
  ingest: () => ({ label: "Ingest", status: "idle" }),
  bm25_search: () => ({
    label: "BM25 Search",
    status: "idle",
    queryTemplate: "{query}",
    topK: 8,
  }),
  read_document: () => ({
    label: "Read Document",
    status: "idle",
    page: 0,
  }),
  parallel_search: () => ({
    label: "Parallel Search",
    status: "idle",
    queries: [
      { type: "bm25_search", query_template: "{query}", top_k: 8 },
      { type: "read_document", page: 0 },
    ],
  }),
  agent: () => ({
    label: "Agent",
    status: "idle",
    promptTemplate: "{query}",
    reasoningEffort: "medium",
    reviewEnabled: false,
    tools: ["bm25_search", "read_document"] as AgentToolType[],
  }),
  output: () => ({ label: "Output", status: "idle" }),
};
