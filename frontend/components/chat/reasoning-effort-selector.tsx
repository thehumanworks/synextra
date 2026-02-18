import React from "react";

import {
  ReasoningEffortLabels,
  type ReasoningEffort,
} from "@/lib/chat/reasoning-contract";

export function ReasoningEffortSelector({
  value,
  onChange,
  disabled,
}: {
  value: ReasoningEffort;
  onChange: (next: ReasoningEffort) => void;
  disabled?: boolean;
}) {
  const options: ReasoningEffort[] = [
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
  ];

  return (
    <div className="flex flex-col gap-2" data-testid="reasoning-effort-selector">
      <label
        className="text-xs uppercase tracking-wider text-muted-foreground"
        htmlFor="reasoning-effort"
      >
        Reasoning effort
      </label>
      <select
        id="reasoning-effort"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value as ReasoningEffort)}
        className={
          "rounded-xl bg-white/5 px-3 py-2 text-xs text-stone-100 ring-1 ring-white/10 " +
          "focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-60"
        }
      >
        {options.map((effort) => (
          <option key={effort} value={effort} className="bg-black text-stone-100">
            {ReasoningEffortLabels[effort]}
          </option>
        ))}
      </select>
      <div className="text-xs text-muted-foreground">
        Higher values can improve reasoning quality but may add latency.
      </div>
    </div>
  );
}
