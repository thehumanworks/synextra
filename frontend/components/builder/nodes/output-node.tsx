"use client";

import { memo } from "react";
import type { NodeProps } from "@xyflow/react";

import type { OutputNode } from "@/lib/builder/types";
import { BasePipelineNode } from "./base-pipeline-node";

export const OutputNodeComponent = memo(function OutputNodeComponent({
  data,
}: NodeProps<OutputNode>) {
  return (
    <BasePipelineNode
      label={data.label}
      status={data.status}
      icon={<span>&#x1F4E4;</span>}
      hasSource={false}
      error={data.error}
    >
      {data.output ? (
        <div className="line-clamp-5 text-stone-300">{data.output}</div>
      ) : (
        <div className="text-stone-500">Awaiting upstream agent output.</div>
      )}
    </BasePipelineNode>
  );
});
