from __future__ import annotations

import time

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

from synextra_backend.repositories.rag_document_repository import ChunkRecord, RagDocumentRepository
from synextra_backend.schemas.errors import ApiErrorResponse, error_response
from synextra_backend.schemas.rag_ingestion import RagIngestionResponse, RagPdfChunk
from synextra_backend.services.block_chunker import chunk_pdf_blocks
from synextra_backend.services.document_store import DocumentStore, build_page_texts_from_blocks
from synextra_backend.services.pdf_ingestion import PdfEncryptedError, PdfIngestionError, extract_pdf_blocks


def _get_repository(request: Request) -> RagDocumentRepository:
    repo = getattr(request.app.state, "rag_repository", None)
    if repo is None:  # pragma: no cover
        raise RuntimeError("RAG repository not configured")
    return repo


def _get_document_store(request: Request) -> DocumentStore:
    store = getattr(request.app.state, "document_store", None)
    if store is None:  # pragma: no cover
        raise RuntimeError("Document store not configured")
    return store


def _is_pdf(*, filename: str | None, content_type: str | None, data: bytes) -> bool:
    if content_type and content_type.lower().startswith("application/pdf"):
        return True
    if filename and filename.lower().endswith(".pdf"):
        return True
    return data.startswith(b"%PDF")


def build_rag_ingestion_router() -> APIRouter:
    router = APIRouter(prefix="/v1/rag", tags=["rag"])

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
        file: UploadFile = File(...),
        repository: RagDocumentRepository = Depends(_get_repository),
        document_store: DocumentStore = Depends(_get_document_store),
    ) -> RagIngestionResponse:
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
            ingestion = extract_pdf_blocks(data, sort=True)
        except PdfEncryptedError:
            payload = error_response(
                code="pdf_encrypted",
                message="PDF is encrypted or requires a password",
                recoverable=False,
            )
            return JSONResponse(status_code=422, content=payload.model_dump())
        except PdfIngestionError:
            payload = error_response(
                code="pdf_parse_failed",
                message="Failed to parse PDF",
                recoverable=False,
            )
            return JSONResponse(status_code=422, content=payload.model_dump())

        checksum = ingestion.checksum_sha256
        document_id = checksum

        existing = repository.get_document_by_checksum(checksum)
        if existing is not None:
            if not document_store.has_document(existing.document_id):
                page_texts = build_page_texts_from_blocks(
                    ingestion.blocks, ingestion.page_count,
                )
                document_store.store_pages(
                    document_id=existing.document_id,
                    filename=existing.filename,
                    pages=page_texts,
                )
            chunks = repository.list_chunks(existing.document_id)
            return RagIngestionResponse(
                document_id=existing.document_id,
                filename=existing.filename,
                mime_type="application/pdf",
                checksum_sha256=existing.checksum_sha256,
                page_count=existing.page_count,
                chunk_count=len(chunks),
                chunks=[
                    RagPdfChunk(
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

        document = repository.upsert_document(
            document_id=document_id,
            filename=file.filename or "upload.pdf",
            mime_type="application/pdf",
            checksum_sha256=checksum,
            page_count=ingestion.page_count,
        )

        chunked = chunk_pdf_blocks(document_id=document.document_id, blocks=ingestion.blocks)

        chunk_records: list[ChunkRecord] = []
        response_chunks: list[RagPdfChunk] = []

        for chunk in chunked:
            record = ChunkRecord(
                chunk_id=chunk.chunk_id,
                document_id=document.document_id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                token_count=chunk.token_count,
                citation_span=chunk.citation_span,
                text=chunk.text,
                bounding_box=chunk.bounding_box,
            )
            chunk_records.append(record)
            response_chunks.append(
                RagPdfChunk(
                    chunk_id=chunk.chunk_id,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    token_count=chunk.token_count,
                    citation_span=chunk.citation_span,
                    preview_text=chunk.preview_text,
                    bounding_box=chunk.bounding_box,
                )
            )

        repository.replace_chunks(document.document_id, chunk_records)

        page_texts = build_page_texts_from_blocks(ingestion.blocks, ingestion.page_count)
        document_store.store_pages(
            document_id=document.document_id,
            filename=document.filename,
            pages=page_texts,
        )

        _ = int((time.perf_counter() - started) * 1000)

        return RagIngestionResponse(
            document_id=document.document_id,
            filename=document.filename,
            mime_type="application/pdf",
            checksum_sha256=document.checksum_sha256,
            page_count=document.page_count,
            chunk_count=len(response_chunks),
            chunks=response_chunks,
        )

    return router
