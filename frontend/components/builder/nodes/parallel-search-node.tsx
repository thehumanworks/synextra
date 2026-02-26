"use client";

import { memo } from "react";
import type { NodeProps } from "@xyflow/react";

import type { ParallelSearchNode } from "@/lib/builder/types";
import { BasePipelineNode } from "./base-pipeline-node";

export const ParallelSearchNodeComponent = memo(function ParallelSearchNodeComponent({
  data,
}: NodeProps<ParallelSearchNode>) {
  return (
    <BasePipelineNode
      label={data.label}
      status={data.status}
      icon={<span>&#x2699;</span>}
      error={data.error}
    >
      <div>Queries: {data.queries.length}</div>
      {data.evidenceCount != null && <div>Evidence: {data.evidenceCount}</div>}
    </BasePipelineNode>
  );
});
