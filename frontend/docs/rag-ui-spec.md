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
- `frontend/tasks/FE-2026-02-17-004.json`: retrieval mode selector + backend mode forwarding + optional agent-event extensibility

## Shared Frontend-Backend Contract (Planned)

```json
{
  "request": {
    "prompt": "string",
    "retrieval_mode": "embedded|vector|hybrid",
    "session_id": "string"
  },
  "response": {
    "answer": "string",
    "mode": "embedded|vector|hybrid",
    "tools_used": ["string"],
    "session_id": "string",
    "citations": [
      {
        "document_id": "string",
        "page_number": 1,
        "chunk_id": "string",
        "supporting_quote": "string"
      }
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
- Integration tests must cover backend response contracts and mode forwarding with enum parity (`embedded|vector|hybrid`).
- Playwright manual checklist execution is required for:
  - dark-mode typography rendering
  - citation visibility/traceability
  - mode switching and optional unknown agent-event fallback
