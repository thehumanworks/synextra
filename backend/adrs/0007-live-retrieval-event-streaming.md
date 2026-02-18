# ADR 0007: Live Retrieval Event Streaming During Agent Tool Calls

- Status: accepted
- Date: 2026-02-18

## Context

`POST /v1/rag/sessions/{session_id}/messages/stream` previously awaited `collect_evidence()` fully, then emitted the accumulated `stream_events` list. This caused tool-call steps to appear only at the end of the turn, even though the frontend already supports rendering event lines before `\x1d`.

We needed tool-call and review steps to appear in real time while retrieval is still running.

## Research Grounding

We reviewed upstream patterns with `wit`:

1. `openai/openai-agents-python`
   - `src/agents/run_internal/streaming.py` pushes stream items into an `asyncio.Queue` with `queue.put_nowait(...)`.
   - `src/agents/result.py` consumes that queue in `stream_events()` and stops on a sentinel (`QueueCompleteSentinel`).
   - `tests/fastapi/streaming_app.py` shows `StreamingResponse` wrapping an async stream of run events.

2. `Kludex/starlette`
   - `docs/responses.md` and `tests/test_responses.py` document and validate `StreamingResponse` over async iterators/generators.

3. `langchain-ai/langgraph`
   - `libs/langgraph/langgraph/pregel/main.py` and `libs/langgraph/langgraph/_internal/_queue.py` use queue-backed streaming (`stream.put_nowait`) to decouple producer execution from consumer emission.

These examples converge on the same architecture: background producer -> queue -> async streaming consumer -> sentinel termination.

## Decision

Adopt queue-backed live event streaming for retrieval:

1. Add an optional async `event_sink` callback to orchestrator retrieval methods.
2. Emit `SearchEvent`/`ReviewEvent` through both:
   - `event_collector` (for existing return-value compatibility), and
   - `event_sink` (for live streaming).
3. In the FastAPI route:
   - start retrieval in a background task,
   - push live events to an `asyncio.Queue`,
   - stream queue items immediately as JSON lines,
   - end event phase on sentinel, then emit `\x1d`, answer tokens, and `\x1e` metadata.

Protocol compatibility is preserved:
- Phase 1: JSON-line events
- Phase 2: answer tokens
- Phase 3: metadata trailer

## Error Handling Policy

- If retrieval fails before any event bytes are committed, return JSON `500` (`chat_failed`) as before.
- If retrieval fails after event streaming has started, complete the active stream with:
  - `\x1d`
  - a fallback assistant message
  - metadata with `tools_used=["chat_failed"]` and empty citations.

This avoids truncating an in-flight streaming response.

## Alternatives Considered

1. Keep list-based event buffering and flush after retrieval
   - Rejected: does not satisfy live intermediate-step visibility.

2. Migrate to SSE / AI SDK UI message stream protocol now
   - Rejected: heavier contract change across backend/frontend than required for the current plain-text transport.

3. Persist intermediate events to storage and poll from frontend
   - Rejected: introduces stateful infra and polling latency for a problem solvable in-process with queue streaming.

## Consequences

- Pros:
  - intermediate tool/review steps are visible while retrieval is running
  - no frontend protocol rewrite required
  - preserves existing separators and metadata trailer behavior

- Trade-offs:
  - streaming route now runs a background retrieval task + queue orchestration
  - in-stream post-start failures return a streamed fallback instead of JSON `500`
  - live event delivery remains process-local (cross-worker ordering is not guaranteed)
