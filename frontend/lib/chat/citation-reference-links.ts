const CITATION_REFERENCE_ID_PREFIX = "citation-ref";
const CITATION_REFERENCE_MARKER_PATTERN = /(?<!\[)\[(\d+)\](?![\]\(:])/g;

function normalizeCitationScopeId(scopeId: string): string {
  return scopeId.replace(/[^a-zA-Z0-9_-]/g, "-");
}

export function buildCitationReferenceElementId(scopeId: string, index: number): string {
  return `${CITATION_REFERENCE_ID_PREFIX}-${normalizeCitationScopeId(scopeId)}-${index}`;
}

export function buildCitationReferenceHref(scopeId: string, index: number): string {
  return `#${buildCitationReferenceElementId(scopeId, index)}`;
}

export function parseCitationReferenceHref(
  href: string | null | undefined,
  scopeId: string,
): number | null {
  if (!href || !href.startsWith("#")) return null;
  const fragment = decodeURIComponent(href.slice(1));
  const expectedPrefix = `${CITATION_REFERENCE_ID_PREFIX}-${normalizeCitationScopeId(scopeId)}-`;
  if (!fragment.startsWith(expectedPrefix)) return null;

  const rawIndex = fragment.slice(expectedPrefix.length);
  if (!/^\d+$/.test(rawIndex)) return null;

  const index = Number.parseInt(rawIndex, 10);
  return Number.isInteger(index) && index > 0 ? index : null;
}

export function injectCitationReferenceLinks(
  text: string,
  options: { scopeId: string; maxIndex: number },
): string {
  const { maxIndex, scopeId } = options;
  if (maxIndex <= 0) return text;

  return text.replace(CITATION_REFERENCE_MARKER_PATTERN, (match, rawIndex) => {
    const index = Number.parseInt(rawIndex, 10);
    if (!Number.isInteger(index) || index < 1 || index > maxIndex) return match;

    return `[[${index}]](${buildCitationReferenceHref(scopeId, index)})`;
  });
}
