# Clerk SSO — AxiomFolio (axiomfolio-next)

Runbook for the AxiomFolio Next.js app (`apps/axiomfolio-next`) identity stack: Clerk SDK foundation (T6c) alongside the existing **`qm_token`** session in `localStorage`. Themed Clerk UI is a separate follow-up (Studio #152 pattern).

## Environment variables (standard names)

| Variable | Where used | Source |
| -------- | ------------ | ------ |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Client + server bootstrap | Vercel Marketplace — Clerk on the linked AxiomFolio / axiomfolio-next project; copy locally from the vault for dev |
| `CLERK_SECRET_KEY` | Server (proxy / session verification) | Same as above |

**Custom prefix** is not used — do not add an `AXIOMFOLIO_` or other prefix to these names in Vercel or `.env`.

Optional Clerk URLs (redirects) follow [Clerk environment variable docs](https://clerk.com/docs/guides/development/clerk-environment-variables) if dashboard defaults are insufficient.

## How Clerk and `qm_token` coexist

- **Legacy auth** — `qm_token` in `localStorage`, `AuthContext`, `/auth/callback`, `/login`, `/register`, and **`RequireAuthClient`** on protected pages remain the **source of truth** for who can use the app today.
- **Clerk** — `/sign-in` and `/sign-up` (catch-all routes) render Clerk’s hosted components. Keys must be present for those routes to work in dev/prod.
- **Proxy** (`apps/axiomfolio-next/src/proxy.ts`) — Next.js 16 uses `proxy.ts` instead of `middleware.ts`. Clerk is composed there and is **non-blocking**: it does not call `auth().protect()` and does not redirect unauthenticated users. It only wires Clerk’s request context for gradual adoption. Server-side protection for Clerk-only flows is future work.

Public paths are explicitly listed in `proxy.ts` (home, legacy auth, Clerk auth, pricing, health). This list may be tightened when server-side gates are introduced.

## Admin routes

There is **no `/admin` surface** in axiomfolio-next yet. When admin or operator routes are added, mirror the Basic Auth + Clerk pattern from LaunchFree/FileFree runbooks if required.

## Test sign-in locally

1. Copy `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` into `apps/axiomfolio-next/.env.local` (never commit).
2. Run: `pnpm --filter @paperwork-labs/axiomfolio-next dev` (port **3005** by default).
3. Open `http://localhost:3005/sign-in` and complete the Clerk dev flow. Confirm legacy flows: `/login`, `/auth/callback`, and `RequireAuthClient`-wrapped pages still work with `qm_token` as before.
4. Public health: `GET /api/health` → `{"status":"ok"}`.

## Related

- LaunchFree: `docs/infra/CLERK_LAUNCHFREE.md`
- Sprint: `docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`
