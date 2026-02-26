// @vitest-environment node

import { describe, expect, it, vi } from "vitest";

import { POST } from "./route";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(chunks[index] ?? ""));
      index += 1;
    },
  });
}

describe("/api/pipeline/run POST", () => {
  it("forwards multipart spec + files to backend run stream endpoint", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(streamFromChunks(['{"event":"run_started"}\n']), {
        status: 200,
        headers: { "content-type": "application/x-ndjson" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const form = new FormData();
    form.append("spec", JSON.stringify({ query: "q", nodes: [], edges: [] }));
    form.append(
      "file:ing-1",
      new File([new Uint8Array([35, 32, 65, 10])], "notes.md", { type: "text/markdown" }),
    );

    const req = new Request("http://localhost/api/pipeline/run", {
      method: "POST",
      body: form,
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(await res.text()).toContain('"event":"run_started"');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend/v1/pipeline/runs/stream");
    expect((init as RequestInit).method).toBe("POST");
    const forwarded = (init as RequestInit).body as FormData;
    expect(forwarded.get("spec")).toBeTruthy();
    expect(forwarded.get("file:ing-1")).toBeInstanceOf(File);

    vi.unstubAllGlobals();
  });

  it("returns validation error when spec is missing", async () => {
    const form = new FormData();
    const req = new Request("http://localhost/api/pipeline/run", {
      method: "POST",
      body: form,
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("pipeline_spec_required");
  });

  it("passes backend errors through", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "pipeline_spec_invalid" } }), {
        status: 400,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const form = new FormData();
    form.append("spec", "{}");
    const req = new Request("http://localhost/api/pipeline/run", {
      method: "POST",
      body: form,
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("pipeline_spec_invalid");

    vi.unstubAllGlobals();
  });

  it("returns structured error when backend is unreachable", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";
    const fetchMock = vi.fn().mockRejectedValue(new Error("network down"));
    vi.stubGlobal("fetch", fetchMock);

    const form = new FormData();
    form.append("spec", "{}");
    const req = new Request("http://localhost/api/pipeline/run", {
      method: "POST",
      body: form,
    });

    const res = await POST(req);
    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.error.code).toBe("backend_unreachable");

    vi.unstubAllGlobals();
  });
});
