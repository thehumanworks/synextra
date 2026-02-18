# ADR 0004: Real Token-by-Token Streaming

- Status: accepted
- Date: 2026-02-18

## Context

The streaming endpoint (`POST /v1/rag/sessions/{id}/messages/stream`) was introduced in ADR 0004 (frontend) to provide incremental chat responses. However, the implementation was fake-streaming: the backend fully awaited the OpenAI Responses API completion, then re-chunked the finished answer into 48-character pieces via `_answer_chunk_stream`. First-byte latency equaled full-response latency.

For a responsive chat experience, answer tokens need to flow from OpenAI through FastAPI to the frontend as they are generated.

## Decision

Adopt a two-phase streaming architecture that separates retrieval (non-streamable) from synthesis (streamable):

### Phase 1: Retrieval (non-streamed answer generation)

The new `collect_evidence()` method runs the existing agent tool-calling loop (`_call_agent`) or the manual retrieval fallback. This phase does not stream answer tokens because:
- Tool calls require multi-turn synchronous interactions with the OpenAI Responses API
- Evidence must be fully collected before citations can be built
- The agent's own answer text (a side effect of the tool-calling loop) is discarded

Note: ADR 0007 later added live streaming of retrieval *events* (tool/review steps) during this phase via an event queue, while keeping answer-token streaming in phase 2.

### Phase 2: Synthesis (streamed token-by-token)

The new `stream_synthesis()` async generator streams the final answer using `AsyncOpenAI.responses.create(stream=True)`. It:
- Receives `RetrievalResult` containing evidence + citations from phase 1
- Builds the same synthesis prompt as the existing `_synthesize_answer`
- Iterates `ResponseStreamEvent` objects, yielding `event.delta` on `response.output_text.delta` events
- Falls back to `_simple_summary()` on any streaming error

### Wire protocol

The metadata trailer protocol is unchanged from the prior citation fix: answer tokens are followed by `\x1e` (ASCII Record Separator) + JSON metadata containing `{citations, mode, tools_used}`. The frontend `splitStreamedText()` parses this at render time.

### Why not stream the agent's final turn directly?

The agent loop uses `tool_choice="auto"`, which can produce mixed text + tool-call outputs in a single response. Streaming this requires handling mid-stream tool calls (buffer partial text, execute tools, resume streaming). The complexity and fragility outweigh the benefit. Re-synthesizing costs ~200-500 extra output tokens but provides clean, predictable streaming with a dedicated synthesis prompt.

## Alternatives Considered

1. Stream the agent's final turn by detecting the last non-tool-call response
   - Rejected: complex mixed text/tool-call event handling in stream, fragile edge cases

2. Use the AI SDK UI Message Protocol (SSE with structured events)
   - Rejected: requires backend to emit the full Vercel AI SDK event protocol, heavier than needed for plain text streaming

3. Server-Sent Events (text/event-stream) instead of plain text
   - Rejected: `TextStreamChatTransport` expects `text/plain`; SSE framing would require frontend changes and adds unnecessary structure for single-stream text

## Consequences

- Pros:
  - True token-level streaming: first visible token arrives within ~500ms of the synthesis call starting
  - Clean separation of retrieval and synthesis phases
  - `AsyncOpenAI` enables proper async streaming without blocking the event loop
  - `X-Accel-Buffering: no` header prevents nginx/reverse-proxy buffering
  - No frontend changes required (existing `TextStreamChatTransport` handles real tokens identically to fake chunks)

- Trade-offs:
  - One extra OpenAI API call for synthesis (~200-500 output tokens) when the agent path would have produced an answer directly
  - Both `OpenAI` (sync, for tool-calling agent loop) and `AsyncOpenAI` (async, for streaming synthesis) clients are maintained
  - The agent's own answer text is discarded; synthesis quality depends on the evidence + synthesis prompt, not the agent's native output

## Follow-up Actions

- Consider streaming the agent's final turn directly if the extra API call latency becomes a concern (requires mixed event handling)
- Monitor synthesis quality vs. agent native answers to validate the re-synthesis approach
- Add streaming latency metrics (time-to-first-token, total stream duration) for observability
