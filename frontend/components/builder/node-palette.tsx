"use client";

import type { DragEvent } from "react";

import type { PipelineNodeType } from "@/lib/builder/types";

const PALETTE_ITEMS: {
  type: PipelineNodeType;
  label: string;
  icon: string;
  description: string;
}[] = [
  {
    type: "input",
    label: "Input",
    icon: ">_",
    description: "Define prompt and upload files",
  },
  {
    type: "parallel_search",
    label: "Parallel Search",
    icon: "\u2699",
    description: "Run multiple search tools concurrently",
  },
  {
    type: "agent",
    label: "Agent",
    icon: "\u2728",
    description: "Build answer envelopes from evidence",
  },
  {
    type: "output",
    label: "Output",
    icon: "\u{1F4E4}",
    description: "Terminal output node",
  },
];

function onDragStart(event: DragEvent, nodeType: PipelineNodeType) {
  event.dataTransfer.setData("application/reactflow", nodeType);
  event.dataTransfer.effectAllowed = "move";
}

type NodePaletteProps = {
  onAddNode: (type: PipelineNodeType) => void;
};

export function NodePalette({ onAddNode }: NodePaletteProps) {
  return (
    <aside className="flex min-h-0 w-full flex-col gap-1.5 rounded-lg border border-stone-800 bg-stone-950 p-3 lg:w-56">
      <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-stone-500">
        Pipeline Nodes
      </h2>
      {PALETTE_ITEMS.map((item) => (
        <div
          key={item.type}
          className="flex items-center gap-2.5 rounded-md border border-stone-800 bg-stone-900 px-3 py-2 text-stone-200 transition-colors hover:border-stone-600 hover:bg-stone-800"
          draggable
          onDragStart={(e) => onDragStart(e, item.type)}
        >
          <span className="text-base">{item.icon}</span>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium">{item.label}</div>
            <div className="truncate text-xs text-stone-500">{item.description}</div>
          </div>
          <button
            onClick={() => onAddNode(item.type)}
            className="rounded border border-stone-700 px-2 py-0.5 text-xs text-stone-300 hover:bg-stone-700"
          >
            Add
          </button>
        </div>
      ))}
    </aside>
  );
}
