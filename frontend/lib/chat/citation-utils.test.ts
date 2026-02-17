import { describe, expect, it } from "vitest";

import { dedupeCitations, formatCitationId, truncateQuote } from "./citation-utils";


describe("citation-utils", () => {
  it("dedupeCitations removes duplicates while keeping order", () => {
    const citations = [
      {
        document_id: "doc",
        chunk_id: "c1",
        page_number: 0,
        supporting_quote: "a",
        source_tool: "bm25",
      },
      {
        document_id: "doc",
        chunk_id: "c1",
        page_number: 0,
        supporting_quote: "a",
        source_tool: "bm25",
      },
      {
        document_id: "doc",
        chunk_id: "c2",
        page_number: 1,
        supporting_quote: "b",
        source_tool: "bm25",
      },
    ];

    const deduped = dedupeCitations(citations);
    expect(deduped).toHaveLength(2);
    expect(deduped[0].chunk_id).toBe("c1");
    expect(deduped[1].chunk_id).toBe("c2");
  });

  it("truncateQuote clamps long text", () => {
    const quote = "x".repeat(300);
    const truncated = truncateQuote(quote, 120);
    expect(truncated.length).toBeLessThanOrEqual(121);
    expect(truncated.endsWith("…")).toBe(true);
  });

  it("formatCitationId includes document and chunk", () => {
    const id = formatCitationId({
      document_id: "doc",
      chunk_id: "chunk",
      page_number: 2,
      supporting_quote: "q",
      source_tool: "bm25",
    });

    expect(id).toContain("doc");
    expect(id).toContain("chunk");
    expect(id).toContain("p2");
  });
});
