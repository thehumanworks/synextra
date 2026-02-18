import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

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

    expect(screen.getByText(/attention mechanism/i)).toBeInTheDocument();
    expect(screen.getByText(/multi-head attention/i)).toBeInTheDocument();
    expect(screen.getByText("Page 3")).toBeInTheDocument();
    expect(screen.getByText("Page 7")).toBeInTheDocument();
  });

  it("shows singular 'source' for a single citation", () => {
    render(<CitationAccordion citations={[CITATIONS[0]]} />);
    expect(screen.getByRole("button", { name: /used 1 source$/i })).toBeInTheDocument();
  });
});
