# RAG UI Specification (Frontend Planning)

- Date: 2026-02-17
- Branch: `feature/spec-frontend-rag`

## Scope

- Deliver planning-ready frontend specs for:
  - dark redesign + typography system
  - structured JSON response parsing + citation rendering
  - hybrid retrieval routing alignment across upload + chat flows
- Keep tasks in planning state (`status: todo`) with explicit TDD and validation criteria.

## Decisions and Traceability

- UI system decision: `frontend/adrs/0002-dark-theme-typography-design-system.md`
- Structured rendering and mode routing decision: `frontend/adrs/0003-structured-chat-rendering-and-mode-routing.md`

## Task Breakdown

- `frontend/tasks/FE-2026-02-17-002.json`: dark visual redesign + tokenized typography system
- `frontend/tasks/FE-2026-02-17-003.json`: backend JSON parsing + readable chat/citation rendering
- `frontend/tasks/FE-2026-02-17-004.json`: retrieval routing + backend mode forwarding + optional agent-event extensibility

## Shared Frontend-Backend Contract (Planned)

```json
{
  "request": {
    "prompt": "string",
    "retrieval_mode": "hybrid",
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

Runtime note:
- Frontend runtime should always send `retrieval_mode: "hybrid"` for chat/upload flows.
- Response `mode` remains enum-compatible because backend contracts and stored history may still include `embedded|vector|hybrid`.

## Validation Mandate

- TDD first: failing unit/component/integration tests before implementation.
- Integration tests must cover backend response contracts and hybrid mode forwarding.
- Playwright manual checklist execution is required for:
  - dark-mode typography rendering
  - citation visibility/traceability
  - sources panel behavior (hidden by default, animated expand/collapse, readable labels)
  - optional unknown agent-event fallback
- Citation UI validation must assert:
  - no raw chunk/document ids are rendered as primary body text in source cards
  - mixed-source rendering works (`bm25_search` and `openai_vector_store_search` labels)
