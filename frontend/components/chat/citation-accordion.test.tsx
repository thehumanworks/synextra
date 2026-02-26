import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Citation } from "@/lib/chat/structured-response";

import { CitationAccordion } from "./citation-accordion";

const CITATIONS: Citation[] = [
  {
    document_id: "doc-1",
    chunk_id: "c1",
    page_number: 3,
    supporting_quote: "The attention mechanism allows the model to focus on relevant parts.",
    source_tool: "bm25",
  },
  {
    document_id: "doc-1",
    chunk_id: "c2",
    page_number: 7,
    supporting_quote: "Multi-head attention enables joint information from different subspaces.",
    source_tool: "vector",
  },
];

describe("CitationAccordion", () => {
  it("renders nothing when citations are empty", () => {
    const { container } = render(<CitationAccordion citations={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the source count button", () => {
    render(<CitationAccordion citations={CITATIONS} />);
    expect(screen.getByRole("button", { name: /used 2 sources/i })).toBeInTheDocument();
  });

  it("does not show citation cards by default", () => {
    render(<CitationAccordion citations={CITATIONS} />);
    expect(screen.queryByText(/attention mechanism/i)).not.toBeInTheDocument();
  });

  it("expands to show citation cards on click", async () => {
    const user = userEvent.setup();
    render(<CitationAccordion citations={CITATIONS} />);

    await user.click(screen.getByRole("button", { name: /used 2 sources/i }));

    expect(screen.getByText("[1]")).toBeInTheDocument();
    expect(screen.getByText("[2]")).toBeInTheDocument();
    expect(screen.getByText(/attention mechanism/i)).toBeInTheDocument();
    expect(screen.getByText(/multi-head attention/i)).toBeInTheDocument();
    expect(screen.getByText("Page 3")).toBeInTheDocument();
    expect(screen.getByText("Page 7")).toBeInTheDocument();
  });

  it("keeps citation indices from original order even when cards dedupe", async () => {
    const user = userEvent.setup();
    render(
      <CitationAccordion
        referenceScopeId="dedupe"
        citations={[
          {
            document_id: "doc-1",
            chunk_id: "c1",
            page_number: 3,
            supporting_quote: "Same quote from doc one.",
            source_tool: "bm25",
          },
          {
            document_id: "doc-1",
            chunk_id: "c2",
            page_number: 4,
            supporting_quote: "Same quote from doc one.",
            source_tool: "vector",
          },
        ]}
      />
    );

    await user.click(screen.getByRole("button", { name: /used 2 sources/i }));

    expect(document.getElementById("citation-ref-dedupe-1")).toBeInTheDocument();
    expect(document.getElementById("citation-ref-dedupe-2")).toBeInTheDocument();
  });

  it("shows singular 'source' for a single citation", () => {
    render(<CitationAccordion citations={[CITATIONS[0]]} />);
    expect(screen.getByRole("button", { name: /used 1 source$/i })).toBeInTheDocument();
  });

  it("auto-expands and focuses source when a reference index is requested", async () => {
    const onFocusReferenceHandled = vi.fn();
    render(
      <CitationAccordion
        citations={CITATIONS}
        referenceScopeId="message-1"
        focusReferenceIndex={2}
        onFocusReferenceHandled={onFocusReferenceHandled}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/multi-head attention/i)).toBeInTheDocument();
    });
    expect(document.getElementById("citation-ref-message-1-2")).toBeInTheDocument();
    await waitFor(() => {
      expect(onFocusReferenceHandled).toHaveBeenCalledTimes(1);
    });
  });

  it("opens a modal with the full citation excerpt", async () => {
    const user = userEvent.setup();
    const longQuote = `${"Long source detail ".repeat(30)}`.trim();
    render(
      <CitationAccordion
        citations={[
          {
            document_id: "doc-1",
            chunk_id: "c1",
            page_number: 2,
            supporting_quote: longQuote,
            source_tool: "bm25",
          },
        ]}
      />
    );

    await user.click(screen.getByRole("button", { name: /used 1 source/i }));
    await user.click(screen.getByRole("button", { name: /expand excerpt/i }));

    expect(screen.getByRole("dialog", { name: /citation detail/i })).toBeInTheDocument();
    expect(screen.getByText(longQuote)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /close/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /citation detail/i })).not.toBeInTheDocument();
    });
  });
});
