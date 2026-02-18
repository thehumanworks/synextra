from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from synextra_backend.schemas.errors import ApiErrorResponse, error_response
from synextra_backend.schemas.rag_chat import RagChatRequest, RagChatResponse
from synextra_backend.services.rag_agent_orchestrator import RagAgentOrchestrator

_STREAM_METADATA_SEPARATOR = "\x1e"


def _get_orchestrator(request: Request) -> RagAgentOrchestrator:
    orchestrator = getattr(request.app.state, "rag_orchestrator", None)
    if orchestrator is None:  # pragma: no cover
        raise RuntimeError("RAG orchestrator not configured")
    return orchestrator


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
    ) -> RagChatResponse:
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
        try:
            hybrid_request = request.model_copy(update={"retrieval_mode": "hybrid"})
            retrieval = await orchestrator.collect_evidence(
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

        async def token_stream() -> AsyncIterator[str]:
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

            metadata = {
                "citations": [c.model_dump() for c in retrieval.citations],
                "mode": hybrid_request.retrieval_mode,
                "tools_used": retrieval.tools_used,
            }
            yield _STREAM_METADATA_SEPARATOR + json.dumps(
                metadata, default=str,
            )

        return StreamingResponse(
            token_stream(),
            media_type="text/plain; charset=utf-8",
            headers={
                "cache-control": "no-cache",
                "x-accel-buffering": "no",
            },
        )

    return router
