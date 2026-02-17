import type { Citation } from "@/lib/chat/structured-response";

export function truncateQuote(quote: string, maxLen = 200): string {
  const cleaned = quote.replace(/\s+/g, " ").trim();
  if (cleaned.length <= maxLen) return cleaned;
  return `${cleaned.slice(0, maxLen).trim()}…`;
}

export function dedupeCitations(citations: Citation[]): Citation[] {
  const seen = new Set<string>();
  const out: Citation[] = [];

  for (const c of citations) {
    const key = `${c.document_id}::${c.chunk_id}::${c.page_number ?? ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(c);
  }

  return out;
}

export function formatCitationId(citation: Citation): string {
  const page = citation.page_number == null ? "" : `p${citation.page_number}`;
  return [citation.document_id, page, citation.chunk_id].filter(Boolean).join(" · ");
}
