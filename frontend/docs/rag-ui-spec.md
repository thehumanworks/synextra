# RAG UI Specification (Frontend Planning)

- Date: 2026-02-17
- Branch: `feature/spec-frontend-rag`

## Scope

- Deliver planning-ready frontend specs for:
  - dark redesign + typography system
  - structured JSON response parsing + citation rendering
  - retrieval-mode selector + backend routing integration
- Keep tasks in planning state (`status: todo`) with explicit TDD and validation criteria.

## Decisions and Traceability

- UI system decision: `frontend/adrs/0002-dark-theme-typography-design-system.md`
- Structured rendering and mode routing decision: `frontend/adrs/0003-structured-chat-rendering-and-mode-routing.md`

## Task Breakdown

- `frontend/tasks/FE-2026-02-17-002.json`: dark visual redesign + tokenized typography system
- `frontend/tasks/FE-2026-02-17-003.json`: backend JSON parsing + readable chat/citation rendering
- `frontend/tasks/FE-2026-02-17-004.json`: retrieval mode selector + backend mode forwarding + agent-event extensibility

## Shared Frontend-Backend Contract (Planned)

```json
{
  "request": {
    "prompt": "string",
    "retrieval_mode": "semantic|hybrid|keyword|agentic"
  },
  "response": {
    "mode": "semantic|hybrid|keyword|agentic",
    "blocks": [
      { "type": "text", "content": "..." },
      { "type": "tool_output", "content": "..." }
    ],
    "citations": [
      { "id": "c1", "title": "Source title", "url": "https://..." }
    ],
    "agent_events": [
      { "type": "verifier", "summary": "..." },
      { "type": "fixer", "summary": "..." }
    ]
  }
}
```

## Validation Mandate

- TDD first: failing unit/component/integration tests before implementation.
- Integration tests must cover backend response contracts and mode forwarding.
- Playwright manual checklist execution is required for:
  - dark-mode typography rendering
  - citation visibility/traceability
  - mode switching and unknown agent-event fallback
