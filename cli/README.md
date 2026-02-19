# Synextra CLI

This module contains the standalone CLI for the Synextra SDK.

## Install (uv)

```bash
cd cli
uv venv
uv sync --dev
```

## Usage

```bash
synextra query "What is the Transformer model described in the paper?" --file ./backend/tests/fixtures/1706.03762v7.pdf
synextra chat --file ./backend/tests/fixtures/1706.03762v7.pdf
```

`ingest` has been removed. `query` and `chat` now require one or more `--file` arguments and ingest those documents for the current in-process run.

## OpenAI / Azure options

All commands (`query`, `research`, `synthesize`, `chat`) support:

- `--openai-api-key` (or env `OPENAI_API_KEY`; fallback env `AZURE_OPENAI_API_KEY`)
- `--openai-base-url` (env `OPENAI_BASE_URL` or `AZURE_OPENAI_BASE_URL`)
- `--openai-api` (`responses|chat_completions`, env `SYNEXTRA_OPENAI_API`)
- optional tracing guard for non-OpenAI keys: `OPENAI_AGENTS_DISABLE_TRACING=1`

Azure example:

```bash
export AZURE_OPENAI_API_KEY="..."
synextra query "Summarize this document" \
  --file ./backend/tests/fixtures/1706.03762v7.pdf \
  --openai-base-url "https://<resource>.openai.azure.com/openai/v1/" \
  --openai-api chat_completions
```
