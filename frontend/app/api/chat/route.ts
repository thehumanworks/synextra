import { coerceReasoningEffort } from "@/lib/chat/reasoning-contract";

type ChatMessagePart = {
  type?: unknown;
  text?: unknown;
};

type ChatMessage = {
  role?: unknown;
  content?: unknown;
  parts?: unknown;
};

function newSessionId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(16).slice(2);
}

function textPartToString(part: unknown): string {
  if (!part || typeof part !== "object") return "";
  const candidate = part as ChatMessagePart;
  if (candidate.type !== "text") return "";
  return typeof candidate.text === "string" ? candidate.text : "";
}

function messageToText(message: ChatMessage): string {
  if (typeof message.content === "string" && message.content.trim()) {
    return message.content;
  }

  if (Array.isArray(message.parts)) {
    const text = message.parts.map(textPartToString).join("");
    if (text.trim()) return text;
  }

  if (Array.isArray(message.content)) {
    const text = message.content.map(textPartToString).join("");
    if (text.trim()) return text;
  }

  return "";
}

function latestUserPrompt(messages: unknown): string {
  if (!Array.isArray(messages)) return "";

  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (!message || typeof message !== "object") continue;

    const candidate = message as ChatMessage;
    if (candidate.role !== "user") continue;

    const text = messageToText(candidate).trim();
    if (text) return text;
  }

  return "";
}

function streamTextResponse(text: string, status: number): Response {
  const encoder = new TextEncoder();
  const chunks = text.match(/.{1,48}/g) ?? [text];
  let index = 0;

  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(chunks[index] ?? ""));
      index += 1;
    },
  });

  return new Response(stream, {
    status,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-cache",
    },
  });
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));

  const sessionId: string =
    typeof body?.id === "string" && body.id.trim()
      ? body.id
      : typeof body?.session_id === "string" && body.session_id.trim()
        ? body.session_id
        : newSessionId();

  const promptFromMessages = latestUserPrompt(body?.messages);
  const promptFromBody =
    typeof body?.prompt === "string" ? body.prompt.trim() : "";
  const prompt = promptFromMessages || promptFromBody;

  const reasoningEffortInput = body?.reasoning_effort;
  const reasoningEffort = coerceReasoningEffort(reasoningEffortInput).effort;
  const reviewEnabled = body?.review_enabled === true;

  if (!prompt) {
    return streamTextResponse("(No prompt provided)", 400);
  }

  const backendBase =
    process.env.SYNEXTRA_BACKEND_URL ?? "http://localhost:8000";
  const url = `${backendBase.replace(/\/$/, "")}/v1/rag/sessions/${encodeURIComponent(
    sessionId,
  )}/messages/stream`;

  try {
    const backendRes = await fetch(url, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "text/plain",
      },
      body: JSON.stringify({
        prompt,
        retrieval_mode: "hybrid",
        reasoning_effort: reasoningEffort,
        review_enabled: reviewEnabled,
      }),
    });

    if (!backendRes.ok) {
      const errorText = await backendRes.text();
      return new Response(errorText || "Chat request failed", {
        status: backendRes.status,
        headers: {
          "content-type":
            backendRes.headers.get("content-type") ??
            "text/plain; charset=utf-8",
        },
      });
    }

    if (!backendRes.body) {
      throw new Error("Backend stream body is empty");
    }

    return new Response(backendRes.body, {
      status: 200,
      headers: {
        "content-type":
          backendRes.headers.get("content-type") ?? "text/plain; charset=utf-8",
        "cache-control": "no-cache",
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return streamTextResponse(
      "Backend unavailable in this environment. This is a local fallback stream.\n\n" +
        `Details: ${message}`,
      200,
    );
  }
}
