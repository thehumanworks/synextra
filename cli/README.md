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
