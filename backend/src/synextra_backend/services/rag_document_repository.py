"""Compatibility wrapper for repository contracts."""

from synextra.repositories.rag_document_repository import (
    ChunkRecord,
    DocumentRecord,
    EmbeddedPersistenceRecord,
    InMemoryRagDocumentRepository,
    RagDocumentRepository,
)

__all__ = [
    "ChunkRecord",
    "DocumentRecord",
    "EmbeddedPersistenceRecord",
    "InMemoryRagDocumentRepository",
    "RagDocumentRepository",
]
