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
synextra ingest ./backend/tests/fixtures/1706.03762v7.pdf
synextra query "What is the Transformer model described in the paper?" --file ./backend/tests/fixtures/1706.03762v7.pdf
```
