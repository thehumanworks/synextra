# ADR 0002: Azure OpenAI-compatible configuration via OpenAI-compatible client settings

- Status: accepted
- Date: 2026-02-19

## Context

The SDK and CLI previously assumed a direct OpenAI Platform setup:

- key source: `OPENAI_API_KEY`
- endpoint shape: default OpenAI base URL
- model API mode: openai-agents default (`responses`)

To support Azure-hosted OpenAI deployments without forking orchestration logic, we need a configuration path that:

1. Works with `openai-agents` (the project standard for all LLM calls).
2. Preserves default OpenAI behavior.
3. Allows OpenAI-compatible endpoint overrides and provider-specific key aliases.

Upstream findings used for this decision:

- `openai-agents` supports custom OpenAI-compatible clients (`AsyncOpenAI(base_url=..., api_key=...)`) and optional API-mode override via `set_default_openai_api("chat_completions")`.
- OpenAI Python and Microsoft endpoint-switching docs confirm Azure OpenAI can be used through OpenAI-compatible `base_url` patterns and requires `model` to be the Azure deployment name.

## Decision

Implement Azure compatibility by extending SDK/CLI configuration, while keeping orchestration on `openai-agents`:

- SDK `Synextra(...)` now accepts:
  - `openai_base_url` (OpenAI-compatible endpoint override)
  - `openai_api` (`responses` or `chat_completions`)
- SDK env alias support:
  - key aliases: `OPENAI_API_KEY` or `AZURE_OPENAI_API_KEY`
  - base URL aliases: `OPENAI_BASE_URL`, `AZURE_OPENAI_BASE_URL`
  - Azure endpoint fallback: `AZURE_OPENAI_ENDPOINT` converted to `/openai/v1/`
  - API-shape override: `SYNEXTRA_OPENAI_API`
- CLI now exposes matching options:
  - `--openai-base-url`
  - `--openai-api`
  - API key fallback includes `AZURE_OPENAI_API_KEY`

No backend/frontend runtime code change is required because backend already instantiates `Synextra` and inherits SDK configuration behavior.

## Alternatives Considered

### A. Replace `openai-agents` usage with Azure-specific raw clients (`AzureOpenAI` / `AsyncAzureOpenAI`)

- Pros: explicit Azure types and `api_version` parameters.
- Cons: violates project convention that orchestrator LLM calls run through `openai-agents`; would re-introduce dual client stacks and more migration risk.
- Rejected: conflicts with current architecture and would increase complexity.

### B. Add only `OPENAI_BASE_URL` support and nothing else

- Pros: minimal code changes.
- Cons: misses common Azure key/env conventions and provides no explicit API-shape control for compatibility fallbacks.
- Rejected: insufficient ergonomics and weaker operational reliability.

### C. Keep OpenAI-only assumptions and document manual monkeypatching

- Pros: zero code changes.
- Cons: forces each consumer to implement brittle process-level setup and does not meet product requirement for Azure integration.
- Rejected: does not satisfy requested capability.

## Consequences

- Positive:
  - Azure-hosted OpenAI endpoints can be used without changing orchestrator internals.
  - CLI and SDK configuration is consistent and explicit.
  - Default OpenAI behavior remains unchanged when overrides are absent.
- Trade-offs:
  - `set_default_openai_api(...)` is process-global within `openai-agents`; mixed API-shape requirements in one process need careful coordination.
  - Azure users must still provide deployment names in `model` values.
  - Some non-OpenAI providers may require tracing configuration (`OPENAI_AGENTS_DISABLE_TRACING=1` or explicit tracing API key), which remains an operator concern.
