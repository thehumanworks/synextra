# ADR 0001: Self-contained SDK with separate CLI workspace

- Status: accepted
- Date: 2026-02-18

## Context

The SDK workspace previously bundled a CLI entrypoint and depended on `backend/` internals. That prevented clear package ownership and made pip-style consumption awkward.

## Decision

- Keep `sdk/` library-only (`synextra` package) with all core ingestion/retrieval/orchestration logic.
- Move CLI into a separate `cli/` workspace (`synextra-cli`) that depends on `synextra`.
- Use local `tool.uv.sources` during monorepo development, while keeping versioned dependencies for publishable metadata.

## Alternatives Considered

### A. Keep CLI inside SDK package

- Pros: fewer workspaces.
- Cons: couples runtime library and shell UX concerns; forces CLI deps into SDK.
- Rejected: violates separation of concerns.

### B. Keep SDK depending on backend and split only CLI

- Pros: smaller refactor.
- Cons: SDK still not self-contained and cannot be cleanly published.
- Rejected: fails core requirement.

### C. Build a shared third package plus thin SDK/CLI packages

- Pros: maximal decomposition.
- Cons: higher migration complexity for limited short-term value.
- Rejected: unnecessary for current scope.

## Consequences

- SDK can be consumed by backend and external clients without backend source coupling.
- CLI versioning/release can evolve independently from SDK internals.
- Monorepo checks now include the dedicated CLI workspace.
