from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from synextra_backend.schemas.errors import ApiErrorResponse, error_response
from synextra_backend.schemas.rag_chat import RagChatRequest, RagChatResponse
from synextra_backend.services.rag_agent_orchestrator import RagAgentOrchestrator


def _get_orchestrator(request: Request) -> RagAgentOrchestrator:
    orchestrator = getattr(request.app.state, "rag_orchestrator", None)
    if orchestrator is None:  # pragma: no cover
        raise RuntimeError("RAG orchestrator not configured")
    return orchestrator


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
        orchestrator: RagAgentOrchestrator = Depends(_get_orchestrator),
    ) -> RagChatResponse:
        try:
            return await orchestrator.handle_message(session_id=session_id, request=request)
        except Exception as exc:  # pragma: no cover
            payload = error_response(
                code="chat_failed",
                message=str(exc) or "Chat request failed",
                recoverable=True,
            )
            return JSONResponse(status_code=500, content=payload.model_dump())

    return router
