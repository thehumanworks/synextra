# ADR 0005: Clickable Citation References and Expandable Source Modal

- Status: Accepted
- Date: 2026-02-18

## Context

RAG answers include inline numeric references (`[1]`, `[2]`, ...), but users still had to manually scan the sources accordion to map each marker to a citation card. Two usability gaps remained:

- inline reference markers were not actionable
- citation cards showed truncated excerpts only, making it hard to inspect full source context

The fix needed to work in both render paths:

- streaming chat bubbles (`AiMessageBubble`)
- structured response cards (`StructuredMessage`)

## Decision

We adopted a scoped reference-navigation model plus an on-demand citation modal:

1. Scoped inline reference linking
- Add `injectCitationReferenceLinks()` to rewrite valid `[n]` markers into internal markdown links using a per-message scope id.
- Preserve non-citation bracketed content by rewriting only in-range citation markers.

2. Citation-aware markdown link handling
- In `MarkdownResponse`, override `Streamdown` link rendering (`components.a`) when citation callbacks are provided.
- Citation links dispatch `onCitationReferenceClick(index)` instead of navigating.
- Non-citation links remain external anchors (`target="_blank"`, `rel="noreferrer"`).

3. Source accordion focus behavior
- `CitationAccordion` now supports `referenceScopeId`, `focusReferenceIndex`, and `onFocusReferenceHandled`.
- On citation click, the accordion auto-expands, scrolls to the matching source tag, and briefly highlights it.

4. Full excerpt modal
- Add an expandable modal (`role="dialog"`) per citation card via `Expand excerpt`.
- Modal shows full `supporting_quote` plus reference tags and source metadata.

## Alternatives Considered

1. Keep static `[n]` text and only show mapping labels in source cards
- Rejected because users still need manual visual matching and scrolling.

2. Use global hash navigation/events without scoped ids
- Rejected because multi-message chat threads can collide on shared ids (`[1]` appears in many messages), causing incorrect jumps.

3. Expand full citation text inline in each card by default
- Rejected because it increases vertical noise and hurts scanability of multi-source answers.

## Consequences

- Pros:
  - users can jump directly from inline evidence markers to the corresponding source card
  - source detail remains concise by default while preserving full-context access in modal
  - behavior is consistent across streaming and structured rendering paths

- Trade-offs:
  - citation rendering now includes scoped id and focus state plumbing
  - markdown reference rewriting is pattern-based and tied to `[n]` citation conventions

## Follow-up Actions

- Consider rendering citation reference chips as keyboard-focus targets with explicit skip links when accessibility audits require stronger source-navigation affordances.
- If backend introduces richer reference formats (for example ranges or grouped claims), extend the rewriting/parser helpers to cover those forms without regex-only assumptions.
