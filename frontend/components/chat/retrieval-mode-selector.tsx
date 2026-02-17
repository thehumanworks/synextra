import React from "react";

import {
  RetrievalModeLabels,
  type RetrievalMode,
} from "@/lib/chat/mode-contract";
import { cn } from "@/lib/utils";

export function RetrievalModeSelector({
  value,
  onChange,
  disabled,
}: {
  value: RetrievalMode;
  onChange: (next: RetrievalMode) => void;
  disabled?: boolean;
}) {
  const options: RetrievalMode[] = ["hybrid"];

  return (
    <div className="flex flex-col gap-2" data-testid="retrieval-mode-selector">
      <div className="text-xs uppercase tracking-wider text-muted-foreground">
        Retrieval mode
      </div>
      <div
        className={cn(
          "grid grid-cols-1",
          "rounded-2xl bg-white/5 p-1",
          "ring-1 ring-white/10"
        )}
      >
        {options.map((mode) => {
          const active = mode === value;
          return (
            <button
              key={mode}
              type="button"
              disabled={disabled}
              onClick={() => onChange(mode)}
              className={cn(
                "rounded-xl px-3 py-2",
                "text-xs font-medium",
                "transition",
                active
                  ? "bg-white/10 text-stone-100 shadow-sm"
                  : "text-stone-300 hover:bg-white/6",
                disabled ? "opacity-60" : ""
              )}
              aria-pressed={active}
            >
              {RetrievalModeLabels[mode]}
            </button>
          );
        })}
      </div>
      <div className="text-xs text-muted-foreground">
        <span>
          Hybrid retrieval combines BM25 search with OpenAI vector store search.
        </span>
      </div>
    </div>
  );
}
