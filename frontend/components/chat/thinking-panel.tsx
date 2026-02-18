"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import type { StreamEvent } from "@/lib/chat/stream-metadata";
import { cn } from "@/lib/utils";

// Simple inline SVG icons to avoid icon library dependencies

function SearchIcon() {
  return (
    <svg
      aria-hidden="true"
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="7" cy="7" r="5" />
      <line x1="11" y1="11" x2="15" y2="15" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="2,9 6,13 14,3" />
    </svg>
  );
}

function CrossIcon() {
  return (
    <svg
      aria-hidden="true"
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="3" y1="3" x2="13" y2="13" />
      <line x1="13" y1="3" x2="3" y2="13" />
    </svg>
  );
}

function BrainIcon() {
  return (
    <svg
      aria-hidden="true"
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M8 3C8 3 6 2 4.5 3.5C3 5 3 7 4 8.5C3 9.5 3 11 4 12C5 13 6.5 13 8 12" />
      <path d="M8 3C8 3 10 2 11.5 3.5C13 5 13 7 12 8.5C13 9.5 13 11 12 12C11 13 9.5 13 8 12" />
      <line x1="8" y1="3" x2="8" y2="12" />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden="true"
      width="10"
      height="10"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("transition-transform duration-200", open ? "rotate-180" : "rotate-0")}
    >
      <polyline points="4,6 8,10 12,6" />
    </svg>
  );
}

function eventLabel(ev: StreamEvent): string {
  if (ev.event === "search") {
    if (ev.tool === "read_document") {
      return ev.page != null ? `Read page ${ev.page}` : "Read document";
    }
    if (ev.query) {
      return `Search: ${ev.query}`;
    }
    return ev.tool ?? "Search";
  }
  if (ev.event === "review") {
    if (ev.verdict === "approved") return "Review passed";
    if (ev.verdict === "rejected") {
      return ev.feedback ? `Review rejected: ${ev.feedback}` : "Review rejected";
    }
    return "Review";
  }
  if (ev.event === "reasoning") {
    return ev.content ? ev.content.slice(0, 80) : "Reasoning";
  }
  return "Event";
}

function EventIcon({ ev }: { ev: StreamEvent }) {
  if (ev.event === "search") {
    return (
      <span className="text-stone-400">
        <SearchIcon />
      </span>
    );
  }
  if (ev.event === "review") {
    if (ev.verdict === "approved") {
      return (
        <span className="text-emerald-500">
          <CheckIcon />
        </span>
      );
    }
    if (ev.verdict === "rejected") {
      return (
        <span className="text-red-400">
          <CrossIcon />
        </span>
      );
    }
    return (
      <span className="text-stone-400">
        <CheckIcon />
      </span>
    );
  }
  if (ev.event === "reasoning") {
    return (
      <span className="text-stone-400">
        <BrainIcon />
      </span>
    );
  }
  return (
    <span className="text-stone-400">
      <SearchIcon />
    </span>
  );
}

type ThinkingPanelProps = {
  events: StreamEvent[];
  isStreaming?: boolean;
};

export function ThinkingPanel({ events, isStreaming = false }: ThinkingPanelProps) {
  const [open, setOpen] = useState(true);

  if (!events.length) return null;

  const label = isStreaming ? "Retrieving…" : `${events.length} step${events.length === 1 ? "" : "s"}`;

  return (
    <div
      data-testid="thinking-panel"
      className={cn(
        "mb-2 rounded-xl border border-white/8 bg-zinc-950/60 px-3 py-2.5",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={cn(
          "flex w-full items-center gap-2 text-left",
          "text-[0.68rem] uppercase tracking-[0.14em] text-stone-500",
          "hover:text-stone-400 transition-colors duration-150",
        )}
      >
        <span className="flex-1">{label}</span>
        <ChevronIcon open={open} />
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.ol
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="mt-2 overflow-hidden"
            aria-label="Retrieval steps"
          >
            {events.map((ev, idx) => (
              <motion.li
                key={`${ev.event}-${ev.timestamp}-${idx}`}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.14, delay: idx * 0.04, ease: "easeOut" }}
                className={cn(
                  "flex items-start gap-2 py-1",
                  idx < events.length - 1 && "border-b border-white/5",
                )}
              >
                <span className="mt-0.5 flex-shrink-0">
                  <EventIcon ev={ev} />
                </span>
                <span className="text-xs leading-relaxed text-stone-400">
                  {eventLabel(ev)}
                </span>
              </motion.li>
            ))}
          </motion.ol>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
