"use client";

import { memo } from "react";
import type { NodeProps } from "@xyflow/react";

import type { AgentNode } from "@/lib/builder/types";
import { AGENT_TOOL_OPTIONS } from "@/lib/builder/types";
import { BasePipelineNode } from "./base-pipeline-node";

const toolLabelMap = Object.fromEntries(
  AGENT_TOOL_OPTIONS.map((opt) => [opt.value, opt.label]),
);

export const AgentNodeComponent = memo(function AgentNodeComponent({
  data,
}: NodeProps<AgentNode>) {
  return (
    <BasePipelineNode
      label={data.label}
      status={data.status}
      icon={<span>&#x2728;</span>}
      error={data.error}
    >
      <div className="flex gap-2">
        <span>Effort: {data.reasoningEffort}</span>
        <span>Review: {data.reviewEnabled ? "on" : "off"}</span>
      </div>
      {data.tools && data.tools.length > 0 && (
        <div className="truncate text-stone-400">
          Tools: {data.tools.map((t) => toolLabelMap[t] ?? t).join(", ")}
        </div>
      )}
      {data.evidenceCount != null && <div>Evidence: {data.evidenceCount}</div>}
      {data.toolsUsed && data.toolsUsed.length > 0 && (
        <div className="truncate">Used: {data.toolsUsed.join(", ")}</div>
      )}
      {data.status === "streaming" && (
        <div className="mt-1 flex items-center gap-1.5 text-cyan-400">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />
          Generating response…
        </div>
      )}
      {data.status === "done" && data.output && (
        <div className="mt-1 flex items-center gap-1.5 text-emerald-400">
          <span>&#x2713;</span>
          <span>Response ready</span>
        </div>
      )}
      {data.citations && data.citations.length > 0 && (
        <div>{data.citations.length} citations</div>
      )}
    </BasePipelineNode>
  );
});
