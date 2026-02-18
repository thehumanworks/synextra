"use client";

import { motion } from "motion/react";

import { CitationAccordion } from "@/components/chat/citation-accordion";
import { MarkdownResponse } from "@/components/chat/markdown-response";
import type { Citation } from "@/lib/chat/structured-response";
import { cn } from "@/lib/utils";

type MessageRole = "user" | "assistant" | "system" | string;

type AiMessageBubbleProps = {
  role: MessageRole;
  text: string;
  isStreaming?: boolean;
  citations?: Citation[];
};

export function AiMessageBubble({
  role,
  text,
  isStreaming = false,
  citations,
}: AiMessageBubbleProps) {
  const isUser = role === "user";

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
      <p className="mb-2 text-[0.65rem] uppercase tracking-[0.16em] text-stone-500">{role}</p>
      {isUser ? (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-100">{text}</p>
      ) : (
        <MarkdownResponse
          mode="static"
          isAnimating={isStreaming}
          className="text-sm leading-relaxed text-stone-100"
        >
          {text}
        </MarkdownResponse>
      )}
      {!isUser && citations && citations.length > 0 ? (
        <CitationAccordion citations={citations} />
      ) : null}
    </motion.div>
  );
}
