# Frontend Task JSON Schema

All tasks in this directory must be JSON files for machine parsing.

## Required Keys
- `task_id`
- `feature_branch`
- `description`
- `bdd_flows`
- `external_dependencies`
- `target_files`
- `if_when_then_tests`
- `status_lifecycle`
- `status`
- `required_subagent_review`
- `execution_log`

## Status Rules
- Allowed lifecycle: `todo -> review -> done`.
- Set `status` to `todo` when the task is picked up.
- Move to `review` when implementation is complete and a subagent review is requested.
- Move to `done` only after review feedback is addressed and lint/typecheck/tests pass.

## Execution Log Rules
- `execution_log` must be append-only.
- Update continuously with timestamped entries for research, implementation, validation, and review.
