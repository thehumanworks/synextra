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

## OpenAI / Azure runtime configuration

Backend OpenAI calls are delegated to the `synextra` SDK. Configure at process env level:

- API key: `OPENAI_API_KEY` (or `AZURE_OPENAI_API_KEY`)
- Base URL override: `OPENAI_BASE_URL` (or `AZURE_OPENAI_BASE_URL` / `AZURE_OPENAI_ENDPOINT`)
- Optional API shape: `SYNEXTRA_OPENAI_API=responses|chat_completions`

For Azure OpenAI, set base URL to your OpenAI-compatible endpoint (`.../openai/v1/`) and use deployment names in model configuration.

## Quality Gates

```bash
uv run ruff format .
uv run ruff check .
uv run mypy
uv run pytest
```
