# ADR 0008: Remove backend compatibility wrappers and import SDK directly

- Status: accepted
- Date: 2026-02-18
- Supersedes: backend compatibility-wrapper layer introduced in ADR 0006

## Context

ADR 0006 moved canonical ingestion/retrieval/orchestration logic into `sdk/src/synextra` while keeping `synextra_backend.services.*`, `retrieval.*`, `repositories.*`, `schemas.rag_chat`, and `sdk.py` wrappers for import-path stability.

After the migration settled, backend source and tests could import `synextra.*` directly without losing behavior. Keeping a duplicate wrapper layer now adds maintenance overhead and stale paths.

## Decision

1. Backend source/tests import SDK modules directly from `synextra.*`.
2. Remove compatibility wrapper modules under:
   - `backend/src/synextra_backend/services/*` (wrapper-only files)
   - `backend/src/synextra_backend/retrieval/*` (wrapper-only files)
   - `backend/src/synextra_backend/repositories/rag_document_repository.py`
   - `backend/src/synextra_backend/schemas/rag_chat.py`
   - `backend/src/synextra_backend/sdk.py`
3. Keep backend-owned HTTP-layer modules (`api/*`, `schemas/errors.py`, `schemas/rag_ingestion.py`, `schemas/rag_persistence.py`, `app.py`) in `synextra_backend`.

## Alternatives Considered

### A. Keep wrappers indefinitely

- Pros: preserves old import paths for any downstream callers.
- Cons: duplicate module surface, extra test maintenance, and repeated boundary confusion.
- Rejected: unnecessary indirection now that backend and tests are fully migrated.

### B. Keep wrappers but emit deprecation warnings

- Pros: softer migration path for unknown external imports.
- Cons: still keeps duplicate implementation surface and warning noise in test/runtime paths.
- Rejected: this repo does not rely on those wrapper imports internally anymore.

### C. Move all backend API schemas into SDK

- Pros: fewer backend-local models.
- Cons: couples transport-specific FastAPI contracts to SDK package semantics.
- Rejected: backend-owned HTTP contracts remain backend concern.

## Consequences

- Backend depends on SDK directly at import level and runtime.
- Reduced maintenance surface in `synextra_backend`.
- Breaking change for external callers importing removed wrapper modules.
