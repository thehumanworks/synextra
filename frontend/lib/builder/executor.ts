import type { AgentToolType, AppEdge, AppNode, ParallelSearchQuery, PipelineNodeType } from "./types";
import { getNodeFile } from "./file-store";

type NodeUpdater = (id: string, patch: Record<string, unknown>) => void;

type PipelineEvent = {
  event:
    | "run_started"
    | "node_started"
    | "node_token"
    | "node_completed"
    | "node_failed"
    | "run_completed"
    | "run_failed";
  run_id: string;
  node_id?: string;
  node_type?: PipelineNodeType;
  token?: string;
  output?: Record<string, unknown>;
  error?: string;
};

function buildRunSpec(nodes: AppNode[], edges: AppEdge[], query: string): Record<string, unknown> {
  return {
    query,
    nodes: nodes.map((node) => {
      const data = node.data as Record<string, unknown>;
      const label = typeof data.label === "string" ? data.label : node.type ?? "Node";
      if (node.type === "ingest") {
        return { id: node.id, type: "ingest", label, config: {} };
      }
      if (node.type === "bm25_search") {
        return {
          id: node.id,
          type: "bm25_search",
          label,
          config: {
            query_template: String(data.queryTemplate ?? "{query}"),
            top_k: Number(data.topK ?? 8),
            document_ids: Array.isArray(data.documentIds)
              ? (data.documentIds as string[])
              : undefined,
          },
        };
      }
      if (node.type === "read_document") {
        return {
          id: node.id,
          type: "read_document",
          label,
          config: {
            page: Number(data.page ?? 0),
            start_line:
              typeof data.startLine === "number" ? Number(data.startLine) : undefined,
            end_line: typeof data.endLine === "number" ? Number(data.endLine) : undefined,
            document_id:
              typeof data.documentId === "string" && data.documentId.trim()
                ? data.documentId
                : undefined,
          },
        };
      }
      if (node.type === "parallel_search") {
        return {
          id: node.id,
          type: "parallel_search",
          label,
          config: {
            queries: Array.isArray(data.queries)
              ? (data.queries as ParallelSearchQuery[])
              : [],
          },
        };
      }
      if (node.type === "agent") {
        return {
          id: node.id,
          type: "agent",
          label,
          config: {
            prompt_template: String(data.promptTemplate ?? "{query}"),
            reasoning_effort: String(data.reasoningEffort ?? "medium"),
            review_enabled: Boolean(data.reviewEnabled),
            tools: Array.isArray(data.tools) ? (data.tools as AgentToolType[]) : [],
            system_instructions:
              typeof data.systemInstructions === "string" && data.systemInstructions.trim()
                ? data.systemInstructions
                : undefined,
          },
        };
      }
      if (node.type === "output") {
        return { id: node.id, type: "output", label, config: {} };
      }
      return { id: node.id, type: "output", label, config: {} };
    }),
    edges: edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
    })),
  };
}

function applyNodeCompleted(
  event: PipelineEvent,
  updateNodeData: NodeUpdater,
): void {
  if (!event.node_id || !event.node_type) return;
  const output = event.output ?? {};
  if (event.node_type === "ingest") {
    const documents = Array.isArray(output.documents)
      ? (output.documents as Record<string, unknown>[])
      : [];
    const first = documents[0];
    updateNodeData(event.node_id, {
      status: "done",
      documents,
      filename:
        first && typeof first.filename === "string" ? first.filename : undefined,
      indexedChunkCount:
        typeof output.indexed_chunk_count === "number"
          ? output.indexed_chunk_count
          : undefined,
    });
    return;
  }

  if (
    event.node_type === "bm25_search" ||
    event.node_type === "read_document" ||
    event.node_type === "parallel_search"
  ) {
    updateNodeData(event.node_id, {
      status: "done",
      evidenceCount:
        typeof output.evidence_count === "number"
          ? output.evidence_count
          : Array.isArray(output.evidence)
            ? output.evidence.length
            : 0,
      ...(typeof output.query === "string" ? { lastQuery: output.query } : {}),
    });
    return;
  }

  if (event.node_type === "agent") {
    const citations =
      Array.isArray(output.citations) && output.citations.length > 0
        ? output.citations
        : Array.isArray(
              (output.agent_output as Record<string, unknown> | undefined)?.citations,
            )
          ? ((output.agent_output as Record<string, unknown>).citations as unknown[])
          : [];
    const toolsUsed =
      Array.isArray(output.tools_used) && output.tools_used.length > 0
        ? output.tools_used
        : Array.isArray(
              (output.agent_output as Record<string, unknown> | undefined)?.tools_used,
            )
          ? ((output.agent_output as Record<string, unknown>).tools_used as unknown[])
          : [];

    updateNodeData(event.node_id, {
      status: "done",
      output: typeof output.answer === "string" ? output.answer : undefined,
      citations,
      toolsUsed,
      evidenceCount:
        typeof output.evidence_count === "number" ? output.evidence_count : undefined,
    });
    return;
  }

  if (event.node_type === "output") {
    updateNodeData(event.node_id, {
      status: "done",
      output: typeof output.answer === "string" ? output.answer : "",
    });
  }
}

export async function executePipeline(
  nodes: AppNode[],
  edges: AppEdge[],
  query: string,
  updateNodeData: NodeUpdater,
  signal: AbortSignal,
): Promise<void> {
  for (const node of nodes) {
    const reset: Record<string, unknown> = { status: "idle", error: undefined };
    if (node.type === "agent" || node.type === "output") {
      reset.output = undefined;
    }
    updateNodeData(node.id, reset);
  }

  const form = new FormData();
  form.append("spec", JSON.stringify(buildRunSpec(nodes, edges, query)));

  for (const node of nodes) {
    if (node.type !== "ingest") continue;
    const file = getNodeFile(node.id);
    if (!file) {
      updateNodeData(node.id, { status: "error", error: "No file selected" });
      throw new Error(`Ingest node ${node.id} is missing a file`);
    }
    form.append(`file:${node.id}`, file, file.name);
  }

  const response = await fetch("/api/pipeline/run", {
    method: "POST",
    body: form,
    signal,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || "Pipeline run request failed");
  }
  if (!response.body) {
    throw new Error("Pipeline runtime stream was empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const streamedText = new Map<string, string>();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        const event = JSON.parse(trimmed) as PipelineEvent;

        if (event.event === "node_started" && event.node_id) {
          updateNodeData(event.node_id, { status: "running", error: undefined });
          if (event.node_type === "agent") {
            streamedText.set(event.node_id, "");
          }
          continue;
        }

        if (event.event === "node_token" && event.node_id && typeof event.token === "string") {
          const existing = streamedText.get(event.node_id) ?? "";
          const next = `${existing}${event.token}`;
          streamedText.set(event.node_id, next);
          updateNodeData(event.node_id, {
            status: "streaming",
            output: next,
          });
          continue;
        }

        if (event.event === "node_completed") {
          applyNodeCompleted(event, updateNodeData);
          continue;
        }

        if (event.event === "node_failed" && event.node_id) {
          updateNodeData(event.node_id, {
            status: "error",
            error: event.error ?? "Node failed",
          });
          continue;
        }

        if (event.event === "run_failed") {
          throw new Error(event.error ?? "Pipeline run failed");
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  const tail = buffer.trim();
  if (tail) {
    const event = JSON.parse(tail) as PipelineEvent;
    if (event.event === "run_failed") {
      throw new Error(event.error ?? "Pipeline run failed");
    }
    if (event.event === "node_completed") {
      applyNodeCompleted(event, updateNodeData);
    }
  }
}
