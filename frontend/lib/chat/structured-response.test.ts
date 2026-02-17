import { describe, expect, it, vi } from "vitest";

import { parseStructuredResponse } from "./structured-response";


describe("parseStructuredResponse", () => {
  it("falls back to plain text when JSON is malformed", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    const parsed = parseStructuredResponse("{not json", {
      fallbackMode: "embedded",
      sessionId: "s",
    });

    expect(parsed.parseMeta.ok).toBe(false);
    expect(parsed.answer).toBe("{not json");
    expect(parsed.mode).toBe("embedded");
    expect(parsed.citations).toHaveLength(0);

    warn.mockRestore();
  });

  it("uses safe fallback when mode is unknown", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    const parsed = parseStructuredResponse({
      session_id: "s",
      mode: "something-else",
      answer: "hello",
      citations: [],
    });

    expect(parsed.mode).toBe("hybrid");
    expect(parsed.parseMeta.usedModeFallback).toBe(true);

    warn.mockRestore();
  });

  it("parses well-formed response", () => {
    const parsed = parseStructuredResponse({
      session_id: "s",
      mode: "hybrid",
      answer: "hello",
      tools_used: ["bm25"],
      citations: [
        {
          document_id: "d",
          chunk_id: "c",
          page_number: 1,
          supporting_quote: "quote",
          source_tool: "bm25",
        },
      ],
    });

    expect(parsed.sessionId).toBe("s");
    expect(parsed.mode).toBe("hybrid");
    expect(parsed.citations).toHaveLength(1);
    expect(parsed.citations[0].document_id).toBe("d");
  });

  it("accepts citation link metadata when present", () => {
    const parsed = parseStructuredResponse({
      session_id: "s",
      mode: "embedded",
      answer: "hello",
      citations: [
        {
          document_id: "d",
          chunk_id: "c",
          page_number: 1,
          supporting_quote: "quote",
          source_tool: "bm25",
          title: "Transformer paper",
          url: "https://example.com/transformer",
        },
      ],
    });

    expect(parsed.parseMeta.ok).toBe(true);
    expect(parsed.citations).toHaveLength(1);
    expect(parsed.citations[0].title).toBe("Transformer paper");
    expect(parsed.citations[0].url).toBe("https://example.com/transformer");
  });
});
