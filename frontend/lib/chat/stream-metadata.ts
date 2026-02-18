import type { Citation } from "@/lib/chat/structured-response";
import { CitationSchema } from "@/lib/chat/structured-response";

export const STREAM_METADATA_SEPARATOR = "\x1e";

export function splitStreamedText(raw: string): { text: string; citations: Citation[] } {
  const idx = raw.lastIndexOf(STREAM_METADATA_SEPARATOR);
  if (idx === -1) return { text: raw, citations: [] };

  const text = raw.slice(0, idx);
  try {
    const meta = JSON.parse(raw.slice(idx + 1)) as Record<string, unknown>;
    const rawCitations = Array.isArray(meta?.citations) ? meta.citations : [];
    const citations: Citation[] = [];
    for (const c of rawCitations) {
      const parsed = CitationSchema.safeParse(c);
      if (parsed.success) citations.push(parsed.data);
    }
    return { text, citations };
  } catch {
    return { text: raw, citations: [] };
  }
}
