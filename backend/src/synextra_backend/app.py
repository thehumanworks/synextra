import os
from typing import Final

import uvicorn
from fastapi import FastAPI
from synextra import Synextra
from synextra.repositories.rag_document_repository import (
    InMemoryRagDocumentRepository,
    RagDocumentRepository,
)
from synextra.services.pipeline_runtime import PipelineRuntime

from synextra_backend.api import (
    build_health_router,
    build_pipeline_router,
    build_rag_chat_router,
    build_rag_ingestion_router,
    build_rag_persistence_router,
)

DEFAULT_SERVICE_NAME: Final[str] = "synextra-backend"
DEFAULT_HOST: Final[str] = "0.0.0.0"
DEFAULT_PORT: Final[int] = 8000


def create_app(
    *,
    service_name: str = DEFAULT_SERVICE_NAME,
    rag_repository: RagDocumentRepository | None = None,
) -> FastAPI:
    normalized_service_name = service_name.strip()
    if not normalized_service_name:
        raise ValueError("service_name must not be empty")

    app = FastAPI(
        title="synextra-backend",
        version="0.1.0",
    )

    # Shared state.
    repository = rag_repository or InMemoryRagDocumentRepository()
    synextra = Synextra(openai_api_key=None, repository=repository)

    app.state.synextra = synextra
    app.state.rag_repository = synextra.repository
    app.state.bm25_store = synextra.bm25_store
    app.state.session_memory = synextra.session_memory
    app.state.document_store = synextra.document_store
    app.state.embedded_store_persistence = synextra.embedded_store_persistence
    app.state.rag_orchestrator = synextra.orchestrator
    app.state.pipeline_runtime = PipelineRuntime(synextra=synextra)

    app.include_router(build_health_router(service_name=normalized_service_name))
    app.include_router(build_rag_ingestion_router())
    app.include_router(build_rag_persistence_router())
    app.include_router(build_rag_chat_router())
    app.include_router(build_pipeline_router())
    return app


app = create_app()


def _read_server_host() -> str:
    configured_host = os.getenv("SYNEXTRA_BACKEND_HOST", DEFAULT_HOST).strip()
    if not configured_host:
        raise ValueError("SYNEXTRA_BACKEND_HOST must not be empty")

    return configured_host


def _read_server_port() -> int:
    configured_port = os.getenv("SYNEXTRA_BACKEND_PORT", str(DEFAULT_PORT)).strip()
    if not configured_port:
        raise ValueError("SYNEXTRA_BACKEND_PORT must not be empty")

    port = int(configured_port)
    if port <= 0:
        raise ValueError("SYNEXTRA_BACKEND_PORT must be greater than zero")

    return port


def main() -> None:
    uvicorn.run(
        "synextra_backend.app:app",
        host=_read_server_host(),
        port=_read_server_port(),
        reload=False,
    )
