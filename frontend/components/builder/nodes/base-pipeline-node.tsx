"use client";

import { memo, type ReactNode } from "react";
import { Handle, Position } from "@xyflow/react";
import type { NodeStatus } from "@/lib/builder/types";

const STATUS_STYLES: Record<NodeStatus, string> = {
  idle: "border-stone-700 bg-stone-900",
  running: "border-sky-500 bg-stone-900 shadow-[0_0_12px_rgba(14,165,233,0.3)]",
  streaming:
    "border-cyan-400 bg-stone-900 shadow-[0_0_16px_rgba(0,212,255,0.35)]",
  done: "border-emerald-500 bg-stone-900",
  error: "border-red-500 bg-stone-900 shadow-[0_0_12px_rgba(239,68,68,0.3)]",
};

const STATUS_INDICATOR: Record<NodeStatus, string> = {
  idle: "bg-stone-600",
  running: "bg-sky-500 animate-pulse",
  streaming: "bg-cyan-400 animate-pulse",
  done: "bg-emerald-500",
  error: "bg-red-500",
};

type BasePipelineNodeProps = {
  label: string;
  status: NodeStatus;
  icon: ReactNode;
  children?: ReactNode;
  hasTarget?: boolean;
  hasSource?: boolean;
  error?: string;
};

export const BasePipelineNode = memo(function BasePipelineNode({
  label,
  status,
  icon,
  children,
  hasTarget = true,
  hasSource = true,
  error,
}: BasePipelineNodeProps) {
  return (
    <div
      className={`relative min-w-[210px] rounded-lg border-2 px-3 py-2.5 text-stone-100 transition-colors ${STATUS_STYLES[status]}`}
    >
      {hasTarget && (
        <Handle
          type="target"
          position={Position.Left}
          className="!h-4 !w-4 !border-2 !border-stone-600 !bg-stone-800"
        />
      )}

      <div className="flex items-center gap-2">
        <span className="text-base">{icon}</span>
        <span className="text-sm font-medium">{label}</span>
        <span
          className={`ml-auto h-2 w-2 rounded-full ${STATUS_INDICATOR[status]}`}
        />
      </div>

      {children && (
        <div className="nodrag mt-2 border-t border-stone-700/50 pt-2 text-xs text-stone-400">
          {children}
        </div>
      )}

      {error && (
        <div className="mt-1.5 truncate text-xs text-red-400">{error}</div>
      )}

      {hasSource && (
        <Handle
          type="source"
          position={Position.Right}
          className="!h-4 !w-4 !border-2 !border-stone-600 !bg-stone-800"
        />
      )}
    </div>
  );
});
