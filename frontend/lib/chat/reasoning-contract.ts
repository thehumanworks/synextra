import { z } from "zod";

export const ReasoningEffortSchema = z.enum([
  "none",
  "low",
  "medium",
  "high",
  "xhigh",
]);

export type ReasoningEffort = z.infer<typeof ReasoningEffortSchema>;

export const DEFAULT_REASONING_EFFORT: ReasoningEffort = "medium";

export function coerceReasoningEffort(value: unknown): {
  effort: ReasoningEffort;
  usedFallback: boolean;
  diagnostics?: Record<string, unknown>;
} {
  const parsed = ReasoningEffortSchema.safeParse(value);
  if (parsed.success) {
    return { effort: parsed.data, usedFallback: false };
  }

  return {
    effort: DEFAULT_REASONING_EFFORT,
    usedFallback: true,
    diagnostics: {
      received: value,
      issueCount: parsed.error.issues.length,
    },
  };
}

export const ReasoningEffortLabels: Record<ReasoningEffort, string> = {
  none: "None",
  low: "Low",
  medium: "Medium",
  high: "High",
  xhigh: "X-High",
};
