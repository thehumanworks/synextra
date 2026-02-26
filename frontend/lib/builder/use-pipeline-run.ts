"use client";

import { useCallback, useRef, useState } from "react";

import { executePipeline } from "@/lib/builder/executor";
import { usePipelineStore } from "@/lib/builder/store";

export type RunState = "idle" | "running" | "paused";

export function usePipelineRun() {
  const nodes = usePipelineStore((s) => s.nodes);
  const edges = usePipelineStore((s) => s.edges);
  const updateNodeData = usePipelineStore((s) => s.updateNodeData);

  const [runState, setRunState] = useState<RunState>("idle");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const runIdRef = useRef<string | null>(null);

  const play = useCallback(async () => {
    if (runState === "paused" && runIdRef.current) {
      try {
        const res = await fetch(
          `/api/pipeline/run/${encodeURIComponent(runIdRef.current)}/resume`,
          { method: "POST" },
        );
        if (res.ok) {
          setRunState("running");
        }
      } catch {
        setError("Failed to resume pipeline");
      }
      return;
    }

    if (runState !== "idle") return;
    if (nodes.length === 0) {
      setError("Add nodes to the pipeline first");
      return;
    }

    setError(null);
    setRunState("running");
    runIdRef.current = null;
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await executePipeline(
        nodes,
        edges,
        updateNodeData,
        controller.signal,
        (runId) => {
          runIdRef.current = runId;
        },
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setRunState("idle");
      abortRef.current = null;
      runIdRef.current = null;
    }
  }, [runState, nodes, edges, updateNodeData]);

  const pause = useCallback(async () => {
    if (runState !== "running" || !runIdRef.current) return;
    try {
      const res = await fetch(
        `/api/pipeline/run/${encodeURIComponent(runIdRef.current)}/pause`,
        { method: "POST" },
      );
      if (res.ok) {
        setRunState("paused");
      }
    } catch {
      setError("Failed to pause pipeline");
    }
  }, [runState]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setRunState("idle");
    runIdRef.current = null;
  }, []);

  const dismissError = useCallback(() => {
    setError(null);
  }, []);

  return { runState, error, play, pause, stop, dismissError } as const;
}
