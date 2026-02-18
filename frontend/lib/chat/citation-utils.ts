import type { Citation } from "@/lib/chat/structured-response";

export type DedupedCitationWithReferenceIndices = {
  citation: Citation;
  referenceIndices: number[];
};

export function truncateQuote(quote: string, maxLen = 200): string {
  const cleaned = quote.replace(/\s+/g, " ").trim();
  if (cleaned.length <= maxLen) return cleaned;
  return `${cleaned.slice(0, maxLen).trim()}…`;
}

function normalizeQuoteForKey(quote: string): string {
  return quote.replace(/\s+/g, " ").trim().toLowerCase();
}

function quoteFingerprint(quote: string, prefixLen = 160): string {
  const normalized = normalizeQuoteForKey(quote);
  if (normalized.length <= prefixLen) return normalized;
  return normalized.slice(0, prefixLen);
}

export function dedupeCitations(citations: Citation[]): Citation[] {
  return dedupeCitationsWithReferenceIndices(citations).map((entry) => entry.citation);
}

export function dedupeCitationsWithReferenceIndices(
  citations: Citation[],
): DedupedCitationWithReferenceIndices[] {
  const seenChunkKeyToIndex = new Map<string, number>();
  const seenQuoteKeyToIndex = new Map<string, number>();
  const out: DedupedCitationWithReferenceIndices[] = [];

  for (const [idx, c] of citations.entries()) {
    const referenceIndex = idx + 1;
    const chunkKey = `${c.document_id}::${c.chunk_id}::${c.page_number ?? ""}`;
    const existingByChunk = seenChunkKeyToIndex.get(chunkKey);
    if (existingByChunk != null) {
      out[existingByChunk].referenceIndices.push(referenceIndex);
      continue;
    }

    const fingerprint = quoteFingerprint(c.supporting_quote);
    const quoteKey = `${c.document_id}::${fingerprint}`;
    if (fingerprint) {
      const existingByQuote = seenQuoteKeyToIndex.get(quoteKey);
      if (existingByQuote != null) {
        out[existingByQuote].referenceIndices.push(referenceIndex);
        continue;
      }
    }

    const outIndex = out.length;
    seenChunkKeyToIndex.set(chunkKey, outIndex);
    if (fingerprint) seenQuoteKeyToIndex.set(quoteKey, outIndex);
    out.push({ citation: c, referenceIndices: [referenceIndex] });
  }

  return out;
}

export function formatReferenceIndices(referenceIndices: number[]): string {
  return referenceIndices.map((idx) => `[${idx}]`).join(", ");
}

export function formatCitationId(citation: Citation): string {
  const page = citation.page_number == null ? "" : `p${citation.page_number}`;
  return [citation.document_id, page, citation.chunk_id].filter(Boolean).join(" · ");
}
