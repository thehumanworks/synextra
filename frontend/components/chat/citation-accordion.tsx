"use client";

import { useId, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import type { Citation } from "@/lib/chat/structured-response";
import { dedupeCitations, truncateQuote } from "@/lib/chat/citation-utils";
import { cn } from "@/lib/utils";

function normalizeCitationUrl(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

export function CitationAccordion({ citations: raw }: { citations: Citation[] }) {
  const citations = dedupeCitations(raw);
  const [open, setOpen] = useState(false);
  const regionId = useId();

  if (!citations.length) return null;

  return (
    <div className="mt-4">
      <button
        aria-controls={regionId}
        aria-expanded={open}
        className={cn(
          "inline-flex items-center gap-2 rounded-md px-2 py-1",
          "text-xs font-medium text-stone-200",
          "ring-1 ring-white/12 hover:bg-white/6",
        )}
        onClick={() => setOpen((c) => !c)}
        type="button"
      >
        <span>
          Used {citations.length} source{citations.length === 1 ? "" : "s"}
        </span>
        <span
          aria-hidden="true"
          className={cn(
            "text-[10px] transition-transform duration-150",
            open ? "rotate-180" : "rotate-0",
          )}
        >
          ▼
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.ul
            animate={{ opacity: 1, height: "auto", y: 0 }}
            className="mt-3 space-y-3 overflow-hidden"
            exit={{ opacity: 0, height: 0, y: -4 }}
            id={regionId}
            initial={{ opacity: 0, height: 0, y: -4 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            {citations.map((c, idx) => {
              const sourceUrl = normalizeCitationUrl(c.url ?? c.href);
              return (
                <motion.li
                  animate={{ opacity: 1, y: 0 }}
                  className={cn("rounded-xl", "bg-white/5", "p-4", "ring-1 ring-white/10")}
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
                    &ldquo;{truncateQuote(c.supporting_quote, 220)}&rdquo;
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
  );
}
