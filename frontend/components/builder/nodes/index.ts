import { AgentNodeComponent } from "./agent-node";
import { IngestNodeComponent } from "./ingest-node";
import { InputNodeComponent } from "./input-node";
import { OutputNodeComponent } from "./output-node";
import { ParallelSearchNodeComponent } from "./parallel-search-node";

/**
 * Keep nodeTypes at module scope to avoid React Flow remounts (error002).
 */
export const nodeTypes = {
  input: InputNodeComponent,
  ingest: IngestNodeComponent,
  parallel_search: ParallelSearchNodeComponent,
  agent: AgentNodeComponent,
  output: OutputNodeComponent,
} as const;
