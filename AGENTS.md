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
