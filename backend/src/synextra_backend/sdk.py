"""Compatibility exports for backend callers.

The canonical SDK implementation now lives in the standalone ``synextra``
package. This module remains as a compatibility layer for backend-local import
paths.
"""

from synextra import (
    IngestionResult,
    QueryResult,
    ResearchResult,
    ReviewResult,
    Synextra,
    SynextraConfigurationError,
    SynextraDocumentEncryptedError,
    SynextraDocumentParseError,
    SynextraError,
    SynextraIngestionError,
    SynextraQueryError,
    SynextraUnsupportedMediaTypeError,
    SynthesisResult,
)

__all__ = [
    "IngestionResult",
    "QueryResult",
    "ResearchResult",
    "ReviewResult",
    "Synextra",
    "SynextraConfigurationError",
    "SynextraDocumentEncryptedError",
    "SynextraDocumentParseError",
    "SynextraError",
    "SynextraIngestionError",
    "SynextraQueryError",
    "SynextraUnsupportedMediaTypeError",
    "SynthesisResult",
]
