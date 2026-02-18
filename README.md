# Synextra `Chat with your documents`



Monorepo scaffold for a document-ingestion challenge application with:
- `backend/`: FastAPI + `uv`
- `frontend/`: Next.js 16 + React 19 + Tailwind
- `sdk/`: standalone `synextra` Python SDK package
- `cli/`: standalone CLI workspace depending on `synextra`
- Buck2 orchestration at the repository root

## Buck2 Setup

This repo is wired for Buck2 using bundled prelude configuration.

1. Install Buck2 from upstream releases: <https://github.com/facebook/buck2/releases>
2. From repo root, run targets:

```bash
buck2 run //:install
buck2 run //:lint
buck2 run //:test
buck2 run //:typecheck
buck2 run //:build
buck2 run //:check
buck2 run //:dev
```

`buck2 run //:dev` starts backend and frontend together and stops both on `Ctrl+C`.

## Module Quickstart

### Backend

```bash
cd backend
uv venv
uv sync --dev
uv run uvicorn synextra_backend.app:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### SDK

```bash
cd sdk
uv venv
uv sync --dev
```

### CLI

```bash
cd cli
uv venv
uv sync --dev

export OPENAI_API_KEY="..."
synextra query "What is this document about?" --pdf ../backend/tests/fixtures/1706.03762v7.pdf
synextra chat --pdf ../backend/tests/fixtures/1706.03762v7.pdf
```

`synextra ingest` is no longer a standalone CLI command. Use `query` or `chat` with at least one `--file`/`--pdf` document each run.

## Engineering Process Files

Each module includes:
- `AGENTS.md` for durable workflow rules
- `docs/` for deeper technical documentation with citations
- `adrs/` for architecture decision records
- `tasks/` for machine-readable task JSON files with execution logs

## Challenge Context

Build an application that can ingest PDF documents for downstream tasks (Q&A, summaries, storage), provide grounded question answering, and include a basic responsive web UI.
