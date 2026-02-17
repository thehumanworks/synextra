import { type RetrievalMode } from "@/lib/chat/mode-contract";
import { coerceReasoningEffort } from "@/lib/chat/reasoning-contract";

function newSessionId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(16).slice(2);
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));

  if (body?.dev_malformed) {
    // Intentionally broken payload to exercise client-side fallback paths.
    return new Response("{\"mode\":\"hybrid\",\"answer\":\"oops\"", {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }

  const sessionId: string =
    typeof body?.session_id === "string" && body.session_id.trim()
      ? body.session_id
      : newSessionId();

  const prompt: string =
    typeof body?.prompt === "string" && body.prompt.trim()
      ? body.prompt
      : "";

  const mode: RetrievalMode = "hybrid";
  const reasoningEffortInput = body?.reasoning_effort;
  const reasoningEffort = coerceReasoningEffort(reasoningEffortInput).effort;

  if (!prompt) {
    return new Response(
      JSON.stringify({
        session_id: sessionId,
        mode,
        answer: "(No prompt provided)",
        tools_used: [],
        citations: [],
        agent_events: [],
      }),
      {
        status: 400,
        headers: { "content-type": "application/json" },
      }
    );
  }

  const backendBase = process.env.SYNEXTRA_BACKEND_URL ?? "http://localhost:8000";
  const url = `${backendBase.replace(/\/$/, "")}/v1/rag/sessions/${encodeURIComponent(
    sessionId
  )}/messages`;

  try {
    const backendRes = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        prompt,
        retrieval_mode: mode,
        reasoning_effort: reasoningEffort,
      }),
    });

    const contentType = backendRes.headers.get("content-type") ?? "";
    const raw = contentType.includes("application/json")
      ? await backendRes.json()
      : await backendRes.text();

    return new Response(
      typeof raw === "string" ? raw : JSON.stringify(raw),
      {
        status: backendRes.status,
        headers: { "content-type": contentType || "application/json" },
      }
    );
  } catch (err) {
    // Backend not reachable in this environment.
    const message = err instanceof Error ? err.message : String(err);

    return new Response(
      JSON.stringify({
        session_id: sessionId,
        mode,
        reasoning_effort: reasoningEffort,
        answer:
          "Backend unavailable in this environment. This is a local fallback response.\n\n" +
          `Details: ${message}`,
        tools_used: ["local_fallback"],
        citations: [],
        agent_events: [
          {
            type: "verifier",
            detail: "backend_unavailable",
          },
        ],
      }),
      {
        status: 200,
        headers: { "content-type": "application/json" },
      }
    );
  }
}
