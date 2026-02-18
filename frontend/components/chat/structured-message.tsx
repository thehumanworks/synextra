import React, { useCallback, useId, useMemo, useState } from "react";

import {
  RetrievalModeLabels,
  type RetrievalMode,
} from "@/lib/chat/mode-contract";
import type { StructuredChatResponse } from "@/lib/chat/structured-response";
import { injectCitationReferenceLinks } from "@/lib/chat/citation-reference-links";
import { cn } from "@/lib/utils";
import { renderAgentEvents } from "@/components/chat/agent-event-renderers";
import { CitationAccordion } from "@/components/chat/citation-accordion";
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

export function StructuredMessage({ response }: { response: StructuredChatResponse }) {
  const hasCitations = response.citations.length > 0;
  const citationScopeId = useId();
  const [focusReferenceIndex, setFocusReferenceIndex] = useState<number | null>(null);

  const answerWithCitationLinks = useMemo(
    () =>
      injectCitationReferenceLinks(response.answer, {
        scopeId: citationScopeId,
        maxIndex: response.citations.length,
      }),
    [citationScopeId, response.answer, response.citations.length]
  );

  const handleCitationReferenceClick = useCallback((index: number) => {
    setFocusReferenceIndex(index);
  }, []);

  const handleFocusReferenceHandled = useCallback(() => {
    setFocusReferenceIndex(null);
  }, []);

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
        <MarkdownResponse
          mode="static"
          citationReferenceScopeId={hasCitations ? citationScopeId : undefined}
          onCitationReferenceClick={hasCitations ? handleCitationReferenceClick : undefined}
        >
          {hasCitations ? answerWithCitationLinks : response.answer}
        </MarkdownResponse>
      </div>

      {response.agentEvents.length ? (
        <div className="mt-5">{renderAgentEvents(response.agentEvents)}</div>
      ) : null}

      {hasCitations ? (
        <div className="mt-6">
          <CitationAccordion
            citations={response.citations}
            referenceScopeId={citationScopeId}
            focusReferenceIndex={focusReferenceIndex}
            onFocusReferenceHandled={handleFocusReferenceHandled}
          />
        </div>
      ) : null}

      {!hasCitations && !response.parseMeta.ok ? (
        <div className="mt-6 text-xs text-muted-foreground">
          Response parsing failed; displaying raw assistant text.
        </div>
      ) : null}
    </div>
  );
}
