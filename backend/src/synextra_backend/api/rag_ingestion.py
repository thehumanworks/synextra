from __future__ import annotations

import time
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from synextra import (
    Synextra,
    SynextraDocumentEncryptedError,
    SynextraDocumentParseError,
    SynextraIngestionError,
    SynextraUnsupportedMediaTypeError,
)
from synextra.repositories.rag_document_repository import RagDocumentRepository

from synextra_backend.schemas.errors import ApiErrorResponse, error_response
from synextra_backend.schemas.rag_ingestion import RagChunk, RagIngestionResponse


def _get_repository(request: Request) -> RagDocumentRepository:
    repo = getattr(request.app.state, "rag_repository", None)
    if repo is None:  # pragma: no cover
        raise RuntimeError("RAG repository not configured")
    return cast(RagDocumentRepository, repo)


def _get_synextra(request: Request) -> Synextra:
    client = getattr(request.app.state, "synextra", None)
    if client is None:  # pragma: no cover
        raise RuntimeError("Synextra SDK not configured")
    return cast(Synextra, client)


def _is_pdf(*, filename: str | None, content_type: str | None, data: bytes) -> bool:
    if content_type and content_type.lower().startswith("application/pdf"):
        return True
    if filename and filename.lower().endswith(".pdf"):
        return True
    return data.startswith(b"%PDF")


def build_rag_ingestion_router() -> APIRouter:
    router = APIRouter(prefix="/v1/rag", tags=["rag"])

    @router.post(
        "/documents",
        response_model=RagIngestionResponse,
        status_code=201,
        responses={
            415: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
        },
        summary="Upload and chunk a document",
    )
    async def ingest_document(
        file: Annotated[UploadFile, File(...)],
        synextra: Annotated[Synextra, Depends(_get_synextra)],
        repository: Annotated[RagDocumentRepository, Depends(_get_repository)],
    ) -> RagIngestionResponse | JSONResponse:
        _started = time.perf_counter()
        data = await file.read()

        try:
            result = synextra.ingest(
                data,
                filename=file.filename or "upload",
                content_type=file.content_type,
            )
        except SynextraUnsupportedMediaTypeError as exc:
            payload = error_response(
                code="unsupported_media_type",
                message=str(exc),
                recoverable=False,
            )
            return JSONResponse(status_code=415, content=payload.model_dump())
        except SynextraDocumentEncryptedError as exc:
            payload = error_response(
                code="document_encrypted",
                message=str(exc),
                recoverable=False,
            )
            return JSONResponse(status_code=422, content=payload.model_dump())
        except SynextraDocumentParseError as exc:
            payload = error_response(
                code="document_parse_failed",
                message=str(exc),
                recoverable=False,
            )
            return JSONResponse(status_code=422, content=payload.model_dump())
        except SynextraIngestionError as exc:
            payload = error_response(
                code="document_ingestion_failed",
                message=str(exc),
                recoverable=False,
            )
            return JSONResponse(status_code=422, content=payload.model_dump())

        document = repository.get_document(result.document_id)
        if document is None:  # pragma: no cover
            payload = error_response(
                code="document_missing",
                message="Document was ingested but cannot be located",
                recoverable=False,
            )
            return JSONResponse(status_code=500, content=payload.model_dump())

        chunks = repository.list_chunks(result.document_id)

        _ = int((time.perf_counter() - _started) * 1000)

        return RagIngestionResponse(
            document_id=document.document_id,
            filename=document.filename,
            mime_type=document.mime_type,
            checksum_sha256=document.checksum_sha256,
            page_count=document.page_count,
            chunk_count=len(chunks),
            chunks=[
                RagChunk(
                    chunk_id=chunk.chunk_id,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    token_count=chunk.token_count,
                    citation_span=chunk.citation_span,
                    preview_text=chunk.text[:240] + ("…" if len(chunk.text) > 240 else ""),
                    bounding_box=chunk.bounding_box,
                )
                for chunk in chunks
            ],
        )

    @router.post(
        "/pdfs",
        response_model=RagIngestionResponse,
        status_code=201,
        responses={
            415: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
        },
        summary="Upload and chunk a PDF",
    )
    async def ingest_pdf(
        file: Annotated[UploadFile, File(...)],
        synextra: Annotated[Synextra, Depends(_get_synextra)],
        repository: Annotated[RagDocumentRepository, Depends(_get_repository)],
    ) -> RagIngestionResponse | JSONResponse:
        started = time.perf_counter()
        data = await file.read()

        if not _is_pdf(filename=file.filename, content_type=file.content_type, data=data):
            payload = error_response(
                code="unsupported_media_type",
                message="Only PDF uploads are supported",
                recoverable=False,
            )
            return JSONResponse(status_code=415, content=payload.model_dump())

        try:
            result = synextra.ingest(
                data,
                filename=file.filename or "upload.pdf",
                content_type=file.content_type,
            )
        except SynextraDocumentEncryptedError:
            payload = error_response(
                code="pdf_encrypted",
                message="PDF is encrypted or requires a password",
                recoverable=False,
            )
            return JSONResponse(status_code=422, content=payload.model_dump())
        except SynextraDocumentParseError:
            payload = error_response(
                code="pdf_parse_failed",
                message="Failed to parse PDF",
                recoverable=False,
            )
            return JSONResponse(status_code=422, content=payload.model_dump())
        except SynextraIngestionError as exc:
            payload = error_response(
                code="pdf_ingestion_failed",
                message=str(exc),
                recoverable=False,
            )
            return JSONResponse(status_code=422, content=payload.model_dump())

        document = repository.get_document(result.document_id)
        if document is None:  # pragma: no cover
            payload = error_response(
                code="document_missing",
                message="PDF was ingested but cannot be located",
                recoverable=False,
            )
            return JSONResponse(status_code=500, content=payload.model_dump())

        chunks = repository.list_chunks(document.document_id)

        _ = int((time.perf_counter() - started) * 1000)

        return RagIngestionResponse(
            document_id=document.document_id,
            filename=document.filename,
            mime_type=document.mime_type,
            checksum_sha256=document.checksum_sha256,
            page_count=document.page_count,
            chunk_count=len(chunks),
            chunks=[
                RagChunk(
                    chunk_id=chunk.chunk_id,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    token_count=chunk.token_count,
                    citation_span=chunk.citation_span,
                    preview_text=chunk.text[:240] + ("…" if len(chunk.text) > 240 else ""),
                    bounding_box=chunk.bounding_box,
                )
                for chunk in chunks
            ],
        )

    return router
