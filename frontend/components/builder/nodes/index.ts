import { AgentNodeComponent } from "./agent-node";
import { Bm25SearchNodeComponent } from "./bm25-search-node";
import { IngestNodeComponent } from "./ingest-node";
import { OutputNodeComponent } from "./output-node";
import { ParallelSearchNodeComponent } from "./parallel-search-node";
import { ReadDocumentNodeComponent } from "./read-document-node";

/**
 * Keep nodeTypes at module scope to avoid React Flow remounts (error002).
 */
export const nodeTypes = {
  ingest: IngestNodeComponent,
  bm25_search: Bm25SearchNodeComponent,
  read_document: ReadDocumentNodeComponent,
  parallel_search: ParallelSearchNodeComponent,
  agent: AgentNodeComponent,
  output: OutputNodeComponent,
} as const;
