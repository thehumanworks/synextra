import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Citation } from "@/lib/chat/structured-response";

import { AiMessageBubble } from "@/components/ai-elements/message-bubble";

describe("AiMessageBubble", () => {
  it("renders text content for a user message", () => {
    render(<AiMessageBubble role="user" text="Hello" />);

    expect(screen.getByText("user")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("applies assistant styling variant", () => {
    render(<AiMessageBubble role="assistant" text="World" />);

    const bubble = screen.getByText("assistant").parentElement;
    expect(bubble?.className).toContain("bg-black");
  });

  it("renders markdown for assistant responses", () => {
    render(<AiMessageBubble role="assistant" text={"# Heading\n\nSome text"} />);

    expect(screen.getByRole("heading", { name: "Heading" })).toBeInTheDocument();
  });

  it("handles unknown roles without crashing", () => {
    render(<AiMessageBubble role="tool" text="Tool output" />);

    expect(screen.getByText("tool")).toBeInTheDocument();
  });

  it("renders citation accordion when citations are provided", () => {
    const citations: Citation[] = [
      {
        document_id: "doc-1",
        chunk_id: "c1",
        page_number: 5,
        supporting_quote: "Relevant excerpt from the document.",
        source_tool: "bm25",
      },
    ];

    render(<AiMessageBubble role="assistant" text="Answer text" citations={citations} />);

    expect(screen.getByRole("button", { name: /used 1 source/i })).toBeInTheDocument();
  });

  it("does not render citation accordion for user messages even if citations passed", () => {
    const citations: Citation[] = [
      {
        document_id: "doc-1",
        chunk_id: "c1",
        page_number: 5,
        supporting_quote: "quote",
        source_tool: "bm25",
      },
    ];

    render(<AiMessageBubble role="user" text="User text" citations={citations} />);

    expect(screen.queryByRole("button", { name: /used/i })).not.toBeInTheDocument();
  });

  it("does not render citation accordion when citations are empty", () => {
    render(<AiMessageBubble role="assistant" text="Answer" citations={[]} />);

    expect(screen.queryByRole("button", { name: /used/i })).not.toBeInTheDocument();
  });

  it("opens matching citation when inline [n] reference is clicked", async () => {
    const user = userEvent.setup();
    const scrollIntoViewSpy = vi.fn();
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoViewSpy,
    });
    const citations: Citation[] = [
      {
        document_id: "doc-1",
        chunk_id: "c1",
        page_number: 5,
        supporting_quote: "Relevant excerpt from the document.",
        source_tool: "bm25",
      },
    ];

    try {
      render(
        <AiMessageBubble
          role="assistant"
          text="The answer is grounded in evidence [1]."
          citations={citations}
        />
      );

      expect(screen.queryByText(/relevant excerpt/i)).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "[1]" }));

      await waitFor(() => {
        expect(screen.getByText(/relevant excerpt/i)).toBeInTheDocument();
      });
      await waitFor(
        () => {
          expect(scrollIntoViewSpy).toHaveBeenCalledTimes(2);
        },
        { timeout: 400 }
      );
    } finally {
      if (originalScrollIntoView) {
        Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
          configurable: true,
          value: originalScrollIntoView,
        });
      } else {
        delete (HTMLElement.prototype as { scrollIntoView?: unknown }).scrollIntoView;
      }
    }
  });
});
