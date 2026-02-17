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
