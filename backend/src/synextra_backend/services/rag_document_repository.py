"""Repository types for RAG documents.

The task specifications reference this module under ``services``. The concrete
implementation lives in :mod:`synextra_backend.repositories.rag_document_repository`.

Keeping this wrapper preserves the expected import path while allowing the
service layer to depend on repository abstractions.
"""

from synextra_backend.repositories.rag_document_repository import (
    ChunkRecord,
    DocumentRecord,
    EmbeddedPersistenceRecord,
    InMemoryRagDocumentRepository,
    RagDocumentRepository,
    VectorStorePersistenceRecord,
)

__all__ = [
    "ChunkRecord",
    "DocumentRecord",
    "EmbeddedPersistenceRecord",
    "InMemoryRagDocumentRepository",
    "RagDocumentRepository",
    "VectorStorePersistenceRecord",
]
