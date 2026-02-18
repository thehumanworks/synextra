"use client";

import { useCallback, useId, useMemo, useState } from "react";
import { motion } from "motion/react";

import { CitationAccordion } from "@/components/chat/citation-accordion";
import { ThinkingPanel } from "@/components/chat/thinking-panel";
import { MarkdownResponse } from "@/components/chat/markdown-response";
import { injectCitationReferenceLinks } from "@/lib/chat/citation-reference-links";
import type { Citation } from "@/lib/chat/structured-response";
import type { StreamEvent } from "@/lib/chat/stream-metadata";
import { cn } from "@/lib/utils";

type MessageRole = "user" | "assistant" | "system" | string;

type AiMessageBubbleProps = {
  role: MessageRole;
  text: string;
  isStreaming?: boolean;
  citations?: Citation[];
  events?: StreamEvent[];
};

function StreamingIndicator() {
  return (
    <div
      className="flex items-center gap-2.5 py-1"
      data-testid="streaming-indicator"
    >
      <span className="inline-flex gap-1">
        <motion.span
          className="h-1.5 w-1.5 rounded-full bg-stone-400"
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.span
          className="h-1.5 w-1.5 rounded-full bg-stone-400"
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{
            duration: 1.2,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.2,
          }}
        />
        <motion.span
          className="h-1.5 w-1.5 rounded-full bg-stone-400"
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{
            duration: 1.2,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.4,
          }}
        />
      </span>
      <span className="text-xs text-stone-500">Thinking…</span>
    </div>
  );
}

function AssistantContent({
  text,
  isStreaming,
  hasCitations,
  citationScopeId,
  citations,
  events,
  onCitationReferenceClick,
}: {
  text: string;
  isStreaming: boolean;
  hasCitations: boolean;
  citationScopeId: string;
  citations?: Citation[];
  events?: StreamEvent[];
  onCitationReferenceClick?: (index: number) => void;
}) {
  const hasEvents = (events?.length ?? 0) > 0;

  const renderedText = useMemo(() => {
    if (!hasCitations) return text;
    return injectCitationReferenceLinks(text, {
      scopeId: citationScopeId,
      maxIndex: citations?.length ?? 0,
    });
  }, [citationScopeId, citations?.length, hasCitations, text]);

  return (
    <>
      {isStreaming && !text && !hasEvents ? <StreamingIndicator /> : null}
      {hasEvents
        ? <ThinkingPanel events={events!} isStreaming={isStreaming} />
        : null}
      {text
        ? (
          <MarkdownResponse
            mode="static"
            isAnimating={isStreaming}
            citationReferenceScopeId={hasCitations
              ? citationScopeId
              : undefined}
            onCitationReferenceClick={hasCitations
              ? onCitationReferenceClick
              : undefined}
            className="text-sm leading-relaxed text-stone-100"
          >
            {renderedText}
          </MarkdownResponse>
        )
        : null}
    </>
  );
}

export function AiMessageBubble({
  role,
  text,
  isStreaming = false,
  citations,
  events,
}: AiMessageBubbleProps) {
  const isUser = role === "user";
  const citationScopeId = useId();
  const hasCitations = !isUser && (citations?.length ?? 0) > 0;
  const [focusReferenceIndex, setFocusReferenceIndex] = useState<number | null>(
    null,
  );

  const handleCitationReferenceClick = useCallback((index: number) => {
    setFocusReferenceIndex(index);
  }, []);

  const handleFocusReferenceHandled = useCallback(() => {
    setFocusReferenceIndex(null);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className={cn(
        "rounded-2xl px-4 py-3 md:px-5 md:py-4",
        isUser ? "ml-auto max-w-[82%] bg-zinc-900/80" : "max-w-full bg-black",
      )}
    >
      <p className="mb-2 text-[0.65rem] uppercase tracking-[0.16em] text-stone-500">
        {role}
      </p>
      {isUser
        ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-100">
            {text}
          </p>
        )
        : (
          <AssistantContent
            text={text}
            isStreaming={isStreaming}
            hasCitations={hasCitations}
            citationScopeId={citationScopeId}
            citations={citations}
            events={events}
            onCitationReferenceClick={hasCitations
              ? handleCitationReferenceClick
              : undefined}
          />
        )}
      {!isUser && citations && citations.length > 0
        ? (
          <CitationAccordion
            citations={citations}
            referenceScopeId={citationScopeId}
            focusReferenceIndex={focusReferenceIndex}
            onFocusReferenceHandled={handleFocusReferenceHandled}
          />
        )
        : null}
    </motion.div>
  );
}
