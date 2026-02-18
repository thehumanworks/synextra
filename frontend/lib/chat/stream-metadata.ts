import type { Citation } from "@/lib/chat/structured-response";
import { CitationSchema } from "@/lib/chat/structured-response";

export const STREAM_METADATA_SEPARATOR = "\x1e";
export const STREAM_EVENTS_SEPARATOR = "\x1d";

export type StreamEvent = {
  event: "search" | "reasoning" | "review";
  tool?: string;
  query?: string;
  page?: number;
  content?: string;
  iteration?: number;
  verdict?: "approved" | "rejected";
  feedback?: string;
  timestamp: string;
};

export function parseEventLine(line: string): StreamEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  try {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    if (
      typeof parsed.event !== "string" ||
      typeof parsed.timestamp !== "string"
    ) {
      return null;
    }
    const eventType = parsed.event;
    if (
      eventType !== "search" &&
      eventType !== "reasoning" &&
      eventType !== "review"
    ) {
      return null;
    }
    const ev: StreamEvent = {
      event: eventType,
      timestamp: parsed.timestamp,
    };
    if (typeof parsed.tool === "string") ev.tool = parsed.tool;
    if (typeof parsed.query === "string") ev.query = parsed.query;
    if (typeof parsed.page === "number") ev.page = parsed.page;
    if (typeof parsed.content === "string") ev.content = parsed.content;
    if (typeof parsed.iteration === "number") ev.iteration = parsed.iteration;
    if (parsed.verdict === "approved" || parsed.verdict === "rejected") {
      ev.verdict = parsed.verdict;
    }
    if (typeof parsed.feedback === "string") ev.feedback = parsed.feedback;
    return ev;
  } catch {
    return null;
  }
}

export function splitStreamedText(raw: string): {
  text: string;
  citations: Citation[];
  events: StreamEvent[];
} {
  const eventsIdx = raw.indexOf(STREAM_EVENTS_SEPARATOR);

  let events: StreamEvent[] = [];
  let rest: string;

  if (eventsIdx !== -1) {
    const eventsSection = raw.slice(0, eventsIdx);
    rest = raw.slice(eventsIdx + 1);

    events = eventsSection
      .split("\n")
      .map(parseEventLine)
      .filter((e): e is StreamEvent => e !== null);
  } else {
    rest = raw;
  }

  const metaIdx = rest.lastIndexOf(STREAM_METADATA_SEPARATOR);
  if (metaIdx === -1) return { text: rest, citations: [], events };

  const text = rest.slice(0, metaIdx);
  try {
    const meta = JSON.parse(rest.slice(metaIdx + 1)) as Record<string, unknown>;
    const rawCitations = Array.isArray(meta?.citations) ? meta.citations : [];
    const citations: Citation[] = [];
    for (const c of rawCitations) {
      const parsed = CitationSchema.safeParse(c);
      if (parsed.success) citations.push(parsed.data);
    }
    return { text, citations, events };
  } catch {
    return { text: raw, citations: [], events: [] };
  }
}
