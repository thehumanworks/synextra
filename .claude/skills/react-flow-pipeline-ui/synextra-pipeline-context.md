# Synextra Pipeline Context

Map flow nodes to SDK and backend capabilities. Use this when designing node types and pipeline execution logic.

## SDK (`sdk/src/synextra/`)

### Ingestion

| Module | Key exports | Purpose |
|--------|-------------|---------|
| `document_ingestion` | `parse_document`, `DocumentParseError`, `UnsupportedDocumentTypeError` | Parse PDF, DOCX, CSV, XLSX, text, code |
| `pdf_ingestion` | `extract_pdf_blocks`, `sha256_hex`, `PdfEncryptedError` | PDF-specific extraction |
| `block_chunker` | `chunk_pdf_blocks`, `chunk_text_pages`, `ChunkedText` | Chunking with `token_target`, `overlap_tokens` |
| `document_store` | `DocumentStore`, `PageText`, `build_page_texts_from_bocks` | Store parsed pages/blocks |

**Supported document kinds**: `pdf`, `doc`, `docx`, `csv`, `xlsx`, `text` (+ code extensions: `.py`, `.ts`, `.json`, etc.)

### Retrieval

| Module | Key exports | Purpose |
|--------|-------------|---------|
| `retrieval.bm25_search` | `Bm25IndexStore` | BM25 search |
| `retrieval.types` | `EvidenceChunk` | Chunk with text, document_id, chunk_id, etc. |
| `services.embedded_store_persistence` | `EmbeddedStorePersistence` | Vector store persistence (OpenAI) |

### Orchestration

| Module | Key exports | Purpose |
|--------|-------------|---------|
| `services.rag_agent_orchestrator` | `RagAgentOrchestrator`, `RetrievalResult` | RAG agent with tools |
| `schemas.rag_chat` | `RagChatRequest`, `RagCitation`, `StreamEvent`, `SearchEvent`, `ReviewEvent` | Chat/stream schemas |

**Agent tools** (used by orchestrator):

- `bm25_search` — BM25 search with query
- `read_document` — Read specific page/line range
- `parallel_search` — Run multiple searches concurrently

### Client API

| Method | Purpose |
|--------|---------|
| `ingest()` | Ingest documents, returns `IngestionResult` (document_id, chunk_count, etc.) |
| `research()` | Run RAG retrieval, returns `ResearchResult` (citations, events) |
| `chat()` | Full chat with synthesis |
| `review()` | Optional judge loop for citation quality |

## Backend (`backend/src/synextra_backend/`)

### API Routes

| Route | Purpose |
|-------|---------|
| `POST /v1/rag/documents` | Upload document (sync) |
| `POST /v1/rag/documents/{id}/persist/vector-store` | Queue vector persistence (async) |
| `GET /v1/rag/documents/{id}/persist/vector-store` | Poll persistence status |
| `POST /v1/rag/chat` | RAG chat |
| `POST /v1/rag/messages/stream` | Streaming chat |

### Persistence Flow

1. Upload → `/v1/rag/documents` (sync)
2. Persist vectors → `POST .../persist/vector-store` (queued, returns `status=queued`)
3. Poll until `status=ok` with `vector_store_id` / `file_ids`

## Suggested Node Types for Pipeline UI

| Node Type | Inputs | Outputs | SDK/Backend mapping |
|-----------|--------|---------|---------------------|
| **FileInput** | — | document(s) | `parse_document`, upload API |
| **Chunk** | document | chunks | `chunk_pdf_blocks`, `chunk_text_pages` |
| **Embed** | chunks | vector store | `EmbeddedStorePersistence` |
| **BM25Index** | chunks | BM25 index | `Bm25IndexStore` |
| **Search** | query + index | evidence | `bm25_search`, `read_document`, `parallel_search` |
| **Synthesize** | evidence + query | answer + citations | `stream_synthesis`, `_simple_summary` |
| **Review** | answer + citations | verdict | `synextra_judge` (optional) |

## Execution Order

Pipelines should execute in topological order (DAG). Typical flow:

1. Ingest → Chunk
2. Chunk → Embed (vector) and/or BM25Index
3. (Embed + BM25Index) → Search (hybrid)
4. Search → Synthesize
5. (Optional) Synthesize → Review → loop or final

## Configuration to Expose in Nodes

- **Chunk**: `token_target` (default 700), `overlap_tokens` (default 120)
- **Retrieval**: `top_k`, hybrid vs BM25-only
- **Synthesis**: model, `reasoning.effort` (none/low/medium/high/xhigh)
- **Review**: `review_enabled`, max iterations (3)

## Streaming Wire Protocol

The chat/stream endpoint uses **two ASCII separator characters** — not SSE:

```
STREAM_EVENTS_SEPARATOR   = "\x1d"  (ASCII 29 — Group Separator)
STREAM_METADATA_SEPARATOR = "\x1e"  (ASCII 30 — Record Separator)
```

**Stream layout:**
```
[event-JSON\n] × N         ← Phase 1: one JSON object per line (SearchEvent / ReviewEvent)
\x1d                       ← marks end of events, start of answer tokens
<answer token chunks>      ← Phase 2: raw text, no line protocol
\x1e                       ← marks end of answer, start of metadata
{"citations":[...],"mode":"hybrid","tools_used":[...]}   ← Phase 3: trailer JSON
```

**Parsing the stream for node status updates:**

```ts
// frontend/lib/chat/stream-metadata.ts pattern
async function* parsePipelineStream(reader: ReadableStreamDefaultReader<Uint8Array>) {
  const decoder = new TextDecoder();
  let buffer = '';
  let phase: 'events' | 'answer' | 'meta' = 'events';

  for await (const chunk of readChunks(reader)) {
    buffer += decoder.decode(chunk, { stream: true });

    if (phase === 'events') {
      const sep = buffer.indexOf('\x1d');
      if (sep !== -1) {
        // Parse event lines before the separator
        const eventLines = buffer.slice(0, sep).split('\n').filter(Boolean);
        for (const line of eventLines) yield { type: 'event', data: JSON.parse(line) };
        buffer = buffer.slice(sep + 1);
        phase = 'answer';
        yield { type: 'phase', phase: 'answer' };
      } else {
        // Flush complete lines as events
        const lines = buffer.split('\n');
        buffer = lines.pop()!;
        for (const l of lines.filter(Boolean)) yield { type: 'event', data: JSON.parse(l) };
      }
    }

    if (phase === 'answer') {
      const sep = buffer.indexOf('\x1e');
      if (sep !== -1) {
        yield { type: 'token', token: buffer.slice(0, sep) };
        const trailer = buffer.slice(sep + 1);
        yield { type: 'meta', data: JSON.parse(trailer) };
        phase = 'meta';
      } else {
        yield { type: 'token', token: buffer };
        buffer = '';
      }
    }
  }
}
```

**Map stream phases to node status updates:**

| Phase | Node update |
|-------|-------------|
| Phase 1 — `SearchEvent` received | `search-node` → `status: 'running'`, show query |
| `\x1d` received | `search-node` → `status: 'done'`; `synth-node` → `status: 'streaming'` |
| Phase 2 — answer token | `synth-node` → `status: 'streaming'`, accumulate `output` |
| `\x1e` received | `synth-node` → `status: 'done'` |

## Frontend TypeScript Types

From `frontend/lib/chat/` — use these when typing pipeline node data:

```ts
// Stream events
type StreamEvent =
  | { event: 'search'; tool: string; query?: string; page?: number; timestamp: string }
  | { event: 'reasoning'; content: string; timestamp: string }  // schema only, not yet emitted
  | { event: 'review'; iteration: number; verdict: 'approved' | 'rejected'; feedback?: string; timestamp: string };

// Post-stream metadata
type Citation = {
  document_id: string;
  chunk_id: string;
  page_number?: number | null;
  supporting_quote: string;
  source_tool: string;
  score?: number | null;
};

// Upload pipeline response (from /api/rag/upload BFF)
type UploadPipelineResponse = {
  document_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  ready_for_chat: boolean;
  effective_mode: 'embedded';
  warning?: string;
};

type ReasoningEffort = 'none' | 'low' | 'medium' | 'high' | 'xhigh';
```

**Important:** There are **no polling/job-status endpoints**. Upload is synchronous (two sequential HTTP calls, ~1–5s). Chat is fully streaming. Node status is driven by stream phase transitions, not by polling.

## API Routes Reference

| Method | Path | Purpose | Response |
|--------|------|---------|---------|
| `POST` | `/api/rag/upload` (BFF) | Upload + index document | `UploadPipelineResponse` |
| `POST` | `/v1/rag/documents` | Ingest raw (direct backend) | `RagIngestionResponse` (chunks with bboxes) |
| `POST` | `/v1/rag/documents/{id}/persist/embedded` | BM25 index | `RagPersistenceResponse` |
| `POST` | `/api/chat` (BFF) | Streaming chat | text/plain with `\x1d`/`\x1e` protocol |
| `POST` | `/v1/rag/sessions/{id}/messages/stream` | Direct backend stream | same protocol |
