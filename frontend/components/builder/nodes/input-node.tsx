"use client";

import { memo, useCallback, useRef } from "react";
import type { NodeProps } from "@xyflow/react";
import type { InputNode } from "@/lib/builder/types";
import { BasePipelineNode } from "./base-pipeline-node";
import { usePipelineStore } from "@/lib/builder/store";
import { setNodeFile } from "@/lib/builder/file-store";

const FILE_ACCEPT =
  ".pdf,.docx,.doc,.csv,.xlsx,.txt,.md,.py,.ts,.js,.json,.yaml,.yml,.toml,.xml,.html,.css,.go,.rs,.java,.rb,.php,.sql,.sh";

export const InputNodeComponent = memo(function InputNodeComponent({
  id,
  data,
}: NodeProps<InputNode>) {
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

  const onPromptChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      updateNodeData(id, { promptText: e.target.value });
    },
    [id, updateNodeData],
  );

  return (
    <BasePipelineNode
      label={data.label}
      status={data.status}
      icon={<span>&gt;_</span>}
      hasTarget={false}
      error={data.error}
    >
      <textarea
        value={data.promptText}
        onChange={onPromptChange}
        placeholder="Enter your prompt..."
        rows={3}
        className="nodrag w-full resize-none rounded border border-stone-700 bg-stone-800 px-2 py-1 text-xs text-stone-200 placeholder:text-stone-500 focus:border-sky-500 focus:outline-none"
      />

      <div className="mt-1.5">
        {data.filename ? (
          <div className="space-y-0.5">
            <div className="truncate font-medium text-stone-300">
              {data.filename}
            </div>
            {data.documents && data.documents.length > 0 && (
              <div>{data.documents.length} document(s) ready</div>
            )}
            {data.indexedChunkCount != null && (
              <div>{data.indexedChunkCount} indexed chunks</div>
            )}
          </div>
        ) : (
          <>
            <input
              ref={inputRef}
              type="file"
              accept={FILE_ACCEPT}
              onChange={onFileSelect}
              className="hidden"
            />
            <button
              onClick={() => inputRef.current?.click()}
              className="rounded border border-stone-600 px-2 py-0.5 text-xs text-stone-300 hover:bg-stone-800"
            >
              Attach file (optional)
            </button>
          </>
        )}
      </div>
    </BasePipelineNode>
  );
});
