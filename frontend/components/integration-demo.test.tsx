import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { IntegrationDemo } from "./integration-demo";


describe("IntegrationDemo", () => {
  it("renders empty state", () => {
    render(<IntegrationDemo />);
    expect(screen.getByText(/No messages yet/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Your message/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("processes upload and then sends prompt to /api/chat", async () => {
    const user = userEvent.setup();

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            document_id: "doc-1",
            filename: "paper.pdf",
            page_count: 4,
            chunk_count: 12,
            requested_mode: "hybrid",
            effective_mode: "hybrid",
            ready_for_chat: true,
            stages: {
              ingestion: { status: "ok" },
              embedded: { status: "ok", indexed_chunk_count: 12 },
              vector: { status: "ok", vector_store_id: "vs_123" },
            },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            session_id: "session",
            mode: "embedded",
            answer: "assistant reply",
            tools_used: ["bm25"],
            citations: [],
            agent_events: [],
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<IntegrationDemo />);

    await user.upload(
      screen.getByLabelText(/PDF file/i),
      new File([new Uint8Array([37, 80, 68, 70])], "paper.pdf", {
        type: "application/pdf",
      }),
    );
    await user.click(screen.getByRole("button", { name: /process document/i }));

    await waitFor(() => {
      expect(screen.getByText(/Ready for chat/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Your message/i)).toBeEnabled();
    });
    expect(screen.queryByRole("option", { name: /minimal/i })).not.toBeInTheDocument();

    const textarea = screen.getByLabelText(/Your message/i);
    await user.selectOptions(screen.getByLabelText(/Reasoning effort/i), "high");
    await user.clear(textarea);
    await user.type(textarea, "  hello  ");

    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(fetchMock).toHaveBeenCalledTimes(2);

    const uploadCall = fetchMock.mock.calls[0];
    expect(uploadCall[0]).toBe("/api/rag/upload");

    const uploadForm = (uploadCall[1] as RequestInit).body as FormData;
    expect(uploadForm.get("retrieval_mode")).toBe("hybrid");

    const [, init] = fetchMock.mock.calls[1];
    const forwarded = JSON.parse((init as RequestInit).body as string);
    expect(forwarded.prompt).toBe("hello");
    expect(forwarded.retrieval_mode).toBe("hybrid");
    expect(forwarded.reasoning_effort).toBe("high");
    expect(typeof forwarded.session_id).toBe("string");

    expect(await screen.findByText(/assistant reply/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(textarea).toHaveValue("");
    });

    vi.unstubAllGlobals();
  });

  it("keeps chat disabled when upload processing fails", async () => {
    const user = userEvent.setup();

    const fetchMock = vi.fn().mockResolvedValue(
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

    render(<IntegrationDemo />);

    await user.upload(
      screen.getByLabelText(/PDF file/i),
      new File([new Uint8Array([37, 80, 68, 70])], "paper.pdf", {
        type: "application/pdf",
      }),
    );
    await user.click(screen.getByRole("button", { name: /process document/i }));

    expect(await screen.findByText(/Failed to parse PDF/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Your message/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/rag/upload");

    vi.unstubAllGlobals();
  });

  it("keeps hybrid mode when vector persistence falls back", async () => {
    const user = userEvent.setup();

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            document_id: "doc-2",
            filename: "paper.pdf",
            page_count: 3,
            chunk_count: 8,
            requested_mode: "hybrid",
            effective_mode: "hybrid",
            ready_for_chat: true,
            warning:
              "Vector persistence failed. Continuing in hybrid mode with BM25 fallback.",
            stages: {
              ingestion: { status: "ok" },
              embedded: { status: "ok", indexed_chunk_count: 8 },
              vector: { status: "failed", recoverable: true },
            },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            session_id: "session",
            mode: "embedded",
            answer: "fallback reply",
            tools_used: ["bm25_search"],
            citations: [],
            agent_events: [],
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<IntegrationDemo />);

    await user.upload(
      screen.getByLabelText(/PDF file/i),
      new File([new Uint8Array([37, 80, 68, 70])], "paper.pdf", {
        type: "application/pdf",
      }),
    );
    await user.click(screen.getByRole("button", { name: /process document/i }));

    expect(
      await screen.findByText(/Vector persistence failed/i),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText(/Your message/i), "hello");
    await user.click(screen.getByRole("button", { name: /send/i }));

    const [, init] = fetchMock.mock.calls[1];
    const forwarded = JSON.parse((init as RequestInit).body as string);
    expect(forwarded.retrieval_mode).toBe("hybrid");

    vi.unstubAllGlobals();
  });
});
