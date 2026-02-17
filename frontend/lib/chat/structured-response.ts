import { z } from "zod";

import {
  coerceRetrievalMode,
  DEFAULT_RETRIEVAL_MODE,
  type RetrievalMode,
} from "@/lib/chat/mode-contract";

export const CitationSchema = z
  .object({
    document_id: z.string().min(1),
    chunk_id: z.string().min(1),
    page_number: z.number().int().nonnegative().nullable().optional(),
    supporting_quote: z.string().min(1),
    source_tool: z.string().min(1).default("unknown"),
    score: z.number().nullable().optional(),
  })
  .strict();

export type Citation = z.infer<typeof CitationSchema>;

export const AgentEventSchema = z
  .object({
    type: z.string().min(1),
  })
  .passthrough();

export type AgentEvent = z.infer<typeof AgentEventSchema>;

export const StructuredChatResponseSchema = z
  .object({
    session_id: z.string().min(1).optional(),
    mode: z.string().optional(),
    answer: z.string().min(1),
    tools_used: z.array(z.string()).optional().default([]),
    citations: z.array(CitationSchema).optional().default([]),
    agent_events: z.array(AgentEventSchema).optional().default([]),
  })
  .passthrough();

export type StructuredChatResponse = {
  sessionId: string;
  mode: RetrievalMode;
  answer: string;
  toolsUsed: string[];
  citations: Citation[];
  agentEvents: AgentEvent[];
  parseMeta: {
    ok: boolean;
    usedModeFallback: boolean;
    diagnostics?: Record<string, unknown>;
  };
};

export function parseStructuredResponse(
  payload: unknown,
  options?: { fallbackMode?: RetrievalMode; sessionId?: string }
): StructuredChatResponse {
  const fallbackMode = options?.fallbackMode ?? DEFAULT_RETRIEVAL_MODE;
  const fallbackSessionId = options?.sessionId ?? "";

  const wrapPlainText = (
    text: string,
    diagnostics: Record<string, unknown>
  ): StructuredChatResponse => {
    return {
      sessionId: fallbackSessionId,
      mode: fallbackMode,
      answer: text,
      toolsUsed: [],
      citations: [],
      agentEvents: [],
      parseMeta: {
        ok: false,
        usedModeFallback: true,
        diagnostics,
      },
    };
  };

  let obj: unknown = payload;

  if (typeof payload === "string") {
    try {
      obj = JSON.parse(payload);
    } catch (err) {
      // Controlled fallback: treat the payload as plain assistant text.
      console.warn("parseStructuredResponse: malformed JSON; falling back", {
        error: String(err),
        sample: payload.slice(0, 120),
      });
      return wrapPlainText(payload, {
        reason: "malformed_json",
        sample: payload.slice(0, 120),
      });
    }
  }

  const parsed = StructuredChatResponseSchema.safeParse(obj);
  if (!parsed.success) {
    console.warn("parseStructuredResponse: schema mismatch; falling back", {
      issues: parsed.error.issues,
    });

    const record = obj && typeof obj === "object"
      ? (obj as Record<string, unknown>)
      : null;
    const plain =
      typeof record?.answer === "string" ? String(record.answer) : "";

    return wrapPlainText(
      plain || "(Unable to parse assistant response)",
      {
        reason: "schema_mismatch",
        issues: parsed.error.issues,
      }
    );
  }

  const rawMode = parsed.data.mode;
  const modeCoercion = coerceRetrievalMode(rawMode);
  if (modeCoercion.usedFallback) {
    console.warn("parseStructuredResponse: unknown mode; using fallback", {
      ...modeCoercion.diagnostics,
    });
  }

  const sessionId = parsed.data.session_id ?? fallbackSessionId;

  return {
    sessionId,
    mode: modeCoercion.mode,
    answer: parsed.data.answer,
    toolsUsed: parsed.data.tools_used ?? [],
    citations: parsed.data.citations ?? [],
    agentEvents: parsed.data.agent_events ?? [],
    parseMeta: {
      ok: true,
      usedModeFallback: modeCoercion.usedFallback,
      diagnostics: modeCoercion.diagnostics,
    },
  };
}
