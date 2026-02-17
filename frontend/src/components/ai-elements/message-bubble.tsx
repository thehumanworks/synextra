"use client";

import { motion } from "motion/react";

import { cn } from "@/lib/utils";

type MessageRole = "user" | "assistant" | "system" | string;

type AiMessageBubbleProps = {
  role: MessageRole;
  text: string;
};

export function AiMessageBubble({ role, text }: AiMessageBubbleProps) {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "rounded-lg border p-4 text-sm",
        isUser ? "border-primary/35 bg-primary/10" : "bg-card/80",
      )}
    >
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {role}
      </p>
      <p className="text-card-foreground">{text}</p>
    </motion.div>
  );
}
