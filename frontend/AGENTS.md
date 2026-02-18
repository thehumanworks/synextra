# Frontend Agent Instructions

## Scope

- These rules apply to `frontend/**`.
- Keep changes modular, composable, and small.
- Prefer strict TypeScript and explicit types for public interfaces.

## Dependency Priming (Required)

- Before implementing changes that depend on external tools/libraries, use the `wit` skill/tool against upstream repositories.
- Reconcile upstream behavior with local code before writing implementation code.
- Record high-value dependency findings in `execution_log` and durable guidance in this file.

## Testing and Delivery Process

- Follow TDD: write or update tests first, then implementation.
- Every feature must include positive, negative, and edge-case tests.
- Do not skip linting, type-checking, or tests before handoff.
- Keep `frontend/vitest.config.ts` aligned with the current folder layout (`app/**`, `components/**`, `lib/**`) and `test/setup.ts`; stale `src/**` patterns can silently skip tests.
- `AGENTS.md` is organizational memory, not a changelog.

## Frontend Retrospective Reminders

- For UI rendering bugs tied to assistant output, inspect and document the backend payload shape/runtime mode before treating it as a frontend-only issue.
- If `structured-response` falls back to raw text, call this out early in diagnosis and verify whether malformed formatting originates upstream.
- For Streamdown/AI Elements markdown rendering, keep `@import "katex/dist/katex.min.css"`, `@import "streamdown/styles.css"`, and `@source "../node_modules/streamdown/dist/*.js"` in `app/globals.css`; missing any of these causes broken markdown/math styling.
- Streamdown link rendering defaults to link-safety button wrappers (not plain `<a>`), so citation-specific link interception should be implemented via `components.a` override rather than relying on anchor click delegation.
- If replacing `<img>` with `next/image` for remote assets, update `frontend/next.config.ts` `images.remotePatterns` in the same change; otherwise runtime/build can fail with invalid host errors.
- With `useChat` + `TextStreamChatTransport`, custom backends should return plain streamed text (`text/plain`) rather than UI-message SSE parts; use default transport only when emitting the full AI SDK UI-message stream protocol and headers.
- For citation-dedupe/render fixes, add tests that cover near-duplicate citation payloads, not only exact duplicate ids.
- Inline answer citation markers (`[n]`) map to the original citation array order from backend synthesis context; source UI must surface matching `[n]` tags (or grouped tags when deduping) so references stay traceable.
- For citation cards, do not expose raw chunk/document UUID-like ids as body text; keep source UI human-readable (`Page N`, title/link, quote, source tool).
- Keep the sources panel collapsed by default and preserve `motion`-based expand/collapse behavior; include tests for both closed and opened states.
- For citation jump links into a collapsed `motion` accordion, a single immediate `scrollIntoView` can fire before layout settles; add a delayed retry aligned with expand duration.
- Frontend chat/upload routes must continue sending `retrieval_mode: "hybrid"` (runtime policy), even though shared schemas still accept `embedded|vector|hybrid` for compatibility.
- For structured citation renderer changes, include a mixed-source fixture (`bm25_search` + `openai_vector_store_search`) so source labeling/regression is caught in component tests.
- Do not mark UI issues resolved from backend metrics alone; confirm in a real UI flow (component/integration/Playwright/manual repro).
- Before handoff, run frontend lint, typecheck, and tests (or explicitly report which checks were intentionally skipped).

## Backend Contract Verification

- When backend changes API response status codes (e.g., 200 -> 202) or response schemas, frontend code that consumes those endpoints must be audited in the same task. The frontend review must verify: (a) status code handling covers the new code, (b) response parsing handles new/changed fields, (c) polling/retry logic exists for async-style 202 responses.
- For async backend endpoints (status=queued → poll for completion), the frontend must implement a polling strategy with backoff and a terminal timeout. Never assume a single request will return the final state.

## Review Quality Standards

- Follow the Subagent Review Protocol defined in root `AGENTS.md`. All reviews must be adversarially framed, must enumerate mandatory categories with explicit reasoning, and must not return bare "no issues" without per-category evidence.
- For frontend-specific reviews, additionally verify: (a) component renders correctly with loading/error/empty states, (b) TypeScript types match the actual backend payload shape (not just the local type definition), (c) accessibility attributes are preserved.

## Buck2 Validation Discipline

- If frontend dependency manifests or lockfiles change (`frontend/package.json` or lockfiles), run `buck2 run //:frontend-install` (or `buck2 run //:install`) before lint/test/typecheck/build.
- If `.buckconfig`, `BUCK`, or `tools/buck/*.sh` changes during frontend work, rerun `buck2 run //:check` before task completion.
- For unexplained Buck regressions after config/dependency edits, run `buck2 clean`, then `buck2 run //:install`, then `buck2 run //:check`.
- Prefer `buck2 run //:dev` for local full-stack development instead of running backend/frontend manually in separate shells.
- When logging setup or infra failures in task `execution_log`, include `buck2 --version`, Python runtime version, and Node runtime version for reproducibility.

## Documentation and Architecture

- Write deeper technical documentation in `frontend/docs/` and include citations.
- Write architectural decisions in `frontend/adrs/`.
- Every ADR must include at least two alternatives that were considered and rejected, with rationale.

## Task JSON Contract (Required)

- Tasks live in `frontend/tasks/*.json`.
- Each task JSON must include:
  - `task_id`
  - `feature_branch`
  - `description`
  - `bdd_flows`
  - `external_dependencies` (with GitHub repo pointers where applicable)
  - `target_files`
  - `if_when_then_tests`
  - `status_lifecycle`
  - `status`
  - `required_subagent_review`
  - `execution_log`
- For backend-coupled UI tasks, add a `test_plan` section that explicitly captures TDD order, unit coverage, backend integration checks, and Playwright manual validation.
- Status lifecycle is mandatory: `todo -> review -> done`.
- When a task is picked up, set `status` to `todo`.
- When implementation is complete, set `status` to `review`, spawn a subagent for review, and act critically on feedback.
- Only move to `done` after review is complete and lint/typecheck/tests pass.
- Keep `execution_log` continuously updated during research, implementation, validation, and review.
