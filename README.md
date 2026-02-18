# Synextra `Chat with your documents`

## Challenge Context

```md
Write a simple application for the ingestion of documents for downstream tasks such as Q&A, summaries, storage, and more.

As a minimum, the application must:

Ingest a PDF document — parse and extract the content (PDF provided in the repo)
Enable question answering — allow a user to ask natural language questions about the ingested document and receive accurate, grounded responses.
Provide a simple interface — this should be a basic, responsive web UI with built in security, styling and interactivity.
Beyond the minimum, consider how you might extend the application to handle scenarios such as multi-document ingestion, chunking strategies, summarisation, or citation of source passages. You are not expected to implement all of these, but demonstrating awareness of them (even in documentation) is valued.
```

## Project Structure

This application is built as a monorepo, comprising of 4 separate (yet composable) components:

- `backend/`: FastAPI + `uv`
- `frontend/`: Next.js 16 + React 19 + Tailwind
- `sdk/`: standalone `synextra` Python SDK package
- `cli/`: standalone CLI workspace depending on `synextra` SDK

## Application Overview

The application is built for agentic RAG. This was a conscious decision, based on my own experience of Vector Search and Graph Search. Often, the cost of retrieval using these methods will be high and there is a risk of incompleteness.

### RAG Workflow

The application ingests and parses documents of different formats (`pdf`, `docx`, `txt`, `csv`...). They all follow similar approaches to processing, so I will use the `pdf` format as example:

1. on upload of a `pdf`, the application leverages `pymupdf` to perform OCR over the pdf document, extracting both text and layout information from the document. This is faster, cheaper and often reliable enough that it outweighs the benefits of using a Vision Model for this step. The extraction is done such that the document's content is broken down into meaningful chunks, both by page and by PDF layout section. This is critical in RAG systems as the chunking of a document will directly impact the quality of the retrieval. If chunks too small are retrieved, it often happens the agent reads incomplete information. If chunks are too large, there may be a lot of noise. These problems are solved with additional strategies, mentioned further below.

2. the second step in this pipeline is the ingestion of the document, which is done across two stores: a BM25 store and a plain Document Store.
  
- The BM25 store is used to retrieve document chunks using sparse embeddings and the well-known BM25 ranking algorithm (used in engines like `Lucene`). The choice of BM25 is also motivated by both research and empirical evidence: LLMs being text prediction `engines` are often great at picking meaningful words and phrases, which BM25 will then leverage to rank chunks based on frequency in the document. BM25 uses IDF (inverted document frequency) to rerank chunks, adding more positive value to terms that are frequent and a lower weight to those that are less common (but still ranked regardless).
- The Document Store stores the PDF's pages as they are extracted. This is used to read pages or lines of pages, often after a `positive` bm25 search hit.

3. The third step is retrieval. The retrieval process can be done both with a `reviewer` agent (becoming a multi-agent system where a reviewer agent validates the research done by the lead agent) or without. GPT-5.2 is used as the base model, and it's reliable enough that single-agent systems work well in this RAG setup. The agent has access to both `bm25_search` and `read_document` tools. The system prompt of the agent can be read from line `272` to `323` in `sdk/synextra/services/rag_agent_orchestrator.py`.

4. The fourth step is the final response generation. The agent will generate a final response based on the retrieved chunks. This is done by the `generate_response` method in `sdk/synextra/services/rag_agent_orchestrator.py`. The response include citations from the sources used and this is displayed in the UI.

Care was taken to make sure the Agent is aware of session-context (the backend uses the `openai-agents` python SDK) and that the interface prevents the user from sending messages when an on-going RAG session is in-place. Additionally, the chat renders markdown prettified and latex notation for mathematical equations (useful when ingesting research papers - the full `attention is all you need` paper is in this repo's root).

NOTE: if you don't like dark mode interfaces, I do apologise.

### Follow-up Steps

From this point there are few things that can be added for the application to make it prod ready.

- if required and appropriate, use persistent storage solutions like Azure's Fabric or similar.
- if persistent storage is used, then it's critical that the ingestion process is idempotent and can handle partial failures (this is specially important if Vector stores are used too).
- user auth must be added to prevent data leakage and unauthorized access.
- rate limiting must be added to prevent abuse and ensure fair usage (this is already taken care of to some degree in the chat interface by preventing messages being sent if the agent is working)
- the chat interface could be moved to an async `push then poll` paradigm, where a chat triggers the background work, the agent stream is drained to a persistent store and the user can drop the connection - and on return, the user can poll and see the results.
- model and reasoning effort can be selectable in the UI (added as dropdowns) - right now I made the decision to set the defaults that I believe work best - in speed and quality (gpt-5.2 and medium reasoning effort)
- the UI could be updated to accept multiple files at once, but since at the moment the app uses a per-session in-process document store, it makes sense to keep it simple for now.

Below are developer setup instructions to get things up and running.

## Developer Setup (without `buck2`)

### Module Quickstart

#### Backend

```bash
cd backend
uv venv
uv sync --dev
uv run uvicorn synextra_backend.app:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

#### SDK

```bash
cd sdk
uv venv
uv sync --dev
```

#### CLI

```bash
cd cli
uv venv
uv sync --dev

export OPENAI_API_KEY="..."
synextra query "What is this document about?" --pdf ../backend/tests/fixtures/1706.03762v7.pdf
synextra chat --pdf ../backend/tests/fixtures/1706.03762v7.pdf
```

## Engineering Process Files

Each module includes:
- `AGENTS.md` for durable workflow rules
- `docs/` for deeper technical documentation with citations
- `adrs/` for architecture decision records
- `tasks/` for machine-readable task JSON files with execution logs

## Local Development (with `Buck2`)

This repo is wired for Buck2 using bundled prelude configuration.

1. Install Buck2 from upstream releases: <https://github.com/facebook/buck2/releases>
2. From repo root, run targets:d

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

### Pre-commit

Install and enable hooks once per clone:

```bash
uv tool install pre-commit
pre-commit install
```

Run the full hook suite on demand:

```bash
pre-commit run --all-files
```

Configured hooks enforce formatter, lint, and tests:
- formatter: `ruff format` for `backend/`, `sdk/`, and `cli/`
- linter: `tools/pre-commit/run-lint.sh` (ruff + frontend eslint)
- tests: `tools/pre-commit/run-tests.sh` (backend/sdk/cli pytest + frontend vitest)