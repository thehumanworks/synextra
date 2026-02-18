# SDK Agent Instructions

## Scope

- These rules apply to `sdk/**`.
- The `synextra` package is the canonical source of all RAG ingestion, retrieval, and orchestration logic.
- It must be self-contained: zero imports from `synextra_backend`. Run `grep -r "from synextra_backend\|import synextra_backend" sdk/src/` before any handoff — the result must be empty.
- The SDK is designed to be pip-installable independently of the backend. Keep `sdk/pyproject.toml` dependencies accurate and complete (no implicit reliance on backend's environment).

## Package Layout

```
sdk/src/synextra/
  client.py              # Public Synextra client (entry point for SDK consumers)
  py.typed               # PEP 561 marker — SDK ships type stubs
  repositories/          # Document repository abstractions
  retrieval/             # BM25 and vector search implementations
  schemas/               # Pydantic models shared across SDK and backend
  services/              # Core services: orchestrator, chunker, persistence, etc.
sdk/tests/               # SDK-specific tests (currently thin; expand as features grow)
sdk/adrs/                # SDK architectural decisions
sdk/pyproject.toml       # Package definition — maintain carefully
```

## Development Standards

- Use `uv` for all dependency and command execution: `uv --directory sdk run <command>`.
- Follow TDD: write or update tests first, then implementation.
- SDK tests live in `sdk/tests/`. Minimum requirement per new feature: one happy-path test, one failure-mode test, and one edge-case test. The current `test_sdk_ingest.py` is happy-path only — do not use it as a coverage template.
- Every feature must be fully typed. Run `uv --directory sdk run mypy src/` before handoff.
- Keep style consistent with `uv --directory sdk run ruff check src/` and `uv --directory sdk run ruff format src/`.

## Self-Containment Verification

After any SDK change, verify the package is importable in isolation before running tests:

```bash
python -c "from synextra.client import Synextra; print('OK')"
```

If this fails with an import error referencing `synextra_backend`, there is a dependency inversion regression — fix before proceeding.

## Orchestrator-Specific Rules

- `sdk/src/synextra/services/rag_agent_orchestrator.py` is the most change-dense file. After any edit to it, run:
  - `uv --directory backend run pytest tests/unit/services/test_rag_agent_orchestrator.py -v`
  - `uv --directory backend run pytest tests/integration/test_rag_end_to_end.py -v`
  (Backend tests exercise the orchestrator through compatibility wrappers and catch contract regressions.)
- All LLM calls go through the `openai-agents` SDK (`Agent` + `Runner`). Never add raw `OpenAI`/`AsyncOpenAI` client calls.
- For `@function_tool` parameters: use typed Pydantic models, never `dict[str, Any]`. Strict schema mode rejects `additionalProperties`, and test with native structured payloads (not only JSON-encoded strings).
- The orchestrator streaming protocol has three phases: (1) JSON-line events via `\x1d` separator, (2) answer tokens, (3) `\x1e` + metadata trailer. Preserve the wire format across refactors.
- Judge review is optional: `RagChatRequest.review_enabled=true` activates the multi-iteration judge loop. Default is `false` for lower latency. Tests must cover both paths.

## Buck2 Targets

- `buck2 run //:sdk-install` — install SDK dependencies
- `buck2 run //:sdk-lint` — run ruff
- `buck2 run //:sdk-test` — run pytest
- `buck2 run //:sdk-typecheck` — run mypy

For SDK-only changes, run these per-workspace targets first for fast feedback, then run `buck2 run //:check` before marking the task complete.

## ADRs

- SDK architectural decisions go in `sdk/adrs/`.
- Every ADR must include at least two alternatives considered and rejected, with rationale.
- Existing ADRs: `0001-self-contained-sdk-and-cli-split.md`.
