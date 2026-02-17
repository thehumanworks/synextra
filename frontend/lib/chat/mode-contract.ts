import { z } from "zod";

export const RetrievalModeSchema = z.enum(["embedded", "vector", "hybrid"]);
export type RetrievalMode = z.infer<typeof RetrievalModeSchema>;

export const DEFAULT_RETRIEVAL_MODE: RetrievalMode = "embedded";

export function coerceRetrievalMode(value: unknown): {
  mode: RetrievalMode;
  usedFallback: boolean;
  diagnostics?: Record<string, unknown>;
} {
  const parsed = RetrievalModeSchema.safeParse(value);
  if (parsed.success) {
    return { mode: parsed.data, usedFallback: false };
  }

  return {
    mode: DEFAULT_RETRIEVAL_MODE,
    usedFallback: true,
    diagnostics: {
      received: value,
      issueCount: parsed.error.issues.length,
    },
  };
}

export const RetrievalModeLabels: Record<RetrievalMode, string> = {
  embedded: "Embedded",
  vector: "Vector",
  hybrid: "Hybrid",
};
