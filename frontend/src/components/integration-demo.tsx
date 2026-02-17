"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { motion } from "motion/react";
import { type FormEvent, useMemo, useState } from "react";

import { AiMessageBubble } from "@/components/ai-elements/message-bubble";
import { Button } from "@/components/ui/button";

function getMessageText(parts: Array<{ type: string; text?: string }>) {
  let value = "";

  for (const part of parts) {
    if (part.type === "text" && typeof part.text === "string") {
      value += part.text;
    }
  }

  return value.trim();
}

export function IntegrationDemo() {
  const [prompt, setPrompt] = useState("");
  const transport = useMemo(
    () => new DefaultChatTransport({ api: "/api/chat" }),
    [],
  );
  const { messages, sendMessage, status, error } = useChat({ transport });
  const isBusy = status === "submitted" || status === "streaming";

  const statusLabel = useMemo(() => {
    if (isBusy) {
      return "Assistant is streaming...";
    }

    if (status === "error") {
      return "The request failed. Check /api/chat.";
    }

    return "Ready. Type and send a prompt.";
  }, [isBusy, status]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextPrompt = prompt.trim();

    if (!nextPrompt || isBusy) {
      return;
    }

    setPrompt("");
    await sendMessage({ text: nextPrompt });
  }

  return (
    <section className="grid w-full gap-6 lg:grid-cols-[1.4fr_1fr]">
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="rounded-xl border bg-card p-6 shadow-lg backdrop-blur-sm"
      >
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
          Frontend Module Demo
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-card-foreground">
          Next.js + Motion + shadcn-style UI + AI SDK
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          This client component uses <code>motion/react</code> animation, a
          shadcn-style <code>Button</code> primitive, and the{" "}
          <code>useChat</code> hook from <code>@ai-sdk/react</code>.
        </p>

        <div className="mt-6 space-y-3">
          {messages.length === 0 ? (
            <div className="rounded-lg border border-dashed bg-input/70 p-4 text-sm text-slate-600">
              No chat messages yet.
            </div>
          ) : (
            messages.map((message) => {
              const text = getMessageText(
                message.parts as Array<{ type: string; text?: string }>,
              );

              return (
                <AiMessageBubble
                  key={message.id}
                  role={message.role}
                  text={text || "Non-text content returned by the stream."}
                />
              );
            })
          )}
        </div>

        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-3 sm:flex-row">
          <input
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Ask something about this scaffold..."
            className="h-10 w-full rounded-md border bg-input px-3 text-sm outline-none ring-offset-background transition placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button type="submit" disabled={isBusy || prompt.trim().length === 0}>
            {isBusy ? "Thinking..." : "Send"}
          </Button>
        </form>

        <p className="mt-3 text-xs text-slate-500">{statusLabel}</p>
        {error ? <p className="mt-1 text-xs text-red-600">{error.message}</p> : null}
      </motion.div>

      <motion.aside
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1, ease: "easeOut" }}
        className="rounded-xl border bg-card/80 p-6 shadow-md backdrop-blur-sm"
      >
        <h2 className="text-lg font-semibold text-card-foreground">
          Integration checklist
        </h2>
        <ul className="mt-3 space-y-2 text-sm text-slate-700">
          <li>
            <code>motion</code> drives entrance and message animations.
          </li>
          <li>
            <code>src/components/ui/button.tsx</code> provides a shadcn-style
            primitive.
          </li>
          <li>
            <code>@ai-sdk/react</code> is wired with <code>useChat</code>.
          </li>
          <li>
            <code>src/app/api/chat/route.ts</code> streams scaffold responses.
          </li>
        </ul>
      </motion.aside>
    </section>
  );
}
