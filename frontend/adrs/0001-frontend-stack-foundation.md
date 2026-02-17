# ADR 0001: Frontend Stack Foundation

- Status: Accepted
- Date: 2026-02-17

## Context
We need a React-based frontend module with fast iteration, strong TypeScript support, modern routing/data patterns, and straightforward integration for animation/UI primitives/AI hooks.

## Decision
Adopt Next.js 16 App Router + React 19 + Tailwind CSS v4 as the baseline. Add Motion, shadcn-compatible UI primitives, and AI SDK + AI Elements-style component scaffolding.

## Alternatives considered

### Alternative 1: Vite + React Router + Tailwind
- Pros:
  - Very fast local startup.
  - Minimal framework abstractions.
- Cons:
  - Requires separate decisions and wiring for server endpoints and deployment conventions.
  - Less built-in guidance for server/client component boundaries.

### Alternative 2: Remix
- Pros:
  - Strong web-standard request/response model.
  - Good data loading and mutation primitives.
- Cons:
  - Different conventions than the broader Next.js ecosystem used by most component/tooling examples.
  - Smaller ecosystem fit for current team defaults.

### Alternative 3: Next.js Pages Router
- Pros:
  - Familiar and stable.
- Cons:
  - Not aligned with current App Router and RSC-first patterns.
  - Less future-oriented for component-level server/client partitioning.

## Consequences
- We get a production-ready baseline quickly with conventions for both UI and API routes.
- We keep the route handler currently as scaffold logic and can replace it with provider-backed `streamText(...)` later.

## Follow-up actions
- Add route tests for chat streaming behavior.
- Replace scaffolded AI response with a configured provider and guardrails.
- Expand UI primitives incrementally via shadcn-style components.

## References
- [Next.js App Router docs](https://nextjs.org/docs/app)
- [Tailwind CSS Next.js guide](https://tailwindcss.com/docs/installation/framework-guides/nextjs)
- [Vercel AI SDK docs](https://ai-sdk.dev/docs)
