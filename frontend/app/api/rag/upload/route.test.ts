// @vitest-environment node

import { describe, expect, it, vi } from "vitest";

import { POST } from "./route";

describe("/api/rag/upload POST", () => {
  it("ingests and persists to embedded store", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            document_id: "doc-1",
            filename: "paper.pdf",
            page_count: 12,
            chunk_count: 55,
          }),
          { status: 201, headers: { "content-type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            document_id: "doc-1",
            store: "embedded",
            status: "ok",
            indexed_chunk_count: 55,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const formData = new FormData();
    formData.append(
      "file",
      new File([new Uint8Array([37, 80, 68, 70])], "paper.pdf", {
        type: "application/pdf",
      }),
    );

    const req = new Request("http://localhost/api/rag/upload", {
      method: "POST",
      body: formData,
    });

    const res = await POST(req);
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.document_id).toBe("doc-1");
    expect(body.ready_for_chat).toBe(true);
    expect(body.requested_mode).toBe("embedded");
    expect(body.effective_mode).toBe("embedded");
    expect(body.stages.vector.status).toBe("skipped");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toBe("http://backend/v1/rag/pdfs");
    expect(fetchMock.mock.calls[1][0]).toBe(
      "http://backend/v1/rag/documents/doc-1/persist/embedded",
    );

    vi.unstubAllGlobals();
  });

  it("falls back to embedded when vector persistence fails recoverably", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            document_id: "doc-2",
            filename: "paper.pdf",
            page_count: 10,
            chunk_count: 48,
          }),
          { status: 201, headers: { "content-type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            document_id: "doc-2",
            store: "embedded",
            status: "ok",
            indexed_chunk_count: 48,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: {
              code: "vector_store_persist_failed",
              message: "OPENAI_API_KEY is not configured",
              recoverable: true,
            },
          }),
          { status: 502, headers: { "content-type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const formData = new FormData();
    formData.append(
      "file",
      new File([new Uint8Array([37, 80, 68, 70])], "paper.pdf", {
        type: "application/pdf",
      }),
    );
    formData.append("retrieval_mode", "vector");

    const req = new Request("http://localhost/api/rag/upload", {
      method: "POST",
      body: formData,
    });

    const res = await POST(req);
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.requested_mode).toBe("vector");
    expect(body.effective_mode).toBe("embedded");
    expect(body.ready_for_chat).toBe(true);
    expect(body.stages.vector.status).toBe("failed");
    expect(body.stages.vector.recoverable).toBe(true);
    expect(body.warning).toContain("Falling back to embedded");

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2][0]).toBe(
      "http://backend/v1/rag/documents/doc-2/persist/vector-store",
    );

    vi.unstubAllGlobals();
  });

  it("returns a validation error when file is missing", async () => {
    const req = new Request("http://localhost/api/rag/upload", {
      method: "POST",
      body: new FormData(),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);

    const body = await res.json();
    expect(body.error.code).toBe("file_required");
  });

  it("returns backend errors for non-recoverable failures", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            document_id: "doc-3",
            filename: "paper.pdf",
            page_count: 10,
            chunk_count: 22,
          }),
          { status: 201, headers: { "content-type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            document_id: "doc-3",
            store: "embedded",
            status: "ok",
            indexed_chunk_count: 22,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: {
              code: "vector_store_persist_failed",
              message: "upstream failure",
              recoverable: false,
            },
          }),
          { status: 502, headers: { "content-type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const formData = new FormData();
    formData.append(
      "file",
      new File([new Uint8Array([37, 80, 68, 70])], "paper.pdf", {
        type: "application/pdf",
      }),
    );
    formData.append("retrieval_mode", "vector");

    const req = new Request("http://localhost/api/rag/upload", {
      method: "POST",
      body: formData,
    });

    const res = await POST(req);
    expect(res.status).toBe(502);

    const body = await res.json();
    expect(body.error.code).toBe("vector_store_persist_failed");
    expect(body.error.recoverable).toBe(false);

    vi.unstubAllGlobals();
  });
});
