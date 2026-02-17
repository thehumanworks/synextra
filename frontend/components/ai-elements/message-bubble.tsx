"use client";

import { motion } from "motion/react";

import { cn } from "@/lib/utils";

type MessageRole = "user" | "assistant" | "system" | string;

type AiMessageBubbleProps = {
  role: MessageRole;
  text: string;
};

function MessageBody({ text }: { text: string }) {
  const segments = text.split(/```/g);

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
        return (
          <pre
            key={idx}
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
            <code>{trimmed}</code>
          </pre>
        );
      })}
    </div>
  );
}

export function AiMessageBubble({ role, text }: AiMessageBubbleProps) {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "rounded-2xl p-5",
        "shadow-md shadow-black/20",
        "ring-1",
        isUser
          ? "ml-auto bg-primary/10 ring-primary/20"
          : "bg-white/5 ring-white/10",
      )}
    >
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {role}
      </p>
      <MessageBody text={text} />
    </motion.div>
  );
}
