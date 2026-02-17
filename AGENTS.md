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
- RAG chat fallback rendering: if structured-response parsing fails, frontend renders raw assistant text with preserved newlines (`whitespace-pre-wrap`), so token-per-line backend output appears as a vertical word list.
- Citation dedupe keyed only by `document_id` + `chunk_id` does not collapse overlap-heavy chunking output; dedupe by normalized span/text if repeated citation cards become noisy.
- For `_simple_summary` outputs, normalize internal whitespace before joining sentences to avoid newline-heavy token dumps from retrieval chunks.
- For repeated near-duplicate citations, fingerprint normalized supporting quotes (prefix-based) rather than relying on chunk ids alone.
- OpenAI answer synthesis is not gated by `SYNEXTRA_USE_OPENAI_CHAT`; it is attempted whenever `OPENAI_API_KEY` is present, with local summary fallback on missing key/SDK/error.
- For Responses API migration, prefer native `instructions` + `input` fields over chat-style role arrays when no multi-item context object is required.
