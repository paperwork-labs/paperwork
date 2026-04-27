---
owner: engineering
last_reviewed: 2026-04-27
doc_kind: plan
domain: other
status: completed
---
# AxiomFolio → Next.js 16 App Router — Migration Plan

## ✅ Completed 2026-04-27 (Track G4 — Q2 Tech Debt Convergence)

Founder directive: drop the `-next` stop-gap; canonical monorepo path is
[`apps/axiomfolio`](../../../apps/axiomfolio) with package name
**`@paperwork-labs/axiomfolio`**. The Vite SPA tree is **archived** (not
deleted) at
[`apps/_archive/axiomfolio-vite-LEGACY`](../../../apps/_archive/axiomfolio-vite-LEGACY)
— excluded from pnpm workspaces; see its README for retention policy.
Render static service **`axiomfolio-frontend`** is not in the root
[`render.yaml`](../../../render.yaml); customer UI is **Next.js on Vercel**
(same linked project — dashboard rename to `axiomfolio` is optional).

**Closing summary**

- **Routes:** App Router coverage matches the former Vite `App.tsx` surface,
  including legacy redirects (e.g. `/market/scanner`, `/settings/admin/system`,
  `/settings/trading/account-risk`, `/settings/admin/users`) implemented as
  thin `redirect()` pages where paths diverged.
- **CI / tooling:** `.github/workflows/ci.yaml` path filter and package filter
  use `apps/axiomfolio` and `@paperwork-labs/axiomfolio`.
- **Docs / infra:** `docs/INFRA.md`, `docs/infra/RENDER_INVENTORY.md`, Clerk
  runbooks, and `render.yaml` header comments updated; Vercel **`vercel.json`**
  `buildCommand` uses `pnpm --filter @paperwork-labs/axiomfolio...`.
- **Founder follow-up (optional):** In Vercel → Project Settings, rename
  project `axiomfolio-next` → `axiomfolio`; set **Root Directory** to
  `apps/axiomfolio` if it still pointed at `apps/axiomfolio-next`.

## Status snapshot (historical — pre-cutover 2026-04-24)

| Milestone | State | Where |
|---|---|---|
| Next.js app at canonical path | **Done (2026-04-27)** | [`apps/axiomfolio/`](../../../apps/axiomfolio) |
| SystemStatus route | Done | [`apps/axiomfolio/src/app/system-status/page.tsx`](../../../apps/axiomfolio/src/app/system-status/page.tsx) |
| Portfolio route | Done | [`apps/axiomfolio/src/app/portfolio/page.tsx`](../../../apps/axiomfolio/src/app/portfolio/page.tsx) |
| Scanner route | Done | [`apps/axiomfolio/src/app/scanner/page.tsx`](../../../apps/axiomfolio/src/app/scanner/page.tsx) |
| `@paperwork-labs/ui` wired | Done | [`apps/axiomfolio/package.json`](../../../apps/axiomfolio/package.json) |
| PWA package shared (`@paperwork-labs/pwa`) | Done | `packages/pwa/` (Track M.7) |
| Feature flag proxy | Done | `apps/axiomfolio/src/proxy.ts` (`NEXT_PUBLIC_AXIOMFOLIO_*`) |
| Full route parity + Vite deletion | **Done (2026-04-27)** | Track G4 |

The sections below are **historical** (original plan and rationale); they were
written when the interim directory was `apps/axiomfolio-next/`.

## Why

AxiomFolio is the last React-Vite SPA in the monorepo. Every other consumer-
facing product (`filefree`, `launchfree`, `distill`, `trinkets`, `studio`)
runs on Next.js 16 App Router on Vercel. The divergence costs us:

1. **Two frontend stacks to maintain.** Different routing, different data-
   fetching mental model, different env var conventions (`VITE_*` vs
   `NEXT_PUBLIC_*`), different SSR story.
2. **No SSR → no SEO for public pages** (`/pricing`, `/why-free`, marketing
   surfaces). Today those render blank to crawlers until hydration.
3. **No RSC → no streaming.** Dashboard first-paint is hydrate-then-fetch,
   waterfalling three React Query calls. RSC + PPR (Cache Components) would
   let us stream the first meaningful chunk immediately.
4. **Auth is stuck in `localStorage`.** Cannot do server-side gating in
   middleware. Means we can't easily build experiences like
   "only-admin dashboards with first-paint data."
5. **Render static hosting** (the current frontend target) rules out ISR
   and edge middleware. A Vercel-hosted Next app gets both for free.
6. **Studio integration.** Every other product uses cross-app patterns
   (shared `@paperwork-labs/ui` registry, consistent nav, Ask-Brain
   drawer) that assume RSC-friendly structure. AxiomFolio's Vite tree
   can't easily consume those.

The conclusion is not "rewrite everything"; the conclusion is "stop paying
the per-stack tax." A migration now lets the Phase C DAG, Phase D persona
operator UI, and the shared component registry all speak the same language.

## Scope (historical)

- ~~`apps/axiomfolio/`~~ — was Vite 8 + React 19 + react-router-dom 7 + Tailwind 4
  + axios + TanStack React Query + 50+ lazy routes + custom PWA (**removed 2026-04-27**).
- `apis/axiomfolio/render.yaml` — frontend service block (swap
  `runtime: static` for a Node/standalone target, or move frontend to
  Vercel and leave Render for API/workers only).

**Out of scope** (separate efforts):

- Backend changes (`apis/axiomfolio/`). Public API contract does not change.
- Auth identity provider (stays custom JWT / `qm_token` for Q3; Clerk/
  Supabase migration is a separate quarter).
- Product feature work. This migration preserves behaviour.

## Current stack (audit findings)

| Area | Value |
|---|---|
| Bundler | Vite 8 + `@vitejs/plugin-react` + `@tailwindcss/vite` |
| React | 19.2 |
| Routing | `react-router-dom` 7 (50+ `React.lazy` routes in `App.tsx`) |
| Data | axios + TanStack React Query (no SWR) |
| Styling | Tailwind 4 + Radix + shadcn-style primitives |
| Auth | `AuthContext` + `localStorage['qm_token']` (OAuth hash callback) |
| PWA | Custom `public/sw.js` + `src/pwa/register.ts` |
| Env vars | `import.meta.env.VITE_API_BASE_URL`, `VITE_ENABLE_EXTERNAL_SIGNALS` |
| Hosting | Render static (`rootDir: apps/axiomfolio`, `dist` publish) |
| Tests | Vitest + Testing Library + Ladle stories |
| Lines of code | ~60 pages; top 10 pages hold ~12k lines (Options, Connections, Market, etc.) |

Full audit: see this doc's "Appendix A — route inventory" below.

## Target stack

| Area | Value |
|---|---|
| Framework | Next.js 16 App Router |
| Bundler | Turbopack (matches `filefree`, `launchfree`, `studio`, `distill`, `trinkets`) |
| React | 19.2 |
| Routing | `app/` directory, co-located layouts, `use client` boundaries |
| Data | React Query preserved on client; RSC for above-the-fold data on public pages |
| Auth | `qm_token` read server-side from httpOnly cookie (migrated from `localStorage`) for middleware gating; client still has `AuthContext` for mutations |
| PWA | `next-pwa` or equivalent App Router-aware setup |
| Env vars | `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_ENABLE_EXTERNAL_SIGNALS` |
| Hosting | Vercel (same account as `filefree`, `launchfree`, `studio`, `distill`, `trinkets`) |
| Render | API + workers only — `axiomfolio-frontend` decommissioned |

## Approach

**Incremental in-place**, not big-bang rewrite. Three phases.

### Phase 1 — Shell swap (≈5 dev-days)

Goal: a Next.js 16 app runs at `apps/axiomfolio/` with one page (`/login`)
ported. Everything else 404s. We validate hosting + env + auth cookie
before touching complex routes.

1. `apps/axiomfolio/package.json`: swap Vite deps for Next.js 16. Keep
   all React Query, Radix, Tailwind, Recharts, etc. deps.
2. `apps/axiomfolio/next.config.ts`: Turbopack on, rewrites for `/api`
   pointing at `VITE_API_BASE_URL` → `NEXT_PUBLIC_API_BASE_URL`.
3. `apps/axiomfolio/src/app/layout.tsx`: root layout + Providers (Query
   client, Auth, ColorMode, PortfolioAccount).
4. `apps/axiomfolio/src/app/login/page.tsx`: port `pages/Login.tsx` as-is
   with `"use client"`.
5. `apps/axiomfolio/middleware.ts`: read `qm_token` cookie, redirect
   unauthenticated users away from anything not under `/{login,register,
   auth,invite,share,pricing,why-free}`.
6. Backend change: `AuthContext.login`/`register` also set a SameSite=
   Lax httpOnly cookie via a new `/api/v1/auth/set-cookie` endpoint
   (copies current `qm_token` into an httpOnly cookie). No behaviour
   change; future removal of `localStorage` deferred to Phase 3.
7. Deploy preview on Vercel. Verify login works end-to-end against
   staging API. Verify middleware redirects work.

**Deliverable:** a Vercel preview URL that can log in and 404 for
everything else. Production remains on Render+Vite.

### Phase 2 — Page porting by tree (≈15–20 dev-days)

Route tree is grouped by feature area. Port one subtree at a time. Each
subtree ships as its own PR, gated behind `NEXT_PUBLIC_AF_NEXT=true` on
Vercel so QA can flip feature flags.

Port order (dependency-driven):

1. `/login`, `/register`, `/auth/*`, `/invite/:token`, `/pricing`,
   `/why-free` (public, simple, already ported in Phase 1 for `/login`).
   ~2 days.
2. `/settings/*` — small leaf pages; good warm-up for the RSC split
   pattern. ~3 days.
3. `/market/*`, `/lab/*`, `/signals/*`, `/trade-cards/today`,
   `/shadow-trades` — dashboard main tree. ~5 days.
4. `/portfolio/*`, `/holding/:symbol` — the big tables + charts,
   highest-risk ports. ~5 days.
5. `/settings/admin/*` — admin-only, lowest traffic, last. ~2 days.
6. `/share/c/:token` — public share link; port late because the PWA
   shell and analytics matter. ~1 day.

Per-subtree recipe:

- Copy `pages/FooBar.tsx` → `app/foo-bar/page.tsx` + `"use client"`.
- Replace `useNavigate` → `useRouter` from `next/navigation`.
- Replace `Link from "react-router-dom"` → `Link from "next/link"`.
- Replace `useParams`, `useSearchParams`, `Navigate` with App Router
  equivalents.
- Swap `import.meta.env.VITE_*` → `process.env.NEXT_PUBLIC_*`.
- Flag feature behind `NEXT_PUBLIC_AF_NEXT`; if false, Vite app serves
  (during transition).

Heavy pages (`PortfolioOptions.tsx`, `SettingsConnections.tsx`,
`MarketDashboard.tsx`) may need `dynamic(..., { ssr: false })` wrappers
around TradingView, Recharts, `lightweight-charts` — these do not
tolerate SSR without work.

### Phase 3 — Cutover + cleanup (≈5 dev-days)

1. Switch default of `NEXT_PUBLIC_AF_NEXT` to `true` on Vercel prod.
   Monitor for 48h; rollback is a single env var flip.
2. Remove Vite config (`vite.config.ts`, `index.html`, `src/main.tsx`,
   `src/App.tsx`) + feature flag gating.
3. Migrate `localStorage['qm_token']` writes to the httpOnly cookie;
   remove `AuthContext`'s direct `localStorage` reads (keep as fallback
   for tabs opened before the migration; auto-migrate on first request).
4. Delete `axiomfolio-frontend` from `apis/axiomfolio/render.yaml`;
   Render keeps only the API + workers.
5. Update `docs/INFRA.md`, `docs/axiomfolio/*` to reflect Next.js.
6. Update `apps/studio/src/data/system-graph.json` (via
   `scripts/system_graph.py`) — no change to `axiomfolio.frontend` node
   shape, just the description from "React 19 + Vite 8. Pending
   migration to Next.js." to "Next.js 16 App Router on Vercel."

## PWA

Vite PWA is custom (`public/sw.js`). Next.js has a few options:

- **`next-pwa`** — most popular, sometimes lags Next major versions.
- **Workbox via App Router route handler** — more work, more control.
- **Drop PWA** — if installs/offline aren't driving retention we drop
  the complexity entirely.

Recommended: evaluate during Phase 1 spike. If retention data shows PWA
installs drive < 5% of DAU, drop it.

## Auth migration detail

Today:

```ts
localStorage.setItem('qm_token', token);
axios.interceptors.request.use((c) => {
  const t = localStorage.getItem('qm_token');
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});
```

After Phase 1:

- Login endpoint also writes `qm_token` to a `Secure; HttpOnly;
  SameSite=Lax; Path=/` cookie (30d expiry matching current token).
- Middleware reads cookie → redirects if absent.
- Client still reads `localStorage` for backwards compat + axios header.

After Phase 3:

- Next.js middleware is the single source of auth truth.
- Axios interceptor stops reading `localStorage`; cookie is
  automatically sent with same-origin requests. Cross-origin (`api.
  axiomfolio.com` vs `axiomfolio.paperworklabs.com`) continues to use
  the `Authorization: Bearer` header — filled by a server action or
  RSC that reads the cookie and passes it to the client.

## Deployment

Phase 1 Vercel deploy:

- New Vercel project `axiomfolio-web` in the paperwork-labs workspace.
- Domain: `preview.axiomfolio.paperworklabs.com` during migration;
  cutover to `axiomfolio.paperworklabs.com` at Phase 3.
- `apps/axiomfolio/vercel.json`: same shape as the other 5 Next apps,
  with `installCommand` scoped to `@paperwork-labs/axiomfolio...` and
  the Dependabot ignoreCommand already in use.

Render change: `apis/axiomfolio/render.yaml` removes the
`axiomfolio-frontend` service (keep API + workers). Blueprint sync
needed on Render dashboard.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| SSR breaks TradingView/Recharts/lightweight-charts | `dynamic(..., { ssr: false })` at the page boundary. Already in use by Studio. |
| `localStorage`-based auth cannot be read server-side | httpOnly cookie shim in Phase 1 (both written at login) |
| React Router patterns deeply embedded | Feature-flag both roots; port tree by tree; cannot ship partial half-states |
| PWA service worker scoping | Evaluate in Phase 1; drop if usage is low |
| Env var renames miss a caller | Grep gate in CI: fail if `import.meta.env` appears outside `archive/` once Phase 3 starts |
| Vercel free-tier build minutes | AxiomFolio shares the Dependabot `ignoreCommand`; CI-only builds for main + preview |
| Prod outage window | Feature flag `NEXT_PUBLIC_AF_NEXT` → rollback is one env var, zero-downtime |

## Not decided yet

- **Cookie domain.** `.paperworklabs.com` (SSO with Studio + marketing)
  vs app-scoped. Ties to whether we eventually consolidate auth with
  FileFree/LaunchFree.
- **RSC usage.** MVP is "use client" everywhere (same as today).
  Incrementally convert public pages and settings pages to RSC after
  cutover. Portfolio/options pages likely stay client-bound.
- **Monorepo shared components.** A `packages/ui` with `@paperwork-labs/
  ui` package would let AxiomFolio + Studio + others share cards,
  drawers, DAG primitives. This is its own effort and doesn't block
  the migration.

## Effort summary

| Phase | Dev-days | Calendar time (1 FTE) |
|---|---|---|
| 1. Shell swap | ~5 | 1 week |
| 2. Page porting | ~15–20 | 3–4 weeks |
| 3. Cutover + cleanup | ~5 | 1 week |
| **Total** | **~25–30** | **5–6 weeks** |

Add ~20% buffer for surprise and holiday weeks → **~30–36 dev-days**
calendar. Bigger if PWA parity is a hard requirement; smaller if we
drop PWA.

## Dependencies

- PR #132 (streamline Phase A, Vercel Dependabot ignore) — merged before
  Phase 1 ships so AxiomFolio's Vercel project doesn't burn build minutes.
- Studio `/admin/architecture` DAG (PR #133) — informs Phase 2 port
  order via the dependency chain; also gets updated to reflect
  AxiomFolio's stack change in Phase 3.
- `persona_models` / `PersonaSpec` (Phase D) — not a hard dependency.
  AxiomFolio's admin pages (`AdminAgent.tsx`) will consume the governance
  table if available, but ship without it.

## Appendix A — Route inventory

50+ routes across these groups (full list in the audit at
[`docs/axiomfolio/plans/PLATFORM_REVIEW_2026Q2.md`](./PLATFORM_REVIEW_2026Q2.md)):

- **Public (6):** `/login`, `/register`, `/pricing`, `/why-free`, `/auth/*`,
  `/invite/:token`, `/share/c/:token`.
- **Dashboard home (1):** `/`, `/onboarding`.
- **Market (8):** `/market`, `/market/universe`, `/market/tracked`,
  `/market/workspace`, `/signals/*`, `/lab/*`, `/learn/education`.
- **Portfolio (8):** `/portfolio/*`, `/holding/:symbol`.
- **Accounts/Connect (2):** `/connect`, `/accounts/manage`.
- **Settings (12):** `/settings/*` (non-admin).
- **Admin (5):** `/settings/admin/system`, `/settings/admin/users`,
  `/settings/admin/agent`, `/settings/admin/picks`.

## Appendix B — Env var migration

| Vite | Next.js |
|---|---|
| `VITE_API_BASE_URL` | `NEXT_PUBLIC_API_BASE_URL` |
| `VITE_ENABLE_EXTERNAL_SIGNALS` | `NEXT_PUBLIC_ENABLE_EXTERNAL_SIGNALS` |
| `VITE_PROXY_TARGET` | replaced by `next.config.ts` `rewrites` |
| `import.meta.env.DEV` | `process.env.NODE_ENV === "development"` |

## Appendix C — Decision log

- 2026-04-24: plan drafted after Studio Phase C DAG shipped; the
  divergence from the other 5 Next.js apps was the triggering pain.
- Ownership: engineering (staff eng).
- Final sign-off required from: trading (AxiomFolio owner),
  infra-ops (Render/Vercel change).
