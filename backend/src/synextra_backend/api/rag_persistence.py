from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from synextra_backend.repositories.rag_document_repository import RagDocumentRepository
from synextra_backend.schemas.errors import ApiErrorResponse, error_response
from synextra_backend.schemas.rag_persistence import RagPersistenceResponse
from synextra_backend.services.embedded_store_persistence import EmbeddedStorePersistence
from synextra_backend.services.openai_vector_store_persistence import OpenAIVectorStorePersistence


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


def _get_vector_persistence(request: Request) -> OpenAIVectorStorePersistence:
    persistence = getattr(request.app.state, "vector_store_persistence", None)
    if persistence is None:  # pragma: no cover
        raise RuntimeError("Vector store persistence not configured")
    return cast(OpenAIVectorStorePersistence, persistence)


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

    @router.post(
        "/documents/{document_id}/persist/vector-store",
        response_model=RagPersistenceResponse,
        status_code=200,
        responses={
            404: {"model": ApiErrorResponse},
            502: {"model": ApiErrorResponse},
        },
        summary="Queue persistence of a document to an OpenAI vector store",
    )
    async def persist_vector_store(
        document_id: str,
        background_tasks: BackgroundTasks,
        repository: Annotated[RagDocumentRepository, Depends(_get_repository)],
        persistence: Annotated[OpenAIVectorStorePersistence, Depends(_get_vector_persistence)],
    ) -> RagPersistenceResponse | JSONResponse:
        document = repository.get_document(document_id)
        if document is None:
            payload = error_response(
                code="document_not_found",
                message="Document not found",
                recoverable=False,
            )
            return JSONResponse(status_code=404, content=payload.model_dump())

        inspection = persistence.inspect(document_id=document_id)
        if inspection.existing is not None:
            return RagPersistenceResponse(
                document_id=document_id,
                store="vector-store",
                status="ok",
                vector_store_id=inspection.existing.vector_store_id,
                file_ids=list(inspection.existing.file_ids),
                duration_ms=0,
            )

        if not persistence.try_acquire_inflight(document_id=document_id):
            return RagPersistenceResponse(
                document_id=document_id,
                store="vector-store",
                status="queued",
                duration_ms=0,
            )

        try:
            background_tasks.add_task(
                persistence.persist_in_background,
                document_id=document_id,
            )
        except Exception as exc:
            persistence.release_inflight(document_id=document_id)
            payload = error_response(
                code="vector_store_queue_failed",
                message=str(exc) or "Vector store persistence could not be queued",
                recoverable=True,
            )
            return JSONResponse(status_code=502, content=payload.model_dump())

        return RagPersistenceResponse(
            document_id=document_id,
            store="vector-store",
            status="queued",
            duration_ms=0,
        )

    @router.get(
        "/documents/{document_id}/persist/vector-store",
        response_model=RagPersistenceResponse,
        status_code=200,
        responses={
            404: {"model": ApiErrorResponse},
        },
        summary="Get vector-store persistence status for a document",
    )
    async def get_vector_store_persistence_status(
        document_id: str,
        repository: Annotated[RagDocumentRepository, Depends(_get_repository)],
        persistence: Annotated[OpenAIVectorStorePersistence, Depends(_get_vector_persistence)],
    ) -> RagPersistenceResponse | JSONResponse:
        document = repository.get_document(document_id)
        if document is None:
            payload = error_response(
                code="document_not_found",
                message="Document not found",
                recoverable=False,
            )
            return JSONResponse(status_code=404, content=payload.model_dump())

        inspection = persistence.inspect(document_id=document_id)
        if inspection.existing is not None:
            return RagPersistenceResponse(
                document_id=document_id,
                store="vector-store",
                status="ok",
                vector_store_id=inspection.existing.vector_store_id,
                file_ids=list(inspection.existing.file_ids),
                duration_ms=0,
            )

        if persistence.is_inflight(document_id=document_id):
            return RagPersistenceResponse(
                document_id=document_id,
                store="vector-store",
                status="queued",
                duration_ms=0,
            )

        payload = error_response(
            code="vector_store_not_persisted",
            message="Document is not persisted to vector store yet",
            recoverable=True,
        )
        return JSONResponse(status_code=404, content=payload.model_dump())

    return router
