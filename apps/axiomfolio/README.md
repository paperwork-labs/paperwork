# @paperwork-labs/axiomfolio

Next.js 16 shell for AxiomFolio. Track E of the Infra & Automation
Hardening Sprint. Lives alongside `apps/axiomfolio` (Vite) so we can port
routes incrementally behind a feature flag instead of flipping the whole
frontend in one go.

## Status (2026-04-24)

- ✅ Monorepo package scaffolded, builds with Turborepo + Turbopack
- ✅ Three shells: `/system-status`, `/portfolio`, `/scanner`
- ✅ Feature-flag middleware (`NEXT_PUBLIC_AXIOMFOLIO_NEXT_ENABLED`)
- ✅ Shared UI tokens via `@paperwork-labs/ui`
- ⏳ Full port of Vite pages — follow-up PRs

## Local dev

```bash
pnpm --filter @paperwork-labs/axiomfolio dev
# http://localhost:3005
```

Until the flag is on, every gated route redirects to the Vite origin.
Point at a local Vite server with:

```bash
export NEXT_PUBLIC_AXIOMFOLIO_VITE_ORIGIN=http://localhost:3000
```

Or flip the flag to preview the new shell directly:

```bash
export NEXT_PUBLIC_AXIOMFOLIO_NEXT_ENABLED=true
```

## Porting checklist (per route)

1. Lift the Vite page into `src/app/<route>/page.tsx` as a Server Component.
2. Replace `react-query` client hooks with `fetch` + Server Components
   where possible; keep `use client` boundaries for interactive bits.
3. Adopt `@paperwork-labs/ui` primitives instead of Radix-in-axiomfolio.
4. Confirm the route works both with the flag on (Next) and off (Vite
   redirect) before shipping.
5. Add route to the QA golden suite (Track G).

## Contract with Brain

`AgentBrain` continues to live in `apis/axiomfolio`. Track M delegates
its LLM step to Paperwork Brain via `persona_pin=trading`, so the
Next.js shell can talk to the same `/api/v1/signals` endpoint without
any additional wiring.
