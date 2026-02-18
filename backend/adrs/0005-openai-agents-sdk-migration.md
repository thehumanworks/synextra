# ADR 0005: Migration from OpenAI Responses API to OpenAI Agents SDK

- Status: accepted
- Date: 2026-02-18
- Supersedes aspects of: ADR 0003 (orchestration layer), ADR 0004 (streaming architecture)

## Context

The RAG orchestrator (`rag_agent_orchestrator.py`) originally used the OpenAI Responses API directly for all LLM interaction. This required manually managing the tool-calling loop: parsing tool call responses, dispatching tool functions, serializing outputs, and feeding them back into successive API calls via `previous_response_id`. A partial migration to the `openai-agents` SDK was started but left the codebase in a broken state:

- `_call_agent` had an empty `async for` loop followed by dead code referencing an undefined `response` variable.
- `@function_tool` decorators on instance methods replaced those methods with `FunctionTool` objects, breaking fallback calls that expected regular return values.
- The method was marked `async` but never `await`ed by its callers, silently returning a coroutine instead of an `AgentCallResult`.
- `_synthesize_answer` used a synchronous `OpenAI` client inside an `async` function, blocking the event loop during fallback synthesis.
- `stream_synthesis` used a raw `AsyncOpenAI` client, bypassing the Agents SDK entirely.

The `openai-agents` SDK (`>=0.9.1`) was already a declared dependency but not properly utilized.

## Decision

Complete the migration: use the `openai-agents` SDK (`Agent` + `Runner`) for all LLM interactions in the orchestrator. Remove all direct `OpenAI` and `AsyncOpenAI` client usage.

### 1. Retrieval agent loop (`_call_agent`)

Use `Runner.run_streamed()` to execute a tool-equipped `Agent`. The SDK handles the full tool-calling lifecycle automatically: argument parsing, function dispatch, output serialization, and multi-turn conversation management.

```
Agent(name="synextra_ai", tools=[bm25_search, read_document], ...)
  └─ Runner.run_streamed(agent, input="Question: ...", max_turns=10)
       └─ SDK manages tool calls → tool outputs → next LLM turn → ...
       └─ stream_events() yields tool_call_item, message_output_item, etc.
       └─ final_output contains the agent's synthesized answer
```

### 2. Tool definition via async closures (`_create_agent_tools`)

Tools are defined as `async` `@function_tool` closures inside a factory method, capturing `self._bm25_store` and `self._document_store` via closure scope. A mutable `evidence_collector: list[EvidenceChunk]` is passed in and populated as a side effect.

Tools are `async` (not `sync`) to ensure the SDK executes them on the event loop thread. The SDK dispatches sync `@function_tool` functions to a thread pool via `asyncio.to_thread()`, which would create concurrent mutations on the shared `evidence_collector` list when the agent calls both tools in parallel. Making tools `async` eliminates this race condition.

### 3. Fallback synthesis (`_synthesize_answer`)

Uses `await Runner.run()` (non-streamed) with a tool-less `Agent` configured as a synthesis-only assistant. This replaces the previous blocking `client.responses.create()` call.

### 4. Streaming synthesis (`stream_synthesis`)

Uses `Runner.run_streamed()` with a tool-less synthesis `Agent`. Text deltas are extracted by filtering for `raw_response_event` events where `isinstance(event.data, ResponseTextDeltaEvent)`, then yielding `event.data.delta`. Falls back to `_simple_summary()` on any exception.

### 5. System prompt enforcement

The agent instructions now explicitly mandate both `bm25_search` and `read_document` tool usage before answering, using `MANDATORY` strategy headings and `MUST` language.

## Alternatives Considered

### A. Keep the raw Responses API with manual tool dispatch

Continue using `client.responses.create()` with manual `_dispatch_tool_call` and `_serialize_tool_output` loops.

- Pros: full control over tool dispatch; no SDK abstraction layer.
- Cons: significant boilerplate (dispatch, serialization, `previous_response_id` chaining); the existing implementation was already broken during partial migration; no type-safe tool definition; manual error handling per tool call.
- Rejected: the SDK eliminates ~80 lines of manual plumbing and provides correct tool lifecycle management out of the box.

### B. Use the Agents SDK for retrieval only, keep raw clients for synthesis

Migrate `_call_agent` to the SDK but leave `_synthesize_answer` and `stream_synthesis` using raw `OpenAI`/`AsyncOpenAI` clients.

- Pros: smaller migration scope; synthesis is a simple one-shot call that doesn't benefit from agent features.
- Cons: maintains two LLM integration patterns in the same file; keeps a sync `OpenAI` client that blocks the event loop in `_synthesize_answer`; requires maintaining both client instances.
- Rejected: consistency and eliminating the event-loop-blocking sync client outweigh the marginal simplicity of raw calls for synthesis.

### C. Use sync tool closures with a threading lock on the evidence collector

Keep tool closures synchronous and protect `evidence_collector` with `threading.Lock`.

- Pros: sync tools are simpler to reason about; explicit locking makes the thread-safety visible.
- Cons: adds lock contention on every tool call; lock overhead for a pattern that can be avoided entirely by making tools async; Python 3.14 free-threading makes list operations unsafe without locks.
- Rejected: async tools are the idiomatic solution — no lock needed, no thread-pool dispatch, and the underlying store operations (`bm25_store.search`, `document_store.read_page`) are in-memory and non-blocking.

## Consequences

- Pros:
  - Single LLM integration pattern: all calls go through `Agent` + `Runner`.
  - No raw `OpenAI`/`AsyncOpenAI` client instances in the orchestrator.
  - `_synthesize_answer` no longer blocks the event loop (was sync `client.responses.create` in an async function).
  - Tool definition is type-safe via `@function_tool` with auto-generated JSON schemas from type hints.
  - Evidence collection is thread-safe by design (async tools run on the event loop).
  - SDK handles `previous_response_id` chaining, tool output serialization, and multi-turn orchestration.
  - ~80 lines of manual dispatch code removed (`_dispatch_tool_call`, `_serialize_tool_output`, `_tools`, `Bm25RetrievalTool`, `ReadDocumentTool`).

- Trade-offs:
  - The SDK is an additional abstraction layer over the Responses API; debugging requires understanding both.
  - `evidence_collector` side-effect pattern (shared mutable list via closure) is less explicit than return-value-based collection but avoids JSON round-tripping through `ToolCallOutputItem.output`.
  - Synthesis via `Runner.run` / `Runner.run_streamed` creates a full `Agent` for a simple one-shot call — slightly heavier than a raw API call but consistent.
  - The `OPENAI_API_KEY` env var is now consumed by the SDK internally rather than explicitly by the orchestrator constructor.

## Follow-up Actions

- ADR 0004's note about "both `OpenAI` (sync) and `AsyncOpenAI` (async) clients are maintained" is now obsolete — neither client is directly instantiated.
- Monitor whether the SDK's internal client management respects connection pooling and timeout settings under production load.
- Consider streaming the retrieval agent's final turn directly (eliminating the separate synthesis call) if the SDK improves mixed text/tool-call stream handling in a future version.
- Evaluate `RunConfig`-level model overrides for A/B testing different models without changing the `Agent` definition.
