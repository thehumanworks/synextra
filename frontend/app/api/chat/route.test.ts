import { describe, expect, it, vi } from "vitest";

import { POST } from "./route";


describe("/api/chat POST", () => {
  it("forwards prompt and retrieval_mode to the backend", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_id: "s",
          mode: "hybrid",
          answer: "ok",
          tools_used: ["bm25"],
          citations: [],
          agent_events: [],
        }),
        { status: 200, headers: { "content-type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const req = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_id: "s",
        prompt: "hello",
        retrieval_mode: "hybrid",
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.answer).toBe("ok");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, rawInit] = fetchMock.mock.calls[0];
    const init = (rawInit ?? {}) as RequestInit;
    expect(init.method).toBe("POST");

    const forwarded = JSON.parse(String(init.body ?? "{}"));
    expect(forwarded.prompt).toBe("hello");
    expect(forwarded.retrieval_mode).toBe("hybrid");

    vi.unstubAllGlobals();
  });

  it("returns malformed JSON when dev_malformed is set", async () => {
    const req = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ dev_malformed: true }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain("\"answer\"");
    expect(() => JSON.parse(text)).toThrow();
  });
});
