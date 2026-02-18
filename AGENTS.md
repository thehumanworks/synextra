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
- Before handoff, run a self-review on the diff to catch residual regressions, edge cases, and mismatches with the user's stated intent.
- `buck2 run //:messages` (`mmr`/DuckDB-backed) is not safe to run in parallel; fetch multiple session IDs sequentially to avoid lock conflicts on `~/Library/Caches/mmr/mmr.duckdb`.
- RAG chat fallback rendering: if structured-response parsing fails, frontend renders raw assistant text with preserved newlines (`whitespace-pre-wrap`), so token-per-line backend output appears as a vertical word list.
- Citation dedupe keyed only by `document_id` + `chunk_id` does not collapse overlap-heavy chunking output; dedupe by normalized span/text if repeated citation cards become noisy.
- For `_simple_summary` outputs, normalize internal whitespace before joining sentences to avoid newline-heavy token dumps from retrieval chunks.
- For repeated near-duplicate citations, fingerprint normalized supporting quotes (prefix-based) rather than relying on chunk ids alone.
- Current PDF chunking defaults are `token_target=700` and `overlap_tokens=120`; ingestion uses `chunk_pdf_blocks` without runtime overrides.
- Vector persistence uploads one file per stored chunk, while synthesis context uses `supporting_quote` truncated to 240 chars per citation; tune chunk size with that quote window in mind.
- OpenAI SDK and `OPENAI_API_KEY` are required backend dependencies for RAG orchestration/search/persistence; keep `openai` imports at module top level and avoid key-presence gating paths.
- For Responses API migration, prefer native `instructions` + `input` fields over chat-style role arrays when no multi-item context object is required.
- For GPT-5.2 reasoning controls in Responses API, pass `reasoning={"effort": ...}`; supported values are `none|low|medium|high|xhigh` (`minimal` is not listed for GPT-5.2), and model default is `none` when omitted.
- Hybrid-first RAG policy: treat upload persistence as hybrid-only (always persist BM25 + vector store when possible) and force chat retrieval mode to `hybrid`; recoverable vector persistence failures should keep chat available with BM25 fallback plus warning.
- `_call_agent` in `rag_agent_orchestrator` is synchronous; do not `await` it or the exception path can silently degrade to `_simple_summary`.
- Any edit to `rag_agent_orchestrator.py` should run both `backend/tests/unit/services/test_rag_agent_orchestrator.py` and `backend/tests/integration/test_rag_end_to_end.py` to catch sync/async contract breaks and tool-wiring regressions before handoff.
- For chat `500` diagnosis, prioritize API error payload + traceback first; uvicorn's `Invalid HTTP request received` warning is often transport noise rather than the root exception.
- Playwright skill wrapper may lag upstream CLI naming (`playwright-cli` vs `playwright-mcp`); if wrapper fails, use `npx playwright@latest ...` commands directly for screenshots/verification.
