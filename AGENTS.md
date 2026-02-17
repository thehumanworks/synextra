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
