import { describe, expect, it } from "vitest";

import { splitStreamedText, STREAM_METADATA_SEPARATOR } from "./stream-metadata";

function buildStreamedPayload(
  answer: string,
  citations: Record<string, unknown>[],
): string {
  const meta = JSON.stringify({ citations, mode: "hybrid", tools_used: ["bm25"] });
  return answer + STREAM_METADATA_SEPARATOR + meta;
}

describe("splitStreamedText", () => {
  it("returns raw text and empty citations when no separator is present", () => {
    const result = splitStreamedText("plain answer text");

    expect(result.text).toBe("plain answer text");
    expect(result.citations).toEqual([]);
  });

  it("parses answer and citations from a valid trailer", () => {
    const raw = buildStreamedPayload("The answer.", [
      {
        document_id: "doc-1",
        chunk_id: "c1",
        page_number: 3,
        supporting_quote: "relevant excerpt",
        source_tool: "bm25",
      },
    ]);

    const result = splitStreamedText(raw);

    expect(result.text).toBe("The answer.");
    expect(result.citations).toHaveLength(1);
    expect(result.citations[0].document_id).toBe("doc-1");
    expect(result.citations[0].page_number).toBe(3);
  });

  it("handles multiple citations", () => {
    const raw = buildStreamedPayload("answer", [
      {
        document_id: "d1",
        chunk_id: "c1",
        page_number: 1,
        supporting_quote: "quote one",
        source_tool: "bm25",
      },
      {
        document_id: "d1",
        chunk_id: "c2",
        page_number: 2,
        supporting_quote: "quote two",
        source_tool: "vector",
      },
    ]);

    const result = splitStreamedText(raw);

    expect(result.text).toBe("answer");
    expect(result.citations).toHaveLength(2);
  });

  it("skips citations that fail schema validation", () => {
    const raw = buildStreamedPayload("answer", [
      {
        document_id: "doc-1",
        chunk_id: "c1",
        page_number: 3,
        supporting_quote: "valid",
        source_tool: "bm25",
      },
      { bad: "data" },
    ]);

    const result = splitStreamedText(raw);

    expect(result.citations).toHaveLength(1);
    expect(result.citations[0].chunk_id).toBe("c1");
  });

  it("returns raw text on malformed JSON trailer", () => {
    const raw = "answer text" + STREAM_METADATA_SEPARATOR + "not-json{{{";

    const result = splitStreamedText(raw);

    expect(result.text).toBe("answer text" + STREAM_METADATA_SEPARATOR + "not-json{{{");
    expect(result.citations).toEqual([]);
  });

  it("handles empty citations array in trailer", () => {
    const raw = buildStreamedPayload("no sources", []);

    const result = splitStreamedText(raw);

    expect(result.text).toBe("no sources");
    expect(result.citations).toEqual([]);
  });

  it("handles answer text containing newlines and markdown", () => {
    const answer = "# Heading\n\nParagraph with **bold**.\n\n- item 1\n- item 2";
    const raw = buildStreamedPayload(answer, [
      {
        document_id: "doc",
        chunk_id: "c1",
        page_number: null,
        supporting_quote: "a quote",
        source_tool: "bm25",
      },
    ]);

    const result = splitStreamedText(raw);

    expect(result.text).toBe(answer);
    expect(result.citations).toHaveLength(1);
  });
});
