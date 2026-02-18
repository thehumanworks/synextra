# ADR 0006: Invert backend dependency to standalone Synextra SDK

- Status: accepted
- Date: 2026-02-18
- Supersedes aspects of: ADR 0005 implementation layout

## Context

The previous layout made `sdk/` depend on `backend/` by re-exporting `synextra_backend.sdk`. That prevented `sdk/` from being a self-contained package and blocked clean package publishing semantics.

We needed:

- `sdk/` to be installable independently (publishable layout).
- `backend/` to consume SDK logic instead of owning the canonical implementation.
- Existing backend import paths/tests to stay stable.

## Decision

1. Move canonical ingestion/retrieval/orchestration runtime into `sdk/src/synextra/**`.
2. Make `backend` depend on `synextra` via local `tool.uv.sources` (`../sdk`) and normal versioned dependency (`synextra>=0.1.0`).
3. Keep backend module paths stable with compatibility wrappers (`synextra_backend.services.*`, `retrieval.*`, `repositories.*`, `schemas.rag_chat`, and `sdk.py`) that re-export SDK types/implementations.

## Alternatives Considered

### A. Keep SDK as a thin backend re-export

- Pros: minimal code movement.
- Cons: SDK not self-contained; cannot publish independently; dependency direction remains wrong.
- Rejected: violates package-boundary goal.

### B. Create third shared `common/` module and make both backend + SDK depend on it

- Pros: no wrappers in backend; clear shared ownership.
- Cons: introduces another package boundary and migration overhead for this iteration.
- Rejected: unnecessary for current objective; wrappers provide faster, safe transition.

### C. Duplicate logic in backend and SDK

- Pros: no immediate wrapper indirection.
- Cons: guaranteed drift and double maintenance.
- Rejected: high regression risk and operational cost.

## Consequences

- SDK is now self-contained and installable without backend source.
- Backend remains API-first and reuses SDK behavior through wrappers.
- Any core logic edits should happen in `sdk/`; backend wrappers should stay thin.
- Type alignment across backend and SDK requires shared schema contracts, now handled by wrapper re-exports.
