import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentChatWorkspace } from "./document-chat-workspace";


function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;

  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(chunks[index]));
      index += 1;
    },
  });
}

describe("DocumentChatWorkspace", () => {
  it("renders empty state with chat locked before upload", () => {
    render(<DocumentChatWorkspace />);
    expect(screen.getByText(/No messages yet/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Your message/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("processes upload and streams assistant response", async () => {
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
            effective_mode: "embedded",
            ready_for_chat: true,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(streamFromChunks(["assistant ", "**reply**"]), {
          status: 200,
          headers: { "content-type": "text/plain; charset=utf-8" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<DocumentChatWorkspace />);

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

    const textarea = screen.getByLabelText(/Your message/i);
    await user.clear(textarea);
    await user.type(textarea, "  hello world  ");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/rag/upload");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/chat");

    const [, init] = fetchMock.mock.calls[1];
    const forwarded = JSON.parse(String((init as RequestInit).body));
    expect(Array.isArray(forwarded.messages)).toBe(true);

    expect(await screen.findAllByText(/assistant/i)).toHaveLength(2);
    expect(await screen.findByText(/reply/i)).toBeInTheDocument();

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

    render(<DocumentChatWorkspace />);

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
    vi.unstubAllGlobals();
  });
});
