"use client";

import { memo } from "react";
import type { NodeProps } from "@xyflow/react";

import type { ReadDocumentNode } from "@/lib/builder/types";
import { BasePipelineNode } from "./base-pipeline-node";

function rangeLabel(startLine?: number, endLine?: number): string {
  if (startLine == null && endLine == null) return "all lines";
  return `${startLine ?? 1}-${endLine ?? "end"}`;
}

export const ReadDocumentNodeComponent = memo(function ReadDocumentNodeComponent({
  data,
}: NodeProps<ReadDocumentNode>) {
  return (
    <BasePipelineNode
      label={data.label}
      status={data.status}
      icon={<span>&#x1F4D6;</span>}
      error={data.error}
    >
      <div>Page: {data.page}</div>
      <div>Lines: {rangeLabel(data.startLine, data.endLine)}</div>
      {data.documentId && <div className="truncate text-stone-500">Doc: {data.documentId}</div>}
      {data.evidenceCount != null && <div>Evidence: {data.evidenceCount}</div>}
    </BasePipelineNode>
  );
});
