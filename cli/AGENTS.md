# CLI Agent Instructions

## Scope

- These rules apply to `cli/**`.
- The CLI (`synextra-cli`) wraps the `synextra` SDK for command-line use.
- It must import only from `synextra` (the SDK) and standard library/third-party packages. Zero imports from `synextra_backend`.
- Entrypoint: `cli/src/synextra_cli/main.py`, registered as the `synextra` console script in `cli/pyproject.toml`.

## Package Layout

```
cli/src/synextra_cli/
  __init__.py
  main.py              # Typer CLI entrypoints: query, research, synthesize, chat
cli/tests/
  test_cli_smoke.py    # Import smoke test + basic command invocation
cli/pyproject.toml     # CLI dependencies: synextra (path dep), typer, rich
```

## Critical: Module Importability

The CLI smoke test (`test_cli_smoke.py`) and all integration tests depend on `synextra_cli.main` being importable. A `SyntaxError` or missing import in `main.py` silently blocks all tests — pytest will report a collection error, not a test failure.

**Before running any CLI tests, verify the module imports cleanly:**

```bash
python -c "import synextra_cli.main; print('OK')"
```

Or via uv:

```bash
uv --directory cli run python -c "import synextra_cli.main; print('OK')"
```

If this fails, fix the import before running `buck2 run //:cli-test`.

## Python Syntax Rules for This Codebase

- Exception handling must use parenthesized syntax: `except (ExcTypeA, ExcTypeB):`.
- The legacy Python 2 comma syntax `except ExcTypeA, ExcTypeB:` is a `SyntaxError` in Python 3.14+ and blocks all module imports. This class of bug was introduced during the CLI workspace creation and only caught in adversarial review.
- Linting does not always catch this — verify by importing the module.

## Development Standards

- Use `uv --directory cli run <command>` for all execution.
- Follow TDD: write or update tests before implementation.
- `test_cli_smoke.py` covers only happy-path import and basic invocations. Expand it with failure-mode tests (e.g., missing API key, invalid file path, network error) when adding new CLI commands.
- `synextra query` and `synextra chat` require at least one `--file` value and always run retrieval in `hybrid` mode. `synextra ingest` no longer exists as a standalone command.
- OpenAI compatibility flags (`--openai-base-url`, `--openai-api`) must be wired consistently across `query`, `research`, `synthesize`, and `chat`, and tests should verify wiring into `Synextra(...)`.
- API-key resolution should remain provider-friendly: accept `OPENAI_API_KEY` and `AZURE_OPENAI_API_KEY`.
- Keep style consistent: `uv --directory cli run ruff check src/` and `uv --directory cli run ruff format src/`.
- Keep types strict: `uv --directory cli run mypy src/`.

## End-to-End CLI Smoke Run

After any CLI or SDK change, validate with a real invocation:

```bash
PYTHONWARNINGS=ignore uv --directory cli run synextra query \
  "Summarize the key idea in this file." \
  --file ../backend/tests/fixtures/1706.03762v7.pdf \
  --json
```

Expected output: valid JSON containing `ingested` metadata plus `answer`/`citations`. If this fails, the CLI is broken regardless of unit test results.

## Buck2 Targets

- `buck2 run //:cli-install` — install CLI dependencies
- `buck2 run //:cli-lint` — run ruff
- `buck2 run //:cli-test` — run pytest
- `buck2 run //:cli-typecheck` — run mypy

For CLI-only changes, run these targets first for fast feedback, then run `buck2 run //:check` before marking the task complete.
