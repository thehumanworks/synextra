"use client";

import { memo } from "react";
import type { NodeProps } from "@xyflow/react";

import type { Bm25SearchNode } from "@/lib/builder/types";
import { BasePipelineNode } from "./base-pipeline-node";

export const Bm25SearchNodeComponent = memo(function Bm25SearchNodeComponent({
  data,
}: NodeProps<Bm25SearchNode>) {
  return (
    <BasePipelineNode
      label={data.label}
      status={data.status}
      icon={<span>&#x1F50D;</span>}
      error={data.error}
    >
      <div>Query: {data.queryTemplate}</div>
      <div>Top-K: {data.topK}</div>
      {data.evidenceCount != null && <div>Evidence: {data.evidenceCount}</div>}
      {data.lastQuery && <div className="truncate text-stone-500">Last: {data.lastQuery}</div>}
    </BasePipelineNode>
  );
});
