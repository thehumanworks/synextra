from synextra_backend.api.health import build_health_router
from synextra_backend.api.pipeline import build_pipeline_router
from synextra_backend.api.rag_chat import build_rag_chat_router
from synextra_backend.api.rag_ingestion import build_rag_ingestion_router
from synextra_backend.api.rag_persistence import build_rag_persistence_router

__all__ = [
    "build_health_router",
    "build_pipeline_router",
    "build_rag_chat_router",
    "build_rag_ingestion_router",
    "build_rag_persistence_router",
]
