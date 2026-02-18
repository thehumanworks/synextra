"""Compatibility wrappers for repository contracts.

The canonical implementation lives in the standalone ``synextra`` SDK.
"""

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
