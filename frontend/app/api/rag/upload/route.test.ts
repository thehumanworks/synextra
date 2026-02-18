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
    expect(body.effective_mode).toBe("embedded");
    expect(body.stages.embedded.status).toBe("ok");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toBe("http://backend/v1/rag/pdfs");
    expect(fetchMock.mock.calls[1][0]).toBe(
      "http://backend/v1/rag/documents/doc-1/persist/embedded",
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

  it("returns backend errors for ingestion failures", async () => {
    process.env.SYNEXTRA_BACKEND_URL = "http://backend";

    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "pdf_parse_failed",
            message: "Failed to parse PDF",
            recoverable: false,
          },
        }),
        { status: 422, headers: { "content-type": "application/json" } },
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
    expect(res.status).toBe(422);

    const body = await res.json();
    expect(body.error.code).toBe("pdf_parse_failed");

    vi.unstubAllGlobals();
  });

  it("returns backend errors for embedded persistence failures", async () => {
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
            error: {
              code: "embedded_persist_failed",
              message: "upstream failure",
              recoverable: false,
            },
          }),
          { status: 500, headers: { "content-type": "application/json" } },
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
    expect(res.status).toBe(500);

    const body = await res.json();
    expect(body.error.code).toBe("embedded_persist_failed");

    vi.unstubAllGlobals();
  });
});
