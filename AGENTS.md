# Synextra Monorepo Agent Memory

## Repository Layout
- `backend/`: FastAPI service managed with `uv`.
- `frontend/`: Next.js 16 + React 19 application.
- `tools/buck/`: Buck2 orchestration scripts used by root Buck targets.

## Build Orchestration
- Root Buck2 configuration uses bundled prelude (`.buckconfig` with `[external_cells] prelude = bundled`).
- Root `BUCK` exposes command targets that proxy into module scripts.
- For Buck changes, validate through Buck itself (not only direct shell scripts): run `buck2 run //:check` after scaffolding and before claiming setup complete.
- Keep `.buckconfig` cell aliases (for example `toolchains`) aligned with bundled prelude expectations and verify shell wrappers work when invoked from Buck resource paths.
- If dependency manifests or lockfiles change (`backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json`, or lockfiles), rerun `buck2 run //:install` before lint/test/typecheck/build.
- Any edit to `.buckconfig`, `BUCK`, or `tools/buck/*.sh` requires rerunning `buck2 run //:check` before task completion.
- For dev wrappers in `tools/buck/*.sh`, shell PID cleanup alone is insufficient for reloader-based servers; terminate the dev process group and clean only newly introduced port listeners to avoid orphaned backend/frontend servers.
- For unexplained Buck regressions after recent config/dependency edits, run `buck2 clean`, then `buck2 run //:install`, then `buck2 run //:check`.
- Prefer `buck2 run //:dev` over manually starting backend/frontend in separate shells so process lifecycle and shutdown behavior match workspace standards.
- When recording setup or infra failures in task `execution_log`, include versions for `buck2`, Python runtime, and Node runtime for reproducibility.
- Preferred entry points:
  - `buck2 run //:install`
  - `buck2 run //:lint`
  - `buck2 run //:test`
  - `buck2 run //:typecheck`
  - `buck2 run //:build`
  - `buck2 run //:check`
  - `buck2 run //:dev` (runs backend + frontend together)

## Dependency Priming Rule
- Before coding against external dependencies, use the `wit` skill/tool against upstream repos.
- Treat local code + upstream findings as a pair; reconcile conflicts explicitly.

## Task Process (Global)
- Task files are JSON and must include continuous `execution_log` updates.
- Status lifecycle is strict: `todo -> review -> done`.
- Moving to `done` requires:
  - subagent review completed and addressed
  - lint, typecheck, and tests passing
- Every task that introduces an architectural decision must produce an ADR in `{module}/adrs/` with at least two alternatives considered. No exceptions.
- Every backend/frontend task must produce a task JSON in the appropriate `tasks/` directory. Missing task JSON is a process violation.

## Subagent Review Protocol (Mandatory)

Reviews are the highest-leverage quality gate. These rules are non-negotiable.

### Adversarial Default Posture
- Never prompt reviews with "final sanity check," "brief findings only if any," or "confirm this looks good." These phrases bias toward false-clean conclusions.
- Always frame reviews adversarially: "Assume this code has bugs. Find them or prove they do not exist. A clean finding requires explicit proof, not absence of suspicion."

### Mandatory Category Enumeration
Every code review must explicitly evaluate each category below and state a conclusion with reasoning. A review that skips any category is incomplete and must be re-run.
1. **API contract changes** — compare to prior contract, note status code changes, response schema changes, breaking changes for existing clients.
2. **Race conditions and concurrency** — thread safety, async/sync boundaries, lock ordering.
3. **State scope** — is shared state process-local, thread-local, or distributed? Is that correct for the deployment model (default assumption: multi-worker, horizontally scaled)?
4. **Error handling completeness** — enumerate all error branches, verify each has a handler, a test, and an observable outcome (not just a log line).
5. **Crash/restart recovery** — what in-memory state is lost on process death? What is the user-visible consequence?
6. **Test coverage fidelity** — do tests exercise the actual failure modes, or do they pass because of test isolation artifacts (single-process, mocked state)?

### No Evidence, No Clean Bill
- A conclusion of "no issues found" is only valid when accompanied by explicit reasoning per category.
- Acceptable form: "Category X: traced [function] -> [function] -> [terminal state], no issue because [reason]."
- Bare "no issues" or "looks good" must be rejected by the orchestrating session and the review re-run with explicit enumeration.

### Diff-Aware Reviews
- Before reviewing any file, run `git diff` against the base to understand what changed. Code that looks correct in isolation may be a regression relative to the prior contract.
- Every review must state which lines changed and evaluate the contract impact of those specific changes.

### Finding-to-Fix Verification
- When a review surfaces a finding and the implementation session claims to have addressed it, the fix must be re-reviewed with a targeted prompt: "Review the fix for [finding]. Confirm the root cause is addressed, not just the symptom."
- A fix that moves an in-memory set to a TTL-decorated in-memory set does not fix a cross-worker race. Verification reviews must catch this class of incomplete fix.

### Async/Background Operation Lifecycle Tracing
For any async or background operation, the review must trace the full lifecycle:
1. What triggers the operation.
2. What happens on success (where is the result stored, how does the caller learn of it).
3. What happens on failure (is the error stored, is the guard released, can it be retried, is a `status=error` state observable).
4. What happens if the process dies mid-operation (what state is lost, what is the recovery path).

## Self-Learning and Continuous Improvement
- After completing a task that exposes a new failure mode, coding pattern, or architectural insight, update the relevant AGENTS.md section before handoff. AGENTS.md is operating memory for future sessions — stale memory causes repeated mistakes.
- When a subagent review catches a real defect, record the class of defect as a durable check item so future reviews can look for it explicitly.
- When a fix is applied for a review finding, add a regression test that encodes the exact failure mode. The test is the durable proof; the AGENTS.md note is the searchable index.

## Durable Guidance
- Keep AGENTS files as high-signal operating memory only.
- Store detailed technical explanations in `docs/` with citations.
- Store architectural decisions in `adrs/` with alternatives considered.
- For coupled frontend/backend specs, maintain one canonical request/response contract.
- Validate enum values and required fields stay in parity before marking planning tasks ready.
- For diagnosis-only asks, explicitly separate analysis from implementation and state whether any fix was or was not applied.
- For persistent UI/UX defects, verify runtime mode/config first (for example OpenAI synthesis path vs `_simple_summary` fallback) before narrowing to rendering code.
- Do not claim a bug is fixed from proxy metrics alone; confirm the exact symptom is gone through end-to-end reproduction (integration test or manual UI check).
- When users report "still seeing the same issue," re-run the live repro immediately and reassess root cause before layering more patches.
- For cross-stack edits, run repo-standard validation (`buck2 run //:lint`, `buck2 run //:typecheck`, `buck2 run //:test` or `buck2 run //:check`) unless the user explicitly scopes checks down; report skipped checks.
- Before handoff, run a self-review on the diff to catch residual regressions, edge cases, and mismatches with the user's stated intent. The self-review must follow the Subagent Review Protocol above — adversarial framing, mandatory category enumeration, and explicit reasoning per category.
- `buck2 run //:messages` (`mmr`/DuckDB-backed) is not safe to run in parallel; fetch multiple session IDs sequentially to avoid lock conflicts on `~/Library/Caches/mmr/mmr.duckdb`.
- RAG chat fallback rendering: if structured-response parsing fails, frontend renders raw assistant text with preserved newlines (`whitespace-pre-wrap`), so token-per-line backend output appears as a vertical word list.
- Citation dedupe keyed only by `document_id` + `chunk_id` does not collapse overlap-heavy chunking output; dedupe by normalized span/text if repeated citation cards become noisy.
- For `_simple_summary` outputs, normalize internal whitespace before joining sentences to avoid newline-heavy token dumps from retrieval chunks.
- For repeated near-duplicate citations, fingerprint normalized supporting quotes (prefix-based) rather than relying on chunk ids alone.
- Current PDF chunking defaults are `token_target=700` and `overlap_tokens=120`; ingestion uses `chunk_pdf_blocks` without runtime overrides.
- Vector persistence uploads one file per stored chunk, while synthesis context uses `supporting_quote` truncated to 240 chars per citation; tune chunk size with that quote window in mind.
- Upload flow is hybrid: `/v1/rag/pdfs` and `/persist/embedded` are synchronous, while `POST /v1/rag/documents/{document_id}/persist/vector-store` queues vector persistence in a background task and returns `status=queued` until persistence is complete.
- Vector persistence status can be polled via `GET /v1/rag/documents/{document_id}/persist/vector-store` (`status=ok` with `vector_store_id`/`file_ids`, `status=queued` while in-flight, or `vector_store_not_persisted` when idle).
- Background vector persistence dedupe is process-local (in-memory in-flight guard with TTL), so strict cross-worker exactly-once guarantees require an external lock/state store in addition to OpenAI request idempotency keys.
- OpenAI SDK and `OPENAI_API_KEY` are required backend dependencies for RAG orchestration/search/persistence; keep `openai` imports at module top level and avoid key-presence gating paths.
- For Responses API migration, prefer native `instructions` + `input` fields over chat-style role arrays when no multi-item context object is required.
- For GPT-5.2 reasoning controls in Responses API, pass `reasoning={"effort": ...}`; supported values are `none|low|medium|high|xhigh` (`minimal` is not listed for GPT-5.2), and model default is `none` when omitted.
- Hybrid-first RAG policy: treat upload persistence as hybrid-only (always persist BM25 + vector store when possible) and force chat retrieval mode to `hybrid`; recoverable vector persistence failures should keep chat available with BM25 fallback plus warning.
- `_call_agent` in `rag_agent_orchestrator` is synchronous; do not `await` it or the exception path can silently degrade to `_simple_summary`.
- Any edit to `rag_agent_orchestrator.py` should run both `backend/tests/unit/services/test_rag_agent_orchestrator.py` and `backend/tests/integration/test_rag_end_to_end.py` to catch sync/async contract breaks and tool-wiring regressions before handoff.
- For chat `500` diagnosis, prioritize API error payload + traceback first; uvicorn's `Invalid HTTP request received` warning is often transport noise rather than the root exception.
- Playwright skill wrapper may lag upstream CLI naming (`playwright-cli` vs `playwright-mcp`); if wrapper fails, use `npx playwright@latest ...` commands directly for screenshots/verification.
- Stream metadata protocol: `/messages/stream` appends a `\x1e` (ASCII Record Separator) + JSON trailer after the answer text containing `{citations, mode, tools_used}`. Frontend parses this via `splitStreamedText()` in `lib/chat/stream-metadata.ts` at render time; during active streaming the trailer is not yet present so the raw text displays cleanly.
- Citation accordion is in `components/chat/citation-accordion.tsx` (extracted from `StructuredMessage`). `AiMessageBubble` accepts an optional `citations` prop and renders the accordion below the answer. Do not duplicate citation rendering in both `StructuredMessage` and `AiMessageBubble`—use one path per render mode.
- When switching render pipelines (e.g. structured JSON to streaming), audit all metadata channels (citations, agent events, mode badges) for data loss before merging; streaming-only paths silently drop non-text data unless explicitly forwarded.
- Real token streaming uses a two-phase architecture: `collect_evidence()` (retrieval, non-streamed) → `stream_synthesis()` (async generator, streamed via `AsyncOpenAI`). See `backend/adrs/0004-real-token-streaming.md`.
- For streaming from OpenAI through FastAPI, always use `AsyncOpenAI` (not sync `OpenAI`); sync clients block the event loop and serialize all chunks to memory before sending.
- Set `X-Accel-Buffering: no` header on all streaming responses to prevent nginx/reverse-proxy buffering. Also set `Cache-Control: no-cache`.
- `GZipMiddleware` buffers `text/plain` streaming responses entirely before compressing; never use it on routes that return `StreamingResponse`. It auto-skips `text/event-stream` but not `text/plain`.
- The orchestrator maintains both `OpenAI` (sync, for the `_call_agent` tool-calling loop) and `AsyncOpenAI` (async, for `stream_synthesis`). Do not replace one with the other — the agent loop is synchronous by design.
- For UI regression testing on streaming features, verify both the real-time token display (isStreaming=true path skips metadata parsing) and the post-stream citation rendering (isStreaming=false path parses metadata trailer).
