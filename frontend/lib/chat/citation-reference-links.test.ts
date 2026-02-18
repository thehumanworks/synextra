import { describe, expect, it } from "vitest";

import {
  buildCitationReferenceElementId,
  buildCitationReferenceHref,
  injectCitationReferenceLinks,
  parseCitationReferenceHref,
} from "./citation-reference-links";

describe("citation-reference-links", () => {
  it("injects scoped links for in-range references", () => {
    const result = injectCitationReferenceLinks("Claim [1] and [2].", {
      scopeId: "message-1",
      maxIndex: 2,
    });

    expect(result).toContain("[[1]](#citation-ref-message-1-1)");
    expect(result).toContain("[[2]](#citation-ref-message-1-2)");
  });

  it("does not rewrite out-of-range or existing link syntax", () => {
    const result = injectCitationReferenceLinks("Keep [3] and existing [[1]](#citation-ref-message-1-1).", {
      scopeId: "message-1",
      maxIndex: 2,
    });

    expect(result).toContain("Keep [3]");
    expect(result).toContain("[[1]](#citation-ref-message-1-1)");
  });

  it("builds and parses matching reference href values", () => {
    const href = buildCitationReferenceHref("message-2", 4);

    expect(parseCitationReferenceHref(href, "message-2")).toBe(4);
    expect(parseCitationReferenceHref(href, "different-message")).toBeNull();
  });

  it("normalizes scope ids for safe element targets", () => {
    expect(buildCitationReferenceElementId("scope:with spaces", 1)).toBe(
      "citation-ref-scope-with-spaces-1"
    );
  });
});
