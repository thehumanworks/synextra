# ADR 0001: Backend Bootstrap Stack

- Status: accepted
- Date: 2026-02-17

## Context

The project needs a backend module that is lightweight, typed, testable, and quick to iterate with agent-driven development.

## Decision

Use FastAPI for the HTTP service layer, `uv` for package/environment management, and pytest + httpx for async API testing.

## Alternatives Considered

1. Flask + pip-tools
- Pros: minimal API surface; broad ecosystem.
- Cons: weaker native typing ergonomics for request/response contracts compared with FastAPI/Pydantic.

2. Django + built-in tooling
- Pros: batteries-included framework with mature conventions.
- Cons: heavier baseline than needed for an initial service with a single endpoint and strict modularity goals.

3. FastAPI + Poetry
- Pros: familiar packaging workflow.
- Cons: slower dependency workflows compared with `uv` in this repository's setup.

## Consequences

- Strong typed request/response support is available from day one.
- Async endpoint testing is straightforward with `httpx.ASGITransport`.
- Future architecture decisions should extend this ADR set rather than modifying this file into a changelog.
