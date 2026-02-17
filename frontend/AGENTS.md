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
- `AGENTS.md` is organizational memory, not a changelog.

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
- Status lifecycle is mandatory: `todo -> review -> done`.
- When a task is picked up, set `status` to `todo`.
- When implementation is complete, set `status` to `review`, spawn a subagent for review, and act critically on feedback.
- Only move to `done` after review is complete and lint/typecheck/tests pass.
- Keep `execution_log` continuously updated during research, implementation, validation, and review.
