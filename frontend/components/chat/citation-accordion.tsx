"use client";

import { useEffect, useId, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import type { Citation } from "@/lib/chat/structured-response";
import {
  dedupeCitationsWithReferenceIndices,
  formatReferenceIndices,
  truncateQuote,
} from "@/lib/chat/citation-utils";
import { buildCitationReferenceElementId } from "@/lib/chat/citation-reference-links";
import { cn } from "@/lib/utils";

const SOURCE_LIST_EXPAND_TRANSITION_SECONDS = 0.2;
const SOURCE_LIST_SCROLL_RETRY_DELAY_MS =
  Math.round(SOURCE_LIST_EXPAND_TRANSITION_SECONDS * 1000) + 40;

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

type CitationAccordionProps = {
  citations: Citation[];
  referenceScopeId?: string;
  focusReferenceIndex?: number | null;
  onFocusReferenceHandled?: () => void;
};

export function CitationAccordion({
  citations: raw,
  referenceScopeId,
  focusReferenceIndex = null,
  onFocusReferenceHandled,
}: CitationAccordionProps) {
  const citations = dedupeCitationsWithReferenceIndices(raw);
  const sourceReferenceCount = raw.length;
  const [manualOpen, setManualOpen] = useState(false);
  const [selectedCitationIndex, setSelectedCitationIndex] = useState<
    number | null
  >(null);
  const regionId = useId();
  const fallbackScopeId = useId();
  const effectiveScopeId = referenceScopeId ?? fallbackScopeId;
  const open = manualOpen || focusReferenceIndex != null;

  useEffect(() => {
    if (focusReferenceIndex == null) return;

    const elementId = buildCitationReferenceElementId(
      effectiveScopeId,
      focusReferenceIndex,
    );
    const scrollTargetIntoView = () => {
      const target = document.getElementById(elementId);
      if (target && typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    };

    scrollTargetIntoView();

    let retryScrollTimer: number | null = null;
    if (!manualOpen) {
      // When the panel is closed, first scroll can fire before expand animation completes.
      retryScrollTimer = window.setTimeout(
        scrollTargetIntoView,
        SOURCE_LIST_SCROLL_RETRY_DELAY_MS,
      );
    }

    const focusHandledTimer = window.setTimeout(() => {
      onFocusReferenceHandled?.();
    }, 600);

    return () => {
      if (retryScrollTimer != null) {
        window.clearTimeout(retryScrollTimer);
      }
      window.clearTimeout(focusHandledTimer);
    };
  }, [
    effectiveScopeId,
    focusReferenceIndex,
    manualOpen,
    onFocusReferenceHandled,
  ]);

  useEffect(() => {
    if (selectedCitationIndex == null) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSelectedCitationIndex(null);
      }
    };

    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("keydown", handleEscape);
    };
  }, [selectedCitationIndex]);

  if (!citations.length) return null;

  const selectedCitation = selectedCitationIndex == null
    ? null
    : citations[selectedCitationIndex] ?? null;

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
        onClick={() => setManualOpen((current) => !current)}
        type="button"
      >
        <span>
          Used {sourceReferenceCount}{" "}
          source{sourceReferenceCount === 1 ? "" : "s"}
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
        {open
          ? (
            <motion.ul
              animate={{ opacity: 1, height: "auto", y: 0 }}
              className="mt-3 space-y-3 overflow-hidden"
              exit={{ opacity: 0, height: 0, y: -4 }}
              id={regionId}
              initial={{ opacity: 0, height: 0, y: -4 }}
              transition={{
                duration: SOURCE_LIST_EXPAND_TRANSITION_SECONDS,
                ease: "easeOut",
              }}
            >
              {citations.map((entry, idx) => {
                const c = entry.citation;
                const sourceUrl = normalizeCitationUrl(c.url ?? c.href);
                return (
                  <motion.li
                    animate={{ opacity: 1, y: 0 }}
                    className={cn(
                      "rounded-xl",
                      "bg-white/5",
                      "p-4",
                      "ring-1 ring-white/10",
                    )}
                    exit={{ opacity: 0, y: -4 }}
                    initial={{ opacity: 0, y: 6 }}
                    key={`${c.document_id}:${c.chunk_id}:${
                      c.page_number ?? ""
                    }`}
                    transition={{
                      duration: 0.16,
                      delay: idx * 0.03,
                      ease: "easeOut",
                    }}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="flex flex-wrap items-center gap-1">
                          {entry.referenceIndices.map(
                            (referenceIndex, referenceIdx) => {
                              const highlighted =
                                focusReferenceIndex === referenceIndex;
                              return (
                                <span
                                  key={referenceIndex}
                                  className="inline-flex items-center gap-1"
                                >
                                  <span
                                    id={buildCitationReferenceElementId(
                                      effectiveScopeId,
                                      referenceIndex,
                                    )}
                                    className={cn(
                                      "rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-mono",
                                      "tracking-wide text-stone-100 ring-1 ring-white/15",
                                      highlighted &&
                                        "bg-primary/20 text-primary ring-primary/40 shadow-[0_0_0_1px_rgba(236,72,153,0.3)]",
                                    )}
                                  >
                                    [{referenceIndex}]
                                  </span>
                                  {referenceIdx <
                                      entry.referenceIndices.length - 1
                                    ? (
                                      <span
                                        aria-hidden="true"
                                        className="text-xs text-muted-foreground"
                                      >
                                        ,
                                      </span>
                                    )
                                    : null}
                                </span>
                              );
                            },
                          )}
                        </div>
                        {c.page_number != null
                          ? (
                            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                              Page {c.page_number}
                            </div>
                          )
                          : null}
                      </div>
                      {sourceUrl
                        ? (
                          <a
                            className="text-xs text-primary underline underline-offset-2"
                            href={sourceUrl}
                            rel="noreferrer"
                            target="_blank"
                          >
                            Open link
                          </a>
                        )
                        : <div />}
                    </div>

                    {c.title
                      ? (
                        <div className="mt-2 text-xs font-medium text-stone-200">
                          {c.title}
                        </div>
                      )
                      : null}

                    <div className="mt-2 text-sm leading-relaxed text-stone-100">
                      &ldquo;{truncateQuote(c.supporting_quote, 220)}&rdquo;
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      Source: <span className="font-mono">{c.source_tool}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedCitationIndex(idx)}
                      className="mt-3 inline-flex items-center rounded-md px-2 py-1 text-xs font-medium text-stone-100 ring-1 ring-white/15 hover:bg-white/8"
                    >
                      Expand excerpt
                    </button>
                  </motion.li>
                );
              })}
            </motion.ul>
          )
          : null}
      </AnimatePresence>

      <AnimatePresence>
        {selectedCitation
          ? (
            <motion.div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 px-4 py-6"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedCitationIndex(null)}
            >
              <motion.div
                role="dialog"
                aria-modal="true"
                aria-label="Citation detail"
                className="w-full max-w-3xl rounded-2xl bg-zinc-950 p-5 ring-1 ring-white/15"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                transition={{ duration: 0.16, ease: "easeOut" }}
                onClick={(event) => event.stopPropagation()}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs text-muted-foreground">
                      References{" "}
                      {formatReferenceIndices(
                        selectedCitation.referenceIndices,
                      )}
                    </div>
                    <div className="mt-1 text-sm text-stone-200">
                      {selectedCitation.citation.page_number != null
                        ? `Page ${selectedCitation.citation.page_number}`
                        : "Page unknown"}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedCitationIndex(null)}
                    className="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium text-stone-100 ring-1 ring-white/15 hover:bg-white/8"
                  >
                    Close
                  </button>
                </div>

                {selectedCitation.citation.title
                  ? (
                    <div className="mt-3 text-sm font-medium text-stone-100">
                      {selectedCitation.citation.title}
                    </div>
                  )
                  : null}

                <div className="mt-4 max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-xl bg-black/45 p-4 text-sm leading-relaxed text-stone-100 ring-1 ring-white/10">
                  {selectedCitation.citation.supporting_quote}
                </div>
                <div className="mt-3 text-xs text-muted-foreground">
                  Source:{" "}
                  <span className="font-mono">
                    {selectedCitation.citation.source_tool}
                  </span>
                </div>
              </motion.div>
            </motion.div>
          )
          : null}
      </AnimatePresence>
    </div>
  );
}
