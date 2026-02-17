import type { Citation } from "@/lib/chat/structured-response";

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
  const seenChunkKeys = new Set<string>();
  const seenQuoteKeys = new Set<string>();
  const out: Citation[] = [];

  for (const c of citations) {
    const chunkKey = `${c.document_id}::${c.chunk_id}::${c.page_number ?? ""}`;
    if (seenChunkKeys.has(chunkKey)) continue;

    const fingerprint = quoteFingerprint(c.supporting_quote);
    const quoteKey = `${c.document_id}::${fingerprint}`;
    if (fingerprint && seenQuoteKeys.has(quoteKey)) continue;

    seenChunkKeys.add(chunkKey);
    if (fingerprint) seenQuoteKeys.add(quoteKey);
    out.push(c);
  }

  return out;
}

export function formatCitationId(citation: Citation): string {
  const page = citation.page_number == null ? "" : `p${citation.page_number}`;
  return [citation.document_id, page, citation.chunk_id].filter(Boolean).join(" · ");
}
