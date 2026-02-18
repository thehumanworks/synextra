from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from synextra.repositories.rag_document_repository import RagDocumentRepository
from synextra.services.embedded_store_persistence import EmbeddedStorePersistence

from synextra_backend.schemas.errors import ApiErrorResponse, error_response
from synextra_backend.schemas.rag_persistence import RagPersistenceResponse


def _get_repository(request: Request) -> RagDocumentRepository:
    repo = getattr(request.app.state, "rag_repository", None)
    if repo is None:  # pragma: no cover
        raise RuntimeError("RAG repository not configured")
    return cast(RagDocumentRepository, repo)


def _get_embedded_persistence(request: Request) -> EmbeddedStorePersistence:
    persistence = getattr(request.app.state, "embedded_store_persistence", None)
    if persistence is None:  # pragma: no cover
        raise RuntimeError("Embedded persistence not configured")
    return cast(EmbeddedStorePersistence, persistence)


def build_rag_persistence_router() -> APIRouter:
    router = APIRouter(prefix="/v1/rag", tags=["rag"])

    @router.post(
        "/documents/{document_id}/persist/embedded",
        response_model=RagPersistenceResponse,
        status_code=200,
        responses={
            404: {"model": ApiErrorResponse},
        },
        summary="Persist a document to the embedded BM25 store",
    )
    async def persist_embedded(
        document_id: str,
        repository: Annotated[RagDocumentRepository, Depends(_get_repository)],
        persistence: Annotated[EmbeddedStorePersistence, Depends(_get_embedded_persistence)],
    ) -> RagPersistenceResponse | JSONResponse:
        document = repository.get_document(document_id)
        if document is None:
            payload = error_response(
                code="document_not_found",
                message="Document not found",
                recoverable=False,
            )
            return JSONResponse(status_code=404, content=payload.model_dump())

        duration_ms, _signature, indexed_chunk_count = persistence.persist(document_id=document_id)
        return RagPersistenceResponse(
            document_id=document_id,
            store="embedded",
            status="ok",
            indexed_chunk_count=indexed_chunk_count,
            duration_ms=duration_ms,
        )

    return router
