# Frontend Foundation

## Runtime baseline
- Framework: Next.js 16 App Router in TypeScript.
- UI runtime: React 19.
- Styling: Tailwind CSS v4 with CSS variables for theme tokens.

## Integration baseline
- Motion animations use the `motion` package with `motion/react` entrypoint.
- ShadCN-compatible baseline includes:
  - `src/lib/utils.ts` `cn()` utility (`clsx` + `tailwind-merge`)
  - `src/components/ui/button.tsx` variant-based button primitive (`class-variance-authority`, Radix Slot)
  - `components.json` aliases and shadcn schema-compatible metadata
- AI scaffolding uses:
  - client hook `useChat` from `@ai-sdk/react`
  - API route stream scaffold in `src/app/api/chat/route.ts` via `ai`
  - AI Elements-style message primitive in `src/components/ai-elements/message-bubble.tsx`

## Why this baseline
- Keeps initial integration minimal while preserving an upgrade path to production model providers.
- Aligns with modern Next.js conventions (RSC by default, client hooks where needed).
- Gives reusable UI primitives immediately, rather than ad hoc classes per page.

## Primary sources
- [Source: Next.js App Router docs](https://nextjs.org/docs/app)
- [Source: React 19 release notes](https://react.dev/blog/2024/12/05/react-19)
- [Source: Tailwind CSS v4 docs](https://tailwindcss.com/docs/installation/framework-guides/nextjs)
- [Source: Motion for React docs](https://motion.dev/docs/react)
- [Source: shadcn/ui docs](https://ui.shadcn.com/docs)
- [Source: Vercel AI SDK docs](https://ai-sdk.dev/docs)
- [Source: Vercel AI Elements docs](https://ai-sdk.dev/elements/overview)
