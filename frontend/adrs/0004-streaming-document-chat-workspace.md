# ADR 0004: Streaming Document Chat Workspace

- Status: Accepted
- Date: 2026-02-17

## Context

The chat UI still behaved like a temporary demo:
- component naming referenced "demo" instead of production behavior
- chat responses were fetched as full JSON payloads, then rendered after completion
- styling included mixed accents and panel framing that conflicted with the required plain black + stone direction

For this release, chat needed to:
- stream outputs from backend through FastAPI `StreamingResponse`
- render streamed markdown safely and incrementally
- simplify the experience to: heading, upload, chat thread with bottom input
- remove "demo" naming and notes side panel

## Decision

We adopted a text-streaming architecture:

1. Backend:
- Add `POST /v1/rag/sessions/{session_id}/messages/stream` that returns streamed text chunks via `StreamingResponse` (`text/plain`).
- Keep existing JSON endpoint for compatibility.

2. Frontend API bridge:
- `frontend/app/api/chat/route.ts` now accepts AI SDK `useChat` payloads (`id`, `messages`), extracts latest user text, forwards to backend stream endpoint, and relays stream body directly.
- On backend outage, return a local fallback text stream so UI remains usable.

3. Frontend UI:
- Rename `integration-demo` to `document-chat-workspace`.
- Switch chat state management to `useChat` + `TextStreamChatTransport`.
- Render assistant markdown through Streamdown-backed AI element message bubble during streaming (`isAnimating`).
- Apply black + stone visual system and keep only required layout sections.

## Alternatives Considered

1. Full UI Message Protocol SSE (`useChat` default transport)
- Rejected because backend would need to emit the complete AI SDK UI message event protocol (`start`, `text-*`, `finish`, etc.) plus stream headers (`x-vercel-ai-ui-message-stream`), which is heavier than required for plain answer streaming.

2. Keep JSON-only backend and simulate streaming on frontend
- Rejected because it does not provide true server streaming and violates the requirement to stream outputs from FastAPI.

3. Keep existing structured-response rendering path during stream
- Rejected because structured JSON parsing is completion-oriented and not ideal for token/chunk-first rendering. Streaming markdown via text parts is simpler and more stable for this UX.

## Consequences

- Pros:
  - true incremental responses from backend to UI
  - lower latency to first visible assistant content
  - markdown remains readable during streaming via Streamdown
  - simpler and more focused chat surface

- Trade-offs:
  - streamed path currently prioritizes answer text over structured metadata (citations/tools) in real-time
  - backend and frontend now maintain both JSON and streaming endpoints/contracts

## Follow-up Actions

- ~~Add optional streamed metadata channel (citations/tools) if real-time citation rendering becomes a requirement.~~ Done: metadata trailer protocol (`\x1e` + JSON) appended after answer tokens carries citations/mode/tools_used. See `lib/chat/stream-metadata.ts` and `backend/adrs/0004-real-token-streaming.md`.
- ~~Fake-streaming replaced with real token-by-token streaming.~~ Done: backend now uses `AsyncOpenAI.responses.create(stream=True)` for synthesis. See `backend/adrs/0004-real-token-streaming.md`.
- Consider upgrading to full AI SDK UI message protocol if tool/result streaming is needed in-chat.
