import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { StructuredMessage } from "@/components/chat/structured-message";
import type { StructuredChatResponse } from "@/lib/chat/structured-response";

function makeResponse(overrides: Partial<StructuredChatResponse> = {}): StructuredChatResponse {
  return {
    sessionId: "session-1",
    mode: "embedded",
    answer: "# Heading\n\nSome **bold** text [1].",
    toolsUsed: [],
    citations: [
      {
        document_id: "doc-1",
        chunk_id: "chunk-1",
        page_number: 3,
        supporting_quote: "Quote one",
        source_tool: "bm25_search",
        title: "Paper source",
        url: "https://example.com/source-1",
      },
      {
        document_id: "doc-2",
        chunk_id: "chunk-2",
        page_number: 5,
        supporting_quote: "Quote two",
        source_tool: "vector_search",
      },
    ],
    agentEvents: [],
    parseMeta: {
      ok: true,
      usedModeFallback: false,
    },
    ...overrides,
  };
}

describe("StructuredMessage", () => {
  it("renders markdown headings instead of plain text markers", () => {
    render(<StructuredMessage response={makeResponse()} />);

    expect(screen.getByRole("heading", { name: "Heading" })).toBeInTheDocument();
  });

  it("keeps sources collapsed by default, expands, and then collapses", async () => {
    const user = userEvent.setup();

    render(<StructuredMessage response={makeResponse()} />);

    const trigger = screen.getByRole("button", { name: /Used 2 sources/i });
    expect(trigger).toBeInTheDocument();
    expect(screen.queryByText(/Quote one/i)).not.toBeInTheDocument();

    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByText(/Quote one/i)).toBeVisible();
    });
    expect(screen.getAllByText("[1]")).not.toHaveLength(0);
    expect(screen.getByText("[2]")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open link/i })).toHaveAttribute(
      "href",
      "https://example.com/source-1",
    );

    await user.click(trigger);

    await waitFor(() => {
      expect(screen.queryByText(/Quote one/i)).not.toBeInTheDocument();
    });
  });

  it("renders agent events when provided", () => {
    render(
      <StructuredMessage
        response={makeResponse({
          agentEvents: [{ type: "verifier", passed: true }],
        })}
      />
    );

    expect(screen.getByTestId("agent-events")).toBeInTheDocument();
    expect(screen.getByText("Verifier")).toBeInTheDocument();
  });

  it("shows parse fallback notice when citations are absent", () => {
    render(
      <StructuredMessage
        response={makeResponse({
          citations: [],
          parseMeta: { ok: false, usedModeFallback: true },
        })}
      />
    );

    expect(
      screen.getByText(/Response parsing failed; displaying raw assistant text/i)
    ).toBeInTheDocument();
  });

  it("opens matching source when inline [n] citation is clicked", async () => {
    const user = userEvent.setup();
    render(<StructuredMessage response={makeResponse()} />);

    expect(screen.queryByText(/Quote one/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "[1]" }));

    await waitFor(() => {
      expect(screen.getByText(/Quote one/i)).toBeInTheDocument();
    });
  });
});
