"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { TextStreamChatTransport } from "ai";
import { AnimatePresence, motion } from "motion/react";

import { AiMessageBubble } from "@/components/ai-elements/message-bubble";
import type { Citation } from "@/lib/chat/structured-response";
import { splitStreamedText } from "@/lib/chat/stream-metadata";
import { Button } from "@/components/ui/button";
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

function parseUploadPipelineResponse(raw: unknown): UploadPipelineResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;

  if (typeof record.document_id !== "string" || !record.document_id) return null;
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
  const [processingLabel, setProcessingLabel] = useState("Upload a PDF to begin");
  const [isReadyForChat, setIsReadyForChat] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [documentInfo, setDocumentInfo] = useState<{
    documentId: string;
    filename: string;
    pageCount: number;
    chunkCount: number;
  } | null>(null);

  const listRef = useRef<HTMLDivElement | null>(null);

  const transport = useMemo(
    () =>
      new TextStreamChatTransport({
        api: "/api/chat",
        body: { reasoning_effort: "medium" },
      }),
    [],
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
    setProcessingLabel("Uploading and processing PDF…");
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
        throw new Error(getErrorMessage(raw, "Failed to process uploaded PDF"));
      }

      const payload = parseUploadPipelineResponse(raw);
      if (!payload || !payload.ready_for_chat) {
        throw new Error("Upload finished, but the document is not ready for chat.");
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

  const lastMessageId = messages.length ? messages[messages.length - 1]?.id : undefined;

  return (
    <section className="mx-auto flex w-full max-w-4xl flex-col gap-5">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: "easeOut" }}
        className="rounded-3xl bg-black px-5 py-5 shadow-[0_20px_70px_rgba(0,0,0,0.65)] md:px-6"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label
              htmlFor="pdf-upload"
              className="text-[0.68rem] uppercase tracking-[0.16em] text-stone-400"
            >
              PDF file
            </label>
            <input
              id="pdf-upload"
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null;
                setSelectedFile(file);
                setUploadError(null);
                setWarning(null);
                setIsReadyForChat(false);
                setDocumentInfo(null);
                setProcessingProgress(0);
                setProcessingLabel(file ? "File selected. Process to enable chat." : "Upload a PDF to begin");
              }}
              disabled={isProcessing || isSending}
              className={
                "mt-2 w-full rounded-2xl bg-zinc-950 px-3 py-3 text-sm text-stone-200 " +
                "file:mr-3 file:rounded-xl file:border-0 file:bg-stone-300 file:px-3 file:py-2 " +
                "file:text-xs file:font-semibold file:text-black"
              }
            />
          </div>
          <Button
            type="button"
            onClick={() => void processDocument()}
            disabled={!selectedFile || isProcessing || isSending}
            className="h-11 rounded-2xl px-5"
          >
            {isProcessing ? "Processing…" : "Process document"}
          </Button>
        </div>

        <div className="mt-3 flex items-center justify-between text-xs text-stone-400">
          <span>{processingLabel}</span>
          <span>{processingProgress}%</span>
        </div>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={processingProgress}
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-900"
        >
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-stone-500 via-stone-300 to-stone-500"
            animate={{ width: `${processingProgress}%` }}
            transition={{ duration: 0.2 }}
          />
        </div>

        <AnimatePresence initial={false}>
          {documentInfo ? (
            <motion.p
              key="doc-info"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mt-3 text-xs text-stone-400"
            >
              <span className="font-mono text-stone-300">{documentInfo.filename}</span>
              {" · "}
              {documentInfo.pageCount} pages
              {" · "}
              {documentInfo.chunkCount} chunks
              {" · "}
              <span className="font-mono text-stone-300">{documentInfo.documentId.slice(0, 12)}…</span>
            </motion.p>
          ) : null}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {warning ? (
            <motion.p
              key="warning"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mt-3 text-sm text-stone-300"
            >
              {warning}
            </motion.p>
          ) : null}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {uploadError ? (
            <motion.p
              key="upload-error"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mt-3 text-sm text-stone-200"
            >
              {uploadError}
            </motion.p>
          ) : null}
        </AnimatePresence>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.32, delay: 0.05, ease: "easeOut" }}
        className="relative min-h-[54vh] rounded-3xl bg-black px-5 pb-5 pt-4 shadow-[0_20px_70px_rgba(0,0,0,0.65)] md:px-6"
      >
        <div ref={listRef} className="max-h-[54vh] overflow-auto pb-32">
          <AnimatePresence initial={false}>
            {messages.length === 0 ? (
              <motion.p
                key="empty"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="px-1 py-3 text-sm text-stone-400"
              >
                No messages yet. Upload and process a PDF, then ask a question.
              </motion.p>
            ) : null}
          </AnimatePresence>

          <div className="flex flex-col gap-3">
            {messages.map((message) => {
              const rawText = messageText(message.parts);
              if (!rawText) return null;
              const isCurrentlyStreaming = isSending && message.id === lastMessageId;
              const { text, citations } = isCurrentlyStreaming
                ? { text: rawText, citations: [] as Citation[] }
                : splitStreamedText(rawText);
              return (
                <AiMessageBubble
                  key={message.id}
                  role={message.role}
                  text={text}
                  isStreaming={isCurrentlyStreaming}
                  citations={citations}
                />
              );
            })}
          </div>
        </div>

        <motion.div
          layout
          className="absolute bottom-0 left-0 right-0 rounded-b-3xl bg-black/96 px-5 pb-5 pt-4 md:px-6"
        >
          <div className="flex flex-col gap-3">
            <AnimatedInput
              id="prompt"
              value={prompt}
              onChange={setPrompt}
              onSubmit={() => void send()}
              disabled={chatDisabled}
              placeholders={
                isReadyForChat
                  ? [
                      "What does this document cover?",
                      "Summarize the key findings…",
                      "Find references to…",
                      "Explain the methodology…",
                    ]
                  : ["Process a PDF to enable chat…"]
              }
              aria-label="Your message"
            />
            <div className="flex gap-2 justify-end">
              <Button
                type="button"
                variant="destructive"
                onClick={() => setMessages([])}
                disabled={isSending || messages.length === 0}
                className="h-9 rounded-2xl px-4"
              >
                Clear
              </Button>
              <Button
                type="button"
                onClick={() => void send()}
                disabled={chatDisabled || !prompt.trim()}
                className="h-9 rounded-2xl px-4"
              >
                {isSending ? "Streaming…" : "Send"}
              </Button>
            </div>
          </div>

          <AnimatePresence initial={false}>
            {error ? (
              <motion.p
                key="chat-error"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="mt-3 text-sm text-stone-300"
              >
                {error.message}
              </motion.p>
            ) : null}
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </section>
  );
}
