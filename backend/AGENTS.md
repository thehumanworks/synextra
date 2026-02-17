# Backend Agent Instructions

## Scope

- These rules apply to `backend/**`.
- Keep modules short, composable, and single-purpose.
- Keep code fully typed and production-grade.

## Dependency Priming (Required)

- Before implementing changes that rely on external libraries, use the `wit` skill/tool to inspect upstream repositories.
- Reconcile upstream behavior with local constraints before writing code.
- Capture high-value findings in task `execution_log` and durable guidance in this file.

## Development Standards

- Use `uv` for environment, dependency, and command execution.
- Follow TDD: write or update tests first, then implementation.
- Every feature must include positive, negative, and edge-case tests.
- Keep style and quality aligned with PEP guidance and strict linting/type checks.
- `AGENTS.md` is organizational memory, not a changelog.

## Buck2 Validation Discipline

- If `backend/pyproject.toml` or `backend/uv.lock` changes, run `buck2 run //:backend-install` (or `buck2 run //:install`) before lint/test/typecheck.
- If `.buckconfig`, `BUCK`, or `tools/buck/*.sh` changes during backend work, rerun `buck2 run //:check` before task completion.
- For unexplained Buck regressions after config/dependency edits, run `buck2 clean`, then `buck2 run //:install`, then `buck2 run //:check`.
- Prefer `buck2 run //:dev` for local full-stack development instead of running backend/frontend manually in separate shells.
- When logging setup or infra failures in task `execution_log`, include `buck2 --version`, Python runtime version, and Node runtime version for reproducibility.

## Documentation and Architecture

- Write deeper technical documentation in `backend/docs/` with citations.
- Write architectural decisions in `backend/adrs/`.
- Every ADR must include at least two alternatives with rationale for rejection.

## Task JSON Contract (Required)

- Tasks live in `backend/tasks/*.json` and must be JSON for machine parsing.
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
- For API-facing tasks, add `related_adrs` and `tdd_test_matrix` entries that explicitly cover unit, integration, edge, and frontend-backend contract scenarios.
- Status lifecycle is mandatory: `todo -> review -> done`.
- When picked up, set `status` to `todo`.
- When implementation is complete, set `status` to `review`, spawn a subagent reviewer, and address review feedback critically.
- Move to `done` only after review feedback is resolved and lint/typecheck/tests pass.
- `execution_log` must be continuously updated throughout the task lifecycle.
