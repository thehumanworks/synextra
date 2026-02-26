"use client";

import { useCallback, useRef, useState } from "react";

import { executePipeline } from "@/lib/builder/executor";
import { usePipelineStore } from "@/lib/builder/store";

type RunToolbarProps = {
  onOpenPalette?: () => void;
  onOpenConfig?: () => void;
  hasSelection: boolean;
};

export function RunToolbar({
  onOpenPalette,
  onOpenConfig,
  hasSelection,
}: RunToolbarProps) {
  const nodes = usePipelineStore((s) => s.nodes);
  const edges = usePipelineStore((s) => s.edges);
  const updateNodeData = usePipelineStore((s) => s.updateNodeData);

  const [query, setQuery] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const onRun = useCallback(async () => {
    if (!query.trim()) {
      setError("Enter a run query first");
      return;
    }
    if (nodes.length === 0) {
      setError("Add nodes to the pipeline first");
      return;
    }

    setError(null);
    setRunning(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await executePipeline(
        nodes,
        edges,
        query.trim(),
        updateNodeData,
        controller.signal,
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, [nodes, edges, query, updateNodeData]);

  const onStop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-stone-800 bg-stone-950 p-2 sm:p-3">
      <div className="flex items-center gap-2 lg:hidden">
        <button
          onClick={onOpenPalette}
          className="rounded-md border border-stone-700 bg-stone-900 px-2.5 py-1 text-xs text-stone-300 hover:bg-stone-800"
        >
          Nodes
        </button>
        <button
          onClick={onOpenConfig}
          disabled={!hasSelection}
          className="rounded-md border border-stone-700 bg-stone-900 px-2.5 py-1 text-xs text-stone-300 hover:bg-stone-800 disabled:opacity-50"
        >
          Config
        </button>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !running) {
              e.preventDefault();
              void onRun();
            }
          }}
          placeholder="Pipeline run query..."
          className="w-full rounded-md border border-stone-700 bg-stone-900 px-3 py-2 text-sm text-stone-200 placeholder:text-stone-500 focus:border-sky-500 focus:outline-none"
          disabled={running}
        />

        {running ? (
          <button
            onClick={onStop}
            className="rounded-md border border-red-800 bg-red-950 px-4 py-2 text-sm font-medium text-red-300 hover:bg-red-900"
          >
            Stop
          </button>
        ) : (
          <button
            onClick={() => void onRun()}
            className="rounded-md border border-sky-700 bg-sky-950 px-4 py-2 text-sm font-medium text-sky-300 hover:bg-sky-900"
          >
            Run
          </button>
        )}
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
