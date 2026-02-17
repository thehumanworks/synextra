import React, { useId, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import {
  RetrievalModeLabels,
  type RetrievalMode,
} from "@/lib/chat/mode-contract";
import type { StructuredChatResponse } from "@/lib/chat/structured-response";
import {
  dedupeCitations,
  truncateQuote,
} from "@/lib/chat/citation-utils";
import { cn } from "@/lib/utils";
import { renderAgentEvents } from "@/components/chat/agent-event-renderers";
import { MarkdownResponse } from "@/components/chat/markdown-response";

function ModeBadge({ mode }: { mode: RetrievalMode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2",
        "rounded-full bg-white/8 px-3 py-1",
        "text-xs font-medium text-stone-200",
        "ring-1 ring-white/10"
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
      {RetrievalModeLabels[mode]}
    </span>
  );
}

function normalizeCitationUrl(url: string | undefined): string | null {
  if (!url) return null;

  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

export function StructuredMessage({ response }: { response: StructuredChatResponse }) {
  const citations = dedupeCitations(response.citations);
  const [showSources, setShowSources] = useState(false);
  const sourcesRegionId = useId();

  return (
    <div
      className={cn(
        "rounded-2xl",
        "bg-white/5",
        "p-5",
        "shadow-md shadow-black/20",
        "ring-1 ring-white/10"
      )}
      data-testid="structured-message"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ModeBadge mode={response.mode} />
        {response.toolsUsed.length ? (
          <div className="text-xs text-muted-foreground">
            Tools: <span className="font-mono">{response.toolsUsed.join(", ")}</span>
          </div>
        ) : null}
      </div>

      <div className="mt-4">
        <MarkdownResponse mode="static">{response.answer}</MarkdownResponse>
      </div>

      {response.agentEvents.length ? (
        <div className="mt-5">{renderAgentEvents(response.agentEvents)}</div>
      ) : null}

      {citations.length ? (
        <div className="mt-6">
          <button
            aria-controls={sourcesRegionId}
            aria-expanded={showSources}
            className={cn(
              "inline-flex items-center gap-2 rounded-md px-2 py-1",
              "text-xs font-medium text-stone-200",
              "ring-1 ring-white/12 hover:bg-white/6"
            )}
            onClick={() => setShowSources((current) => !current)}
            type="button"
          >
            <span>Used {citations.length} source{citations.length === 1 ? "" : "s"}</span>
            <span
              aria-hidden="true"
              className={cn(
                "text-[10px] transition-transform duration-150",
                showSources ? "rotate-180" : "rotate-0"
              )}
            >
              ▼
            </span>
          </button>

          <AnimatePresence initial={false}>
            {showSources ? (
              <motion.ul
                animate={{ opacity: 1, height: "auto", y: 0 }}
                className="mt-3 space-y-3 overflow-hidden"
                exit={{ opacity: 0, height: 0, y: -4 }}
                id={sourcesRegionId}
                initial={{ opacity: 0, height: 0, y: -4 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                {citations.map((c, idx) => {
                  const sourceUrl = normalizeCitationUrl(c.url ?? c.href);

                  return (
                    <motion.li
                      animate={{ opacity: 1, y: 0 }}
                      className={cn(
                        "rounded-xl",
                        "bg-white/5",
                        "p-4",
                        "ring-1 ring-white/10"
                      )}
                      exit={{ opacity: 0, y: -4 }}
                      initial={{ opacity: 0, y: 6 }}
                      key={`${c.document_id}:${c.chunk_id}:${c.page_number ?? ""}`}
                      transition={{ duration: 0.16, delay: idx * 0.03, ease: "easeOut" }}
                    >
                      {c.page_number != null || sourceUrl ? (
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          {c.page_number != null ? (
                            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                              Page {c.page_number}
                            </div>
                          ) : (
                            <div />
                          )}
                          {sourceUrl ? (
                            <a
                              className="text-xs text-primary underline underline-offset-2"
                              href={sourceUrl}
                              rel="noreferrer"
                              target="_blank"
                            >
                              Open link
                            </a>
                          ) : null}
                        </div>
                      ) : null}

                      {c.title ? (
                        <div className="mt-2 text-xs font-medium text-stone-200">{c.title}</div>
                      ) : null}

                      <div className="mt-2 text-sm leading-relaxed text-stone-100">
                        “{truncateQuote(c.supporting_quote, 220)}”
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground">
                        Source: <span className="font-mono">{c.source_tool}</span>
                      </div>
                    </motion.li>
                  );
                })}
              </motion.ul>
            ) : null}
          </AnimatePresence>
        </div>
      ) : null}

      {!citations.length && !response.parseMeta.ok ? (
        <div className="mt-6 text-xs text-muted-foreground">
          Response parsing failed; displaying raw assistant text.
        </div>
      ) : null}
    </div>
  );
}
