# Spec Review Report

- Date: 2026-02-17
- Reviewer branch: `feature/spec-review-rag`
- Reviewed branches:
  - `feature/spec-backend-rag`
  - `feature/spec-frontend-rag`

## Findings (Ordered by Severity)

1. **Blocking (Fixed in this review branch): Frontend/backend RAG contract drift on mode enum and response shape.**

- Evidence (backend):
  - `backend/adrs/0003-dual-store-retrieval-and-agent-orchestration.md` defines modes `embedded|vector|hybrid`.
  - `backend/tasks/BE-2026-02-17-004.json` requires response fields `answer`, `citations`, `mode`, `tools_used`, `session_id` and citation fields `document_id`, `page_number`, `chunk_id`, `supporting_quote`.
- Evidence (frontend before fix):
  - `frontend/docs/rag-ui-spec.md` defined request/response mode enum `semantic|hybrid|keyword|agentic`.
  - `frontend/docs/rag-ui-spec.md` and `frontend/adrs/0003-structured-chat-rendering-and-mode-routing.md` modeled response around `blocks` (and implicitly required metadata not in backend v1 contract).
- Impact:
  - Frontend parser/routing tests and backend contract tests could not simultaneously pass.
  - Mode selection and citation rendering expectations were inconsistent across teams.
- Fixes applied in this branch:
  - Aligned frontend contract docs/specs to backend enum and response fields.
  - Updated associated frontend task test language to validate the shared contract.

## Changed Files in This Review Branch

- `frontend/adrs/0003-structured-chat-rendering-and-mode-routing.md`
- `frontend/docs/rag-ui-spec.md`
- `frontend/tasks/FE-2026-02-17-003.json`
- `frontend/tasks/FE-2026-02-17-004.json`
- `AGENTS.md` (added durable guidance to enforce cross-stack contract parity)

## Validation / Checks

- JSON validity (`jq`) on reviewed task files: **pass**.
- Schema key presence checks for new backend/frontend task JSON contracts: **pass**.
- Prettier check on changed frontend markdown/json spec files: **pass**.
- `buck2 run //:check`: **failed** due existing lint issue outside spec edits:
  - `backend/src/synextra_backend/handlers/parser.py`: ANN201 missing return type annotation for `extract_blocks`.

## Overall Verdict

- **Blocking issue was found and corrected in this review branch.**
- No additional blocking defects observed in backend ADR/task specs after contract alignment.
