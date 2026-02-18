import { describe, expect, it, vi } from "vitest";

import { POST } from "./route";


function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let idx = 0;

  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (idx >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(chunks[idx]));
      idx += 1;
    },
  });
}

describe("/api/chat POST", () => {
  it("forwards latest user message to backend streaming endpoint", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(streamFromChunks(["assistant ", "reply"]), {
        status: 200,
        headers: { "content-type": "text/plain; charset=utf-8" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const req = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        id: "chat-session",
        messages: [
          {
            id: "u1",
            role: "user",
            parts: [{ type: "text", text: "hello from user" }],
          },
        ],
        reasoning_effort: "high",
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("assistant reply");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend/v1/rag/sessions/chat-session/messages/stream");
    expect((init as RequestInit).method).toBe("POST");
    const forwarded = JSON.parse(String((init as RequestInit).body));
    expect(forwarded.prompt).toBe("hello from user");
    expect(forwarded.retrieval_mode).toBe("hybrid");
    expect(forwarded.reasoning_effort).toBe("high");

    vi.unstubAllGlobals();
  });

  it("falls back unsupported reasoning effort to medium", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(streamFromChunks(["ok"]), {
        status: 200,
        headers: { "content-type": "text/plain; charset=utf-8" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const req = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        id: "s",
        messages: [{ id: "u", role: "user", content: "hello" }],
        reasoning_effort: "minimal",
      }),
    });

    await POST(req);

    const [, init] = fetchMock.mock.calls[0];
    const forwarded = JSON.parse(String((init as RequestInit).body));
    expect(forwarded.reasoning_effort).toBe("medium");

    vi.unstubAllGlobals();
  });

  it("returns a 400 plain-text response when prompt is missing", async () => {
    const req = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        id: "s",
        messages: [],
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
    expect(await res.text()).toContain("No prompt provided");
  });

  it("streams a local fallback when backend is unavailable", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";

    const fetchMock = vi.fn().mockRejectedValue(new Error("connect ECONNREFUSED"));
    vi.stubGlobal("fetch", fetchMock);

    const req = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        id: "fallback-session",
        messages: [{ id: "u", role: "user", content: "hello" }],
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/plain");
    expect(await res.text()).toContain("Backend unavailable");

    vi.unstubAllGlobals();
  });
});
