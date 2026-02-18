"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { TextStreamChatTransport } from "ai";
import { AnimatePresence, motion } from "motion/react";

import { AiMessageBubble } from "@/components/ai-elements/message-bubble";
import type { Citation } from "@/lib/chat/structured-response";
import type { StreamEvent } from "@/lib/chat/stream-metadata";
import {
  parseEventLine,
  splitStreamedText,
  STREAM_EVENTS_SEPARATOR,
} from "@/lib/chat/stream-metadata";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { AnimatedInput } from "@/components/ui/animated-input";

type UploadPipelineResponse = {
  document_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  ready_for_chat: boolean;
  effective_mode: "embedded";
  warning?: string;
};

function newId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(16).slice(2);
}

function parseUploadPipelineResponse(
  raw: unknown,
): UploadPipelineResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;

  if (typeof record.document_id !== "string" || !record.document_id) {
    return null;
  }
  if (typeof record.filename !== "string" || !record.filename) return null;
  if (typeof record.page_count !== "number") return null;
  if (typeof record.chunk_count !== "number") return null;
  if (typeof record.ready_for_chat !== "boolean") return null;
  if (record.effective_mode !== "embedded") {
    return null;
  }

  return {
    document_id: record.document_id,
    filename: record.filename,
    page_count: record.page_count,
    chunk_count: record.chunk_count,
    ready_for_chat: record.ready_for_chat,
    effective_mode: record.effective_mode as "embedded",
    warning: typeof record.warning === "string" ? record.warning : undefined,
  };
}

function getErrorMessage(raw: unknown, fallback: string): string {
  if (!raw || typeof raw !== "object") {
    return typeof raw === "string" && raw.trim() ? raw : fallback;
  }

  const error = (raw as Record<string, unknown>).error;
  if (!error || typeof error !== "object") {
    return fallback;
  }

  const message = (error as Record<string, unknown>).message;
  return typeof message === "string" && message.trim() ? message : fallback;
}

function messageText(parts: unknown): string {
  if (!Array.isArray(parts)) return "";

  return parts
    .map((part) => {
      if (!part || typeof part !== "object") return "";
      const candidate = part as { type?: unknown; text?: unknown };
      if (candidate.type !== "text") return "";
      return typeof candidate.text === "string" ? candidate.text : "";
    })
    .join("");
}

export function DocumentChatWorkspace() {
  const [sessionId] = useState(() => newId());
  const [prompt, setPrompt] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [isProcessing, setIsProcessing] = useState(false);
  const [processingProgress, setProcessingProgress] = useState(0);
  const [processingLabel, setProcessingLabel] = useState(
    "Upload a document to begin",
  );
  const [isReadyForChat, setIsReadyForChat] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [documentInfo, setDocumentInfo] = useState<
    {
      documentId: string;
      filename: string;
      pageCount: number;
      chunkCount: number;
    } | null
  >(null);

  const [reviewEnabled, setReviewEnabled] = useState(false);

  const listRef = useRef<HTMLDivElement | null>(null);

  const transport = useMemo(
    () =>
      new TextStreamChatTransport({
        api: "/api/chat",
        body: { reasoning_effort: "medium", review_enabled: reviewEnabled },
      }),
    [reviewEnabled],
  );

  const { messages, sendMessage, setMessages, status, error } = useChat({
    id: sessionId,
    transport,
  });

  const isSending = status === "submitted" || status === "streaming";
  const chatDisabled = !isReadyForChat || isProcessing || isSending;

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, status]);

  async function processDocument() {
    if (!selectedFile || isProcessing) return;

    setUploadError(null);
    setWarning(null);
    setIsReadyForChat(false);
    setDocumentInfo(null);
    setMessages([]);

    setIsProcessing(true);
    setProcessingLabel("Uploading and processing document…");
    setProcessingProgress(8);

    const timer = window.setInterval(() => {
      setProcessingProgress((current) => {
        if (current >= 92) return current;
        return current + 5;
      });
    }, 240);

    try {
      const form = new FormData();
      form.append("file", selectedFile, selectedFile.name || "upload.pdf");
      form.append("retrieval_mode", "hybrid");

      const res = await fetch("/api/rag/upload", {
        method: "POST",
        body: form,
      });

      const contentType = res.headers.get("content-type") ?? "";
      const raw = contentType.includes("application/json")
        ? await res.json()
        : await res.text();

      if (!res.ok) {
        throw new Error(
          getErrorMessage(raw, "Failed to process uploaded document"),
        );
      }

      const payload = parseUploadPipelineResponse(raw);
      if (!payload || !payload.ready_for_chat) {
        throw new Error(
          "Upload finished, but the document is not ready for chat.",
        );
      }

      setDocumentInfo({
        documentId: payload.document_id,
        filename: payload.filename,
        pageCount: payload.page_count,
        chunkCount: payload.chunk_count,
      });
      setWarning(payload.warning ?? null);
      setIsReadyForChat(true);
      setProcessingProgress(100);
      setProcessingLabel("Ready for chat");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setUploadError(message);
      setProcessingLabel("Processing failed");
      setProcessingProgress(0);
    } finally {
      window.clearInterval(timer);
      setIsProcessing(false);
    }
  }

  async function send() {
    const trimmed = prompt.trim();
    if (!trimmed || chatDisabled) return;

    setPrompt("");
    await sendMessage({ text: trimmed });
  }

  const lastMessageId = messages.length
    ? messages[messages.length - 1]?.id
    : undefined;

  return (
    <section className="mx-auto flex w-full max-w-4xl flex-col gap-4 sm:gap-5">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: "easeOut" }}
        className="rounded-2xl bg-black px-4 py-4 shadow-[0_20px_70px_rgba(0,0,0,0.65)] sm:rounded-3xl sm:px-5 sm:py-5 md:px-6"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label
              htmlFor="pdf-upload"
              className="text-[0.68rem] uppercase tracking-[0.16em] text-stone-400"
            >
              Document file
            </label>
            <input
              id="pdf-upload"
              type="file"
              accept=".pdf,.doc,.docx,.csv,.xlsx,.txt,.md,.py,.js,.jsx,.ts,.tsx,.json,.yaml,.yml,.toml,.go,.rs,.java,.kt,.swift,.c,.h,.cpp,.hpp,.cs,.rb,.php,.sql,.html,.css,.sh"
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null;
                setSelectedFile(file);
                setUploadError(null);
                setWarning(null);
                setIsReadyForChat(false);
                setDocumentInfo(null);
                setProcessingProgress(0);
                setProcessingLabel(
                  file
                    ? "File selected. Process to enable chat."
                    : "Upload a document to begin",
                );
              }}
              disabled={isProcessing || isSending}
              className={"mt-2 w-full rounded-2xl bg-zinc-950 px-3 py-3 text-sm text-stone-200 " +
                "file:mr-3 file:rounded-xl file:border-0 file:bg-stone-300 file:px-3 file:py-2.5 " +
                "file:text-xs file:font-semibold file:text-black sm:file:py-2"}
            />
          </div>
          <Button
            type="button"
            onClick={() => void processDocument()}
            disabled={!selectedFile || isProcessing || isSending}
            className="h-12 w-full rounded-2xl px-5 sm:h-11 sm:w-auto"
          >
            {isProcessing ? "Processing…" : "Process document"}
          </Button>
        </div>

        <div className="mt-3 flex items-center justify-between text-xs text-stone-400">
          <span>{processingLabel}</span>
          <span>{processingProgress}%</span>
        </div>
        <progress
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={processingProgress}
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-900"
        >
          <motion.div
            className="h-full rounded-full bg-linear-to-r from-stone-500 via-stone-300 to-stone-500"
            animate={{ width: `${processingProgress}%` }}
            transition={{ duration: 0.2 }}
          />
        </progress>

        <AnimatePresence initial={false}>
          {documentInfo
            ? (
              <motion.p
                key="doc-info"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="mt-3 text-xs text-stone-400"
              >
                <span className="font-mono text-stone-300">
                  {documentInfo.filename}
                </span>
                {" · "}
                {documentInfo.pageCount} pages
                {" · "}
                {documentInfo.chunkCount} chunks
                {" · "}
                <span className="font-mono text-stone-300">
                  {documentInfo.documentId.slice(0, 12)}…
                </span>
              </motion.p>
            )
            : null}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {warning
            ? (
              <motion.p
                key="warning"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="mt-3 text-sm text-stone-300"
              >
                {warning}
              </motion.p>
            )
            : null}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {uploadError
            ? (
              <motion.p
                key="upload-error"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="mt-3 text-sm text-stone-200"
              >
                {uploadError}
              </motion.p>
            )
            : null}
        </AnimatePresence>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.32, delay: 0.05, ease: "easeOut" }}
        className="relative min-h-[60vh] rounded-2xl bg-black px-4 pb-4 pt-3 shadow-[0_20px_70px_rgba(0,0,0,0.65)] sm:min-h-[54vh] sm:rounded-3xl sm:px-5 sm:pb-5 sm:pt-4 md:px-6"
      >
        <div
          ref={listRef}
          className="max-h-[60vh] overflow-auto pb-36 sm:max-h-[54vh] sm:pb-32"
        >
          <AnimatePresence initial={false}>
            {messages.length === 0
              ? (
                <motion.p
                  key="empty"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="px-1 py-3 text-sm text-stone-400"
                >
                  No messages yet. Upload and process a document, then ask a
                  question.
                </motion.p>
              )
              : null}
          </AnimatePresence>

          <div className="flex flex-col gap-3">
            {messages.map((message) => {
              const rawText = messageText(message.parts);
              const isCurrentlyStreaming = isSending &&
                message.id === lastMessageId;
              const isStreamingAssistant = isCurrentlyStreaming &&
                message.role === "assistant";

              if (!rawText && !isStreamingAssistant) return null;

              let text: string;
              let citations: Citation[];
              let events: StreamEvent[];

              if (isCurrentlyStreaming && message.role !== "user") {
                if (!rawText) {
                  events = [];
                  text = "";
                  citations = [];
                } else {
                  const eventsIdx = rawText.indexOf(STREAM_EVENTS_SEPARATOR);
                  if (eventsIdx !== -1) {
                    const parsed = splitStreamedText(rawText);
                    events = parsed.events;
                    text = parsed.text;
                    citations = [];
                  } else {
                    events = rawText
                      .split("\n")
                      .map(parseEventLine)
                      .filter((e): e is StreamEvent => e !== null);
                    text = "";
                    citations = [];
                  }
                }
              } else {
                const parsed = splitStreamedText(rawText);
                text = parsed.text;
                citations = parsed.citations;
                events = parsed.events;
              }

              return (
                <AiMessageBubble
                  key={message.id}
                  role={message.role}
                  text={text}
                  isStreaming={isCurrentlyStreaming}
                  citations={citations}
                  events={events}
                />
              );
            })}

            {isSending &&
                (messages.length === 0 ||
                  messages.at(-1)?.role === "user")
              ? (
                <AiMessageBubble
                  key="__thinking_placeholder__"
                  role="assistant"
                  text=""
                  isStreaming
                  events={[]}
                />
              )
              : null}
          </div>
        </div>

        <motion.div
          layout
          className="absolute bottom-0 left-0 right-0 rounded-b-2xl bg-black/96 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 sm:rounded-b-3xl sm:px-5 sm:pb-5 sm:pt-4 md:px-6"
        >
          <div className="flex flex-col gap-3">
            <AnimatedInput
              id="prompt"
              value={prompt}
              onChange={setPrompt}
              onSubmit={() => void send()}
              disabled={chatDisabled}
              placeholders={isReadyForChat
                ? [
                  "What does this document cover?",
                  "Summarize the key findings…",
                  "Find references to…",
                  "Explain the methodology…",
                ]
                : ["Process a document to enable chat…"]}
              aria-label="Your message"
            />
            <div className="flex items-center justify-between">
              <button
                type="button"
                role="switch"
                aria-checked={reviewEnabled}
                aria-label="Enable review workflow"
                onClick={() => setReviewEnabled((v) => !v)}
                className={cn(
                  "flex items-center gap-2 text-xs transition-colors duration-150",
                  "disabled:pointer-events-none disabled:opacity-50",
                  reviewEnabled ? "text-stone-200" : "text-stone-500",
                )}
              >
                <span
                  className={cn(
                    "relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors duration-200",
                    reviewEnabled ? "bg-emerald-600" : "bg-zinc-700",
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200",
                      reviewEnabled ? "translate-x-[18px]" : "translate-x-0.5",
                    )}
                  />
                </span>
                <span className="tracking-wide">Review</span>
              </button>

              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => setMessages([])}
                  disabled={isSending || messages.length === 0}
                  className="h-10 rounded-2xl px-4 sm:h-9"
                >
                  Clear
                </Button>
                <Button
                  type="button"
                  onClick={() => void send()}
                  disabled={chatDisabled || !prompt.trim()}
                  className="h-10 rounded-2xl px-5 sm:h-9 sm:px-4"
                >
                  {isSending ? "Streaming…" : "Send"}
                </Button>
              </div>
            </div>
          </div>

          <AnimatePresence initial={false}>
            {error
              ? (
                <motion.p
                  key="chat-error"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="mt-3 text-sm text-stone-300"
                >
                  {error.message}
                </motion.p>
              )
              : null}
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </section>
  );
}
