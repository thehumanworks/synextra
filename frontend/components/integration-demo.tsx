"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { motion } from "motion/react";

import { AiMessageBubble } from "@/components/ai-elements/message-bubble";
import { StructuredMessage } from "@/components/chat/structured-message";
import { RetrievalModeSelector } from "@/components/chat/retrieval-mode-selector";
import { Button } from "@/components/ui/button";
import {
  DEFAULT_RETRIEVAL_MODE,
  type RetrievalMode,
} from "@/lib/chat/mode-contract";
import { parseStructuredResponse } from "@/lib/chat/structured-response";
import { ds } from "@/lib/design-system/tokens";
import { cn } from "@/lib/utils";

type LocalMessage =
  | { id: string; role: "user"; text: string }
  | {
      id: string;
      role: "assistant";
      raw: unknown;
      response: ReturnType<typeof parseStructuredResponse>;
    };

type UploadPipelineMode = "embedded" | "vector";

type UploadPipelineResponse = {
  document_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  ready_for_chat: boolean;
  effective_mode: UploadPipelineMode;
  warning?: string;
};

function newId() {
  // Browser + test environments.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(16).slice(2);
}

function SessionIdSlice({ sessionId }: { sessionId: string }) {
  const [slice, setSlice] = useState("");

  useEffect(() => {
    setSlice(sessionId.slice(0, 10));
  }, [sessionId]);

  if (!slice) return null;
  return <span>{slice}…</span>;
}

function uploadModeForRetrievalMode(mode: RetrievalMode): UploadPipelineMode {
  return mode === "vector" ? "vector" : "embedded";
}

function parseUploadPipelineResponse(raw: unknown): UploadPipelineResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;

  const documentId = record.document_id;
  const filename = record.filename;
  const pageCount = record.page_count;
  const chunkCount = record.chunk_count;
  const ready = record.ready_for_chat;
  const effectiveMode = record.effective_mode;

  if (typeof documentId !== "string" || !documentId) return null;
  if (typeof filename !== "string" || !filename) return null;
  if (typeof pageCount !== "number") return null;
  if (typeof chunkCount !== "number") return null;
  if (typeof ready !== "boolean") return null;
  if (effectiveMode !== "embedded" && effectiveMode !== "vector") return null;

  return {
    document_id: documentId,
    filename,
    page_count: pageCount,
    chunk_count: chunkCount,
    ready_for_chat: ready,
    effective_mode: effectiveMode,
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
  if (typeof message !== "string" || !message.trim()) {
    return fallback;
  }
  return message;
}

export function IntegrationDemo() {
  const [mode, setMode] = useState<RetrievalMode>(DEFAULT_RETRIEVAL_MODE);
  const [prompt, setPrompt] = useState<string>(
    "What is the Transformer model described in the paper?",
  );
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [isSending, setIsSending] = useState(false);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingProgress, setProcessingProgress] = useState(0);
  const [processingLabel, setProcessingLabel] = useState("Upload a PDF to begin");
  const [isReadyForChat, setIsReadyForChat] = useState(false);
  const [documentInfo, setDocumentInfo] = useState<{
    documentId: string;
    filename: string;
    pageCount: number;
    chunkCount: number;
  } | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [sessionId, setSessionId] = useState("");
  useEffect(() => {
    setSessionId(newId());
  }, []);

  const listRef = useRef<HTMLDivElement | null>(null);
  const chatDisabled = !isReadyForChat || isProcessing || isSending;

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  async function processDocument() {
    if (!selectedFile || isProcessing) return;

    setError(null);
    setWarning(null);
    setIsReadyForChat(false);
    setDocumentInfo(null);
    setMessages([]);
    setPrompt("What is the Transformer model described in the paper?");

    setIsProcessing(true);
    setProcessingLabel("Uploading and processing PDF…");
    setProcessingProgress(6);

    const timer = window.setInterval(() => {
      setProcessingProgress((current) => {
        if (current >= 92) return current;
        return current + 6;
      });
    }, 260);

    try {
      const uploadMode = uploadModeForRetrievalMode(mode);
      const form = new FormData();
      form.append("file", selectedFile, selectedFile.name || "upload.pdf");
      form.append("retrieval_mode", uploadMode);

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

      if (payload.effective_mode !== mode) {
        setMode(payload.effective_mode);
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
      setError(message);
      setProcessingProgress(0);
      setProcessingLabel("Processing failed");
    } finally {
      window.clearInterval(timer);
      setIsProcessing(false);
    }
  }

  async function send() {
    const trimmed = prompt.trim();
    if (!trimmed || isSending || !isReadyForChat || isProcessing) return;

    setError(null);
    setIsSending(true);

    const userMessage: LocalMessage = {
      id: newId(),
      role: "user",
      text: trimmed,
    };
    setMessages((prev) => [...prev, userMessage]);
    setPrompt("");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          prompt: trimmed,
          retrieval_mode: mode,
        }),
      });

      const contentType = res.headers.get("content-type") ?? "";
      const raw = contentType.includes("application/json")
        ? await res.json()
        : await res.text();

      const response = parseStructuredResponse(raw, {
        fallbackMode: mode,
        sessionId,
      });

      const assistantMessage: LocalMessage = {
        id: newId(),
        role: "assistant",
        raw,
        response,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      const response = parseStructuredResponse(`Request failed: ${message}`, {
        fallbackMode: mode,
        sessionId,
      });

      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "assistant", raw: String(err), response },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <section className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={ds.panel}
      >
        <div className={ds.panelInner}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">
                Chat
              </div>
              <div className="mt-1 text-sm text-stone-100">
                Upload a PDF, process it, and then ask grounded questions.
              </div>
            </div>
            <div className="text-right">
              <div className={cn(ds.smallLabel)}>Session</div>
              <div className="mt-1 font-mono text-xs text-stone-200">
                <Suspense>
                  <SessionIdSlice sessionId={sessionId} />
                </Suspense>
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1">
                <label className={ds.smallLabel} htmlFor="pdf-upload">
                  PDF file
                </label>
                <input
                  id="pdf-upload"
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    setSelectedFile(file);
                    setError(null);
                    setWarning(null);
                    setIsReadyForChat(false);
                    setDocumentInfo(null);
                    setProcessingProgress(0);
                    setProcessingLabel(
                      file
                        ? "File selected. Process to enable chat."
                        : "Upload a PDF to begin",
                    );
                  }}
                  disabled={isProcessing || isSending}
                  className={
                    "mt-2 w-full rounded-xl bg-black/20 px-3 py-2 text-sm text-stone-100 " +
                    "file:mr-3 file:rounded-lg file:border-0 file:bg-white/10 file:px-3 file:py-2 " +
                    "file:text-xs file:font-medium file:text-stone-100"
                  }
                />
              </div>
              <Button
                type="button"
                onClick={() => void processDocument()}
                disabled={!selectedFile || isProcessing || isSending}
                className="h-11 rounded-2xl"
              >
                {isProcessing ? "Processing…" : "Process document"}
              </Button>
            </div>

            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>{processingLabel}</span>
              <span>{processingProgress}%</span>
            </div>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={processingProgress}
              className="mt-2 h-2 overflow-hidden rounded-full bg-white/10 ring-1 ring-white/10"
            >
              <div
                className={cn(
                  "h-full rounded-full bg-primary/70 transition-all duration-300",
                  isProcessing ? "animate-pulse" : "",
                )}
                style={{ width: `${processingProgress}%` }}
              />
            </div>
            {documentInfo ? (
              <div className="mt-3 text-xs text-muted-foreground">
                <span className="font-mono">{documentInfo.filename}</span>
                {" · "}
                {documentInfo.pageCount} pages
                {" · "}
                {documentInfo.chunkCount} chunks
                {" · "}
                <span className="font-mono">{documentInfo.documentId.slice(0, 12)}…</span>
              </div>
            ) : null}
          </div>

          <div
            ref={listRef}
            className={"mt-6 max-h-[52vh] overflow-auto pr-1 " + ds.chatList}
          >
            {messages.length === 0 ? (
              <div className="rounded-2xl bg-white/5 p-6 text-sm text-muted-foreground ring-1 ring-white/10">
                No messages yet. Upload and process a PDF, then ask a question.
              </div>
            ) : null}

            {messages.map((m) => {
              if (m.role === "user") {
                return <AiMessageBubble key={m.id} role="user" text={m.text} />;
              }
              return <StructuredMessage key={m.id} response={m.response} />;
            })}
          </div>

          <div className={ds.inputRow}>
            <RetrievalModeSelector
              value={mode}
              onChange={setMode}
              disabled={isSending || isProcessing}
            />

            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1">
                <label className={ds.smallLabel} htmlFor="prompt">
                  Your message
                </label>
                <textarea
                  id="prompt"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault();
                      void send();
                    }
                  }}
                  placeholder={
                    isReadyForChat
                      ? "Ask something and press Ctrl+Enter…"
                      : "Process a PDF to enable chat…"
                  }
                  className={
                    "mt-2 w-full resize-none rounded-2xl bg-white/5 p-4 text-sm text-stone-100 " +
                    "placeholder:text-stone-500 ring-1 ring-white/10 focus:outline-none focus:ring-2 focus:ring-primary/40"
                  }
                  rows={3}
                  disabled={chatDisabled}
                />
                <div className="mt-2 text-xs text-muted-foreground">
                  {isReadyForChat ? (
                    <span>
                      Tip: Press <span className="font-mono">Ctrl</span>+
                      <span className="font-mono">Enter</span> to send.
                    </span>
                  ) : (
                    <span>Process a PDF to unlock chat.</span>
                  )}
                </div>
              </div>

              <div className="flex gap-3 sm:flex-col sm:items-stretch">
                <Button
                  type="button"
                  onClick={() => void send()}
                  disabled={chatDisabled || !prompt.trim()}
                  className="h-11 rounded-2xl"
                >
                  {isSending ? "Sending…" : "Send"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setMessages([])}
                  disabled={isSending || messages.length === 0}
                  className="h-11 rounded-2xl"
                >
                  Clear
                </Button>
              </div>
            </div>

            {warning ? (
              <div className="rounded-2xl bg-amber-500/10 p-4 text-sm text-amber-200 ring-1 ring-amber-500/20">
                {warning}
              </div>
            ) : null}

            {error ? (
              <div className="rounded-2xl bg-red-500/10 p-4 text-sm text-red-200 ring-1 ring-red-500/20">
                {error}
              </div>
            ) : null}
          </div>
        </div>
      </motion.div>

      <motion.aside
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className={ds.panel}
      >
        <div className={ds.panelInner}>
          <div className="text-xs uppercase tracking-wider text-muted-foreground">
            Notes
          </div>
          <div className="mt-3 space-y-3 text-sm leading-relaxed text-stone-100">
            <p>
              Processing runs through ingestion plus persistence before chat is
              enabled.
            </p>
            <ul className="list-disc space-y-1 pl-5 text-stone-200">
              <li>Ingest PDF chunks to the repository.</li>
              <li>Persist embedded BM25 index (always).</li>
              <li>Persist vector embeddings when vector mode is selected.</li>
            </ul>
            <p className="text-xs text-muted-foreground">
              Retrieval currently uses either local BM25 chunks or OpenAI vector
              embeddings.
            </p>
          </div>
        </div>
      </motion.aside>
    </section>
  );
}
