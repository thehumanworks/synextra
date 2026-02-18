import { describe, expect, it } from "vitest";

import {
  splitStreamedText,
  STREAM_METADATA_SEPARATOR,
  STREAM_EVENTS_SEPARATOR,
} from "./stream-metadata";

function buildStreamedPayload(
  answer: string,
  citations: Record<string, unknown>[],
): string {
  const meta = JSON.stringify({ citations, mode: "hybrid", tools_used: ["bm25"] });
  return answer + STREAM_METADATA_SEPARATOR + meta;
}

function buildStreamedPayloadWithEvents(
  events: Record<string, unknown>[],
  answer: string,
  citations: Record<string, unknown>[],
): string {
  const eventLines = events.map((e) => JSON.stringify(e)).join("\n");
  const meta = JSON.stringify({ citations, mode: "hybrid", tools_used: ["bm25"] });
  return eventLines + STREAM_EVENTS_SEPARATOR + answer + STREAM_METADATA_SEPARATOR + meta;
}

describe("splitStreamedText", () => {
  it("returns raw text and empty citations when no separator is present", () => {
    const result = splitStreamedText("plain answer text");

    expect(result.text).toBe("plain answer text");
    expect(result.citations).toEqual([]);
    expect(result.events).toEqual([]);
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
    expect(result.events).toEqual([]);
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

  // Three-phase protocol tests

  it("parses events when events separator is present before answer", () => {
    const raw = buildStreamedPayloadWithEvents(
      [
        { event: "search", tool: "bm25_search", query: "what is entropy", timestamp: "2024-01-01T00:00:00Z" },
      ],
      "The answer.",
      [],
    );

    const result = splitStreamedText(raw);

    expect(result.events).toHaveLength(1);
    expect(result.events[0].event).toBe("search");
    expect(result.events[0].tool).toBe("bm25_search");
    expect(result.events[0].query).toBe("what is entropy");
    expect(result.text).toBe("The answer.");
    expect(result.citations).toEqual([]);
  });

  it("parses multiple events of different types", () => {
    const raw = buildStreamedPayloadWithEvents(
      [
        { event: "search", tool: "bm25_search", query: "entropy", timestamp: "2024-01-01T00:00:01Z" },
        { event: "search", tool: "read_document", page: 3, timestamp: "2024-01-01T00:00:02Z" },
        { event: "review", iteration: 1, verdict: "approved", timestamp: "2024-01-01T00:00:03Z" },
      ],
      "Final answer.",
      [
        {
          document_id: "doc-1",
          chunk_id: "c1",
          page_number: 3,
          supporting_quote: "relevant excerpt",
          source_tool: "bm25",
        },
      ],
    );

    const result = splitStreamedText(raw);

    expect(result.events).toHaveLength(3);
    expect(result.events[0].event).toBe("search");
    expect(result.events[0].tool).toBe("bm25_search");
    expect(result.events[1].event).toBe("search");
    expect(result.events[1].page).toBe(3);
    expect(result.events[2].event).toBe("review");
    expect(result.events[2].verdict).toBe("approved");
    expect(result.text).toBe("Final answer.");
    expect(result.citations).toHaveLength(1);
  });

  it("parses review rejected event with feedback", () => {
    const raw = buildStreamedPayloadWithEvents(
      [
        {
          event: "review",
          iteration: 1,
          verdict: "rejected",
          feedback: "Missing key detail",
          timestamp: "2024-01-01T00:00:01Z",
        },
      ],
      "Revised answer.",
      [],
    );

    const result = splitStreamedText(raw);

    expect(result.events).toHaveLength(1);
    expect(result.events[0].verdict).toBe("rejected");
    expect(result.events[0].feedback).toBe("Missing key detail");
    expect(result.events[0].iteration).toBe(1);
  });

  it("returns empty events array when no events separator is present", () => {
    const raw = buildStreamedPayload("answer without events", []);

    const result = splitStreamedText(raw);

    expect(result.events).toEqual([]);
    expect(result.text).toBe("answer without events");
  });

  it("skips malformed event lines gracefully", () => {
    const eventLines =
      '{"event":"search","tool":"bm25","query":"foo","timestamp":"2024-01-01T00:00:00Z"}\n' +
      "not-valid-json\n" +
      '{"event":"review","verdict":"approved","timestamp":"2024-01-01T00:00:01Z","iteration":1}';

    const meta = JSON.stringify({ citations: [], mode: "hybrid", tools_used: [] });
    const raw =
      eventLines +
      STREAM_EVENTS_SEPARATOR +
      "answer" +
      STREAM_METADATA_SEPARATOR +
      meta;

    const result = splitStreamedText(raw);

    expect(result.events).toHaveLength(2);
    expect(result.events[0].tool).toBe("bm25");
    expect(result.events[1].verdict).toBe("approved");
    expect(result.text).toBe("answer");
  });

  it("handles events-only stream with no metadata separator yet (mid-stream)", () => {
    const eventLines =
      '{"event":"search","tool":"bm25_search","query":"test","timestamp":"2024-01-01T00:00:00Z"}';
    const raw = eventLines + STREAM_EVENTS_SEPARATOR + "partial answer so far";

    const result = splitStreamedText(raw);

    expect(result.events).toHaveLength(1);
    expect(result.events[0].tool).toBe("bm25_search");
    expect(result.text).toBe("partial answer so far");
    expect(result.citations).toEqual([]);
  });

  it("ignores unknown event types in events section", () => {
    const eventLines =
      '{"event":"unknown_type","timestamp":"2024-01-01T00:00:00Z"}\n' +
      '{"event":"search","tool":"bm25","query":"q","timestamp":"2024-01-01T00:00:01Z"}';
    const meta = JSON.stringify({ citations: [], mode: "hybrid", tools_used: [] });
    const raw =
      eventLines +
      STREAM_EVENTS_SEPARATOR +
      "answer" +
      STREAM_METADATA_SEPARATOR +
      meta;

    const result = splitStreamedText(raw);

    expect(result.events).toHaveLength(1);
    expect(result.events[0].event).toBe("search");
  });
});
