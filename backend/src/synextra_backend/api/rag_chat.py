from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any, cast

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from synextra.schemas.rag_chat import RagChatRequest, RagChatResponse, StreamEvent
from synextra.services.rag_agent_orchestrator import RagAgentOrchestrator

from synextra_backend.schemas.errors import ApiErrorResponse, error_response

_STREAM_METADATA_SEPARATOR = "\x1e"
_STREAM_EVENTS_SEPARATOR = "\x1d"
_STREAM_EVENTS_DONE = object()
_NO_PRELOADED_EVENT = object()
_RETRIEVAL_ERROR_ANSWER = "I hit an internal error while gathering evidence. Please retry."


def _get_orchestrator(request: Request) -> RagAgentOrchestrator:
    orchestrator = getattr(request.app.state, "rag_orchestrator", None)
    if orchestrator is None:  # pragma: no cover
        raise RuntimeError("RAG orchestrator not configured")
    return cast(RagAgentOrchestrator, orchestrator)


ORCHESTRATOR_DEPENDENCY = Depends(_get_orchestrator)


def build_rag_chat_router() -> APIRouter:
    router = APIRouter(prefix="/v1/rag", tags=["rag"])

    @router.post(
        "/sessions/{session_id}/messages",
        response_model=RagChatResponse,
        status_code=200,
        responses={
            500: {"model": ApiErrorResponse},
        },
        summary="Send a chat message for grounded QA",
    )
    async def post_message(
        session_id: str,
        request: RagChatRequest,
        orchestrator: RagAgentOrchestrator = ORCHESTRATOR_DEPENDENCY,
    ) -> RagChatResponse | JSONResponse:
        try:
            hybrid_request = request.model_copy(update={"retrieval_mode": "hybrid"})
            return await orchestrator.handle_message(
                session_id=session_id,
                request=hybrid_request,
            )
        except Exception as exc:  # pragma: no cover
            payload = error_response(
                code="chat_failed",
                message=str(exc) or "Chat request failed",
                recoverable=True,
            )
            return JSONResponse(status_code=500, content=payload.model_dump())

    @router.post(
        "/sessions/{session_id}/messages/stream",
        response_model=None,
        status_code=200,
        responses={
            500: {"model": ApiErrorResponse},
        },
        summary="Stream a chat message response for grounded QA",
    )
    async def post_message_stream(
        session_id: str,
        request: RagChatRequest,
        orchestrator: RagAgentOrchestrator = ORCHESTRATOR_DEPENDENCY,
    ) -> Response:
        hybrid_request = request.model_copy(update={"retrieval_mode": "hybrid"})
        event_queue: asyncio.Queue[object] = asyncio.Queue()

        async def on_stream_event(event: StreamEvent) -> None:
            await event_queue.put(event)

        async def collect_with_live_events() -> Any:
            try:
                return await orchestrator.collect_evidence(
                    session_id=session_id,
                    request=hybrid_request,
                    event_sink=on_stream_event,
                )
            finally:
                await event_queue.put(_STREAM_EVENTS_DONE)

        retrieval_task: asyncio.Task[Any] = asyncio.create_task(collect_with_live_events())

        preloaded_event: object = _NO_PRELOADED_EVENT
        first_event_task: asyncio.Task[object] = asyncio.create_task(event_queue.get())
        done, _pending = await asyncio.wait(
            {retrieval_task, first_event_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if first_event_task in done:
            preloaded_event = first_event_task.result()
        else:
            first_event_task.cancel()
            with suppress(asyncio.CancelledError):
                await first_event_task

        if retrieval_task in done and preloaded_event in (_NO_PRELOADED_EVENT, _STREAM_EVENTS_DONE):
            try:
                await retrieval_task
            except Exception as exc:  # pragma: no cover
                payload = error_response(
                    code="chat_failed",
                    message=str(exc) or "Chat request failed",
                    recoverable=True,
                )
                return JSONResponse(status_code=500, content=payload.model_dump())

        async def token_stream() -> AsyncIterator[str]:
            try:
                # Phase 1: Emit intermediate events as they are produced.
                first_item = preloaded_event
                if first_item is not _NO_PRELOADED_EVENT and first_item is not _STREAM_EVENTS_DONE:
                    yield cast(StreamEvent, first_item).model_dump_json() + "\n"

                if first_item is not _STREAM_EVENTS_DONE:
                    while True:
                        queued_item = await event_queue.get()
                        if queued_item is _STREAM_EVENTS_DONE:
                            break
                        yield cast(StreamEvent, queued_item).model_dump_json() + "\n"

                # Retrieval either succeeded or failed after some events already streamed.
                try:
                    retrieval, _stream_events = await retrieval_task
                except Exception:
                    yield _STREAM_EVENTS_SEPARATOR
                    yield _RETRIEVAL_ERROR_ANSWER
                    orchestrator._session_memory.append_turn(
                        session_id=session_id,
                        role="assistant",
                        content=_RETRIEVAL_ERROR_ANSWER,
                        mode=hybrid_request.retrieval_mode,
                        citations=[],
                        tools_used=["chat_failed"],
                    )
                    yield _STREAM_METADATA_SEPARATOR + json.dumps(
                        {
                            "citations": [],
                            "mode": hybrid_request.retrieval_mode,
                            "tools_used": ["chat_failed"],
                        },
                        default=str,
                    )
                    return

                # Group separator marks end of events, start of answer tokens.
                yield _STREAM_EVENTS_SEPARATOR

                # Phase 2: Stream answer tokens.
                answer_parts: list[str] = []
                async for token in orchestrator.stream_synthesis(
                    prompt=hybrid_request.prompt.strip(),
                    retrieval=retrieval,
                    reasoning_effort=hybrid_request.reasoning_effort,
                ):
                    answer_parts.append(token)
                    yield token

                full_answer = "".join(answer_parts)
                orchestrator._session_memory.append_turn(
                    session_id=session_id,
                    role="assistant",
                    content=full_answer,
                    mode=hybrid_request.retrieval_mode,
                    citations=retrieval.citations,
                    tools_used=retrieval.tools_used,
                )

                # Phase 3: Metadata trailer.
                metadata = {
                    "citations": [c.model_dump() for c in retrieval.citations],
                    "mode": hybrid_request.retrieval_mode,
                    "tools_used": retrieval.tools_used,
                }
                yield _STREAM_METADATA_SEPARATOR + json.dumps(
                    metadata,
                    default=str,
                )
            finally:
                if not retrieval_task.done():
                    retrieval_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await retrieval_task

        return StreamingResponse(
            token_stream(),
            media_type="text/plain; charset=utf-8",
            headers={
                "cache-control": "no-cache",
                "x-accel-buffering": "no",
            },
        )

    return router
