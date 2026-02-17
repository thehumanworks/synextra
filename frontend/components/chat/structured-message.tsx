import React from "react";

import {
  RetrievalModeLabels,
  type RetrievalMode,
} from "@/lib/chat/mode-contract";
import type { StructuredChatResponse } from "@/lib/chat/structured-response";
import {
  dedupeCitations,
  formatCitationId,
  truncateQuote,
} from "@/lib/chat/citation-utils";
import { cn } from "@/lib/utils";
import { renderAgentEvents } from "@/components/chat/agent-event-renderers";

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

function AnswerBody({ answer }: { answer: string }) {
  const segments = answer.split(/```/g);

  return (
    <div className="space-y-3">
      {segments.map((segment, idx) => {
        const isCode = idx % 2 === 1;
        if (!isCode) {
          return (
            <p
              key={idx}
              className={cn(
                "whitespace-pre-wrap",
                "font-sans",
                "text-sm leading-relaxed text-stone-100"
              )}
            >
              {segment.trim()}
            </p>
          );
        }

        const trimmed = segment.replace(/^\n+/, "").replace(/\n+$/, "");
        const [maybeLang, ...rest] = trimmed.split("\n");
        const looksLikeLang = maybeLang.length < 18 && /^[a-zA-Z0-9_+-]+$/.test(maybeLang);
        const language = looksLikeLang ? maybeLang : undefined;
        const code = looksLikeLang ? rest.join("\n") : trimmed;

        return (
          <div key={idx} className="space-y-2">
            {language ? (
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                {language}
              </div>
            ) : null}
            <pre
              className={cn(
                "overflow-x-auto",
                "rounded-xl",
                "bg-black/55",
                "p-4",
                "text-xs leading-relaxed",
                "font-mono",
                "text-stone-100",
                "ring-1 ring-white/10"
              )}
            >
              <code>{code}</code>
            </pre>
          </div>
        );
      })}
    </div>
  );
}

export function StructuredMessage({ response }: { response: StructuredChatResponse }) {
  const citations = dedupeCitations(response.citations);

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
        <AnswerBody answer={response.answer} />
      </div>

      {response.agentEvents.length ? (
        <div className="mt-5">{renderAgentEvents(response.agentEvents)}</div>
      ) : null}

      {citations.length ? (
        <div className="mt-6">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">
            Citations
          </div>
          <ul className="mt-3 space-y-3">
            {citations.map((c) => (
              <li
                key={`${c.document_id}:${c.chunk_id}:${c.page_number ?? ""}`}
                className={cn(
                  "rounded-xl",
                  "bg-white/5",
                  "p-4",
                  "ring-1 ring-white/10"
                )}
              >
                <div className="text-xs font-mono text-stone-200">
                  {formatCitationId(c)}
                </div>
                <div className="mt-2 text-sm leading-relaxed text-stone-100">
                  “{truncateQuote(c.supporting_quote, 220)}”
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  Source: <span className="font-mono">{c.source_tool}</span>
                </div>
              </li>
            ))}
          </ul>
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
