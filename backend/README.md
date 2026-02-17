# Synextra Backend

FastAPI backend scaffold managed with `uv`.

## Quickstart

```bash
uv venv
uv sync
uv run uvicorn synextra_backend.app:app --reload

# Optional CLI entrypoint configuration
SYNEXTRA_BACKEND_HOST=0.0.0.0 SYNEXTRA_BACKEND_PORT=8000 uv run synextra-backend
```

## Quality Gates

```bash
uv run ruff format .
uv run ruff check .
uv run mypy
uv run pytest
```
