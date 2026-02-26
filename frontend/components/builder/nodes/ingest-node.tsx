"use client";

import { memo, useCallback, useRef } from "react";
import type { NodeProps } from "@xyflow/react";
import type { IngestNode } from "@/lib/builder/types";
import { BasePipelineNode } from "./base-pipeline-node";
import { usePipelineStore } from "@/lib/builder/store";
import { setNodeFile } from "@/lib/builder/file-store";

export const IngestNodeComponent = memo(function IngestNodeComponent({
  id,
  data,
}: NodeProps<IngestNode>) {
  const updateNodeData = usePipelineStore((s) => s.updateNodeData);
  const inputRef = useRef<HTMLInputElement>(null);

  const onFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setNodeFile(id, file);
        updateNodeData(id, { filename: file.name });
      }
    },
    [id, updateNodeData],
  );

  return (
    <BasePipelineNode
      label={data.label}
      status={data.status}
      icon={<span>&#x1F4C4;</span>}
      hasTarget={false}
      error={data.error}
    >
      {data.filename ? (
        <div className="space-y-0.5">
          <div className="truncate font-medium text-stone-300">
            {data.filename}
          </div>
          {data.documents && data.documents.length > 0 && (
            <div>{data.documents.length} document(s) ready</div>
          )}
          {data.indexedChunkCount != null && <div>{data.indexedChunkCount} indexed chunks</div>}
        </div>
      ) : (
        <>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.doc,.csv,.xlsx,.txt,.md,.py,.ts,.js,.json,.yaml,.yml,.toml,.xml,.html,.css,.go,.rs,.java,.rb,.php,.sql,.sh"
            onChange={onFileSelect}
            className="hidden"
          />
          <button
            onClick={() => inputRef.current?.click()}
            className="rounded border border-stone-600 px-2 py-0.5 text-xs text-stone-300 hover:bg-stone-800"
          >
            Choose file
          </button>
        </>
      )}
    </BasePipelineNode>
  );
});
