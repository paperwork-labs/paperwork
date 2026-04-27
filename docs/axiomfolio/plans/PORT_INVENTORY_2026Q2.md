---
owner: engineering
last_reviewed: 2026-04-26
doc_kind: plan
domain: other
status: active
---
# AxiomFolio port inventory (2026 Q2)

Generated: 2026-04-26
Coordinator: `chore/axiomfolio-port-survey` (Track G coordinator subagent)
Companion plan: [NEXTJS_MIGRATION_2026Q3.md](./NEXTJS_MIGRATION_2026Q3.md)
(plan filename retains `Q3` for traceability — the founder accelerated the
schedule into Q2 under the Q2 Tech Debt Convergence sprint, Track G).

## Why this doc exists

Track G of the Q2 Tech Debt Convergence sprint folded the Vite app into the
Next.js app and renamed the directory (**completed 2026-04-27**, Track G4):

1. Port every remaining Vite route — done; canonical app is `apps/axiomfolio/`
   (this doc’s historical counts referred to the interim `apps/axiomfolio-next/` tree).
2. `git mv` + Vite tree deletion + Render `axiomfolio-frontend` removal from
   root `render.yaml` — done.

This document inventories what is already ported, what is left, and how
the remaining routes were grouped into parallel sub-subagent batches.

## Methodology

- Vite routes were enumerated from `apps/axiomfolio/src/App.tsx` (removed
  2026-04-27; use git history for the React Router root).
- Next routes were enumerated from `apps/axiomfolio/src/app/**/page.tsx` via `Glob`.
- A "real port" is a `page.tsx` that renders an actual ported client
  component (e.g. `<MarketDashboardClient />`). A "stub" is a page that
  contains only placeholder copy ("Next port lands in the next PR…")
  with no hookup to a real client component.

## Status snapshot

| State | Count |
|---|---|
| Vite routes (App.tsx unique paths, excluding pure `Navigate` redirects) | 47 |
| Already real-ported in `axiomfolio-next/` | 21 |
| Stubs in `axiomfolio-next/` (need full port) | 4 |
| Missing entirely from `axiomfolio-next/` | 22 |
| **Total to port (this sprint)** | **26** |

## Already ported (real implementations)

| Vite route | Next route | Notes |
|---|---|---|
| `/login` | `/login` | Direct port (Track E) |
| `/register` | `/register` | Direct port (Track E) |
| `/onboarding` | `/onboarding` | Direct port (Track E) |
| `/auth/callback` | `/auth/callback` | Direct port |
| `/auth/forgot-password` | `/auth/forgot-password` | Direct port |
| `/auth/reset-password` | `/auth/reset-password` | Direct port |
| `/pricing` | `/pricing` | Direct port |
| `/connect` | `/connect` | Direct port |
| `/accounts/manage` | `/accounts/manage` | 402 LOC client |
| `/holding/:symbol` | `/holding/[symbol]` | `dynamic({ssr:false})` for chart |
| `/lab/strategies` | `/strategies` | Path alias (legacy `/strategies`) |
| `/lab/strategies/manage` | `/strategies/manage` (redirect) | Redirects to `/strategies` |
| `/lab/strategies/:strategyId` | `/strategies/[strategyId]` | `dynamic({ssr:false})` |
| `/lab/intelligence` | `/market/intelligence` | Lives under `/market/*` in Next |
| `/learn/education` | `/market/education` | Lives under `/market/*` in Next |
| `/market/dashboard` | `/market/dashboard` | `MarketDashboardClient` |
| `/market/tracked` | `/market/tracked` | `MarketTrackedClient` |
| `/signals` | `/signals` | `SignalsHubClient` |
| `/signals/candidates` | `/signals/candidates` | `SignalsCandidatesClient` |
| `/signals/regime` | `/signals/regime` | `SignalsRegimeClient` |
| `/signals/stage-scan` | `/signals/stage-scan` | `SignalsStageScanClient` |
| `/signals/picks` | `/signals/picks` | `SignalsPicksClient` |
| `/trade-cards/today` | `/trade-cards/today` | `TradeCardsTodayClient` |
| `/shadow-trades` | `/shadow-trades` | `ShadowTradesClient` |
| `/settings/profile` | `/settings/profile` | `SettingsProfile` |
| `/settings/preferences` | `/settings/preferences` | `SettingsPreferences` |
| `/settings/notifications` | `/settings/notifications` | Client |
| `/settings/connections` | `/settings/connections` | Client |
| `/settings/data-privacy` | `/settings/data-privacy` | Client |
| `/settings/mcp` | `/settings/mcp` | Client |
| `/settings/ai-keys` | `/settings/ai-keys` | Client |
| `/settings/trading/account-risk` | `/settings/account-risk` | Path alias |
| `/settings/admin/users` | `/settings/users` | Path alias |
| (Clerk) | `/sign-in/[[...sign-in]]` | New (Track B Clerk) |
| (Clerk) | `/sign-up/[[...sign-up]]` | New (Track B Clerk) |
| (`/lab` lab landing) | `/backtest` | New `BacktestLabClient` (Track E) |

## Stubs in `axiomfolio-next/` (need full port)

These have a `page.tsx` but it just renders placeholder copy. A real port
must wire up an actual client component (or in Scanner's case, a redirect):

| Vite route | Vite source | LOC | Next stub path | Action |
|---|---|---|---|---|
| `/` | `pages/Home.tsx` | 116 | `app/page.tsx` | Port `Home.tsx` → `HomeClient` |
| `/portfolio` | `pages/portfolio/PortfolioTabShell.tsx` | 37 | `app/portfolio/page.tsx` | Port `PortfolioTabShell` (small wrapper that renders sub-tabs) |
| `/market/scanner` | `pages/Scanner.tsx` | 8 | `app/scanner/page.tsx` | Replace stub with `redirect('/market/tracked?mode=scan')` (Vite is also just a redirect) |
| `/settings/admin/system` | `pages/SystemStatus.tsx` | 939 | `app/system-status/page.tsx` | Port `SystemStatus.tsx` → `SystemStatusClient` (currently 96-line placeholder with hard-coded tile counts) |

## Unported routes (no Next page.tsx)

Sorted by Vite source file LOC descending so heavy ports get matched to
batches that can absorb them:

| Vite route | Vite source | LOC | Target Next path | Heaviness | Notes / dependencies |
|---|---|---|---|---|---|
| `/portfolio/options` | `pages/portfolio/PortfolioOptions.tsx` | **2160** | `app/portfolio/options/page.tsx` | XL | Largest single file in the app. IV-rank, options chain, charts. Needs `dynamic({ssr:false})` for chart libs. |
| `/portfolio/categories` | `pages/portfolio/PortfolioCategories.tsx` | 1366 | `app/portfolio/categories/page.tsx` | L | Allocation/category dashboards, lots of state. |
| `/market/workspace` | `pages/PortfolioWorkspace.tsx` | 1349 | `app/market/workspace/page.tsx` | L | Top-down market workspace, charts. |
| `/portfolio/tax` | `pages/portfolio/PortfolioTaxCenter.tsx` | 892 | `app/portfolio/tax/page.tsx` | L | Tax-lots, wash sales. Heavy data. |
| `/portfolio/holdings` | `pages/portfolio/PortfolioHoldings.tsx` | 721 | `app/portfolio/holdings/page.tsx` | L | Big positions table. |
| `/settings/admin/agent` | `pages/AdminAgent.tsx` | 655 | `app/settings/admin/agent/page.tsx` | M | Admin only — guard with `RequireAdmin` (already ported as `RequireAdmin` component). |
| `/settings/admin/picks` | `pages/admin/PicksValidator.tsx` | 508 | `app/settings/admin/picks/page.tsx` | M | Admin picks validator. |
| `/portfolio/orders` | `pages/portfolio/PortfolioOrders.tsx` | 479 | `app/portfolio/orders/page.tsx` | M | Orders table, status filters. |
| `/portfolio/transactions` | `pages/portfolio/PortfolioTransactions.tsx` | 405 | `app/portfolio/transactions/page.tsx` | M | Transactions table. |
| `/lab/monte-carlo` | `pages/Backtest/MonteCarlo.tsx` | 354 | `app/lab/monte-carlo/page.tsx` | M | Monte Carlo backtest UI. Charts via Recharts. |
| `/why-free` | `pages/WhyFree.tsx` | 227 | `app/why-free/page.tsx` | S | Public marketing — RSC candidate. |
| `/lab/walk-forward` | `pages/Backtest/WalkForward.tsx` | 226 | `app/lab/walk-forward/page.tsx` | M | Walk-forward backtest UI. Charts via Recharts. |
| `/settings/connections/historical-import` | `pages/settings/HistoricalImportWizard.tsx` | 197 | `app/settings/connections/historical-import/page.tsx` | M | Multi-step wizard. |
| `/share/c/:token` | `pages/share/ChartShare.tsx` | 160 | `app/share/c/[token]/page.tsx` | S | Public share link. PWA shell + chart. |
| `/invite/:token` | `pages/Invite.tsx` | 116 | `app/invite/[token]/page.tsx` | S | Invite acceptance flow. |
| `/portfolio/import` | `pages/PortfolioImport.tsx` | 77 | `app/portfolio/import/page.tsx` | S | Small import gateway. |
| `/portfolio/positions` | `pages/portfolio/PositionsTabShell.tsx` | 69 | `app/portfolio/positions/page.tsx` | S | Tab shell for positions. |
| `/portfolio/activity` | `pages/portfolio/ActivityTabShell.tsx` | 38 | `app/portfolio/activity/page.tsx` | S | Tab shell for activity. |
| `/market/universe` | `pages/market/Universe.tsx` | 19 | `app/market/universe/page.tsx` | XS | Just renders `MarketTracked` — `MarketTrackedClient` already exists, so a 5-line wrapper. |
| `/market` | (alias of `/market/dashboard`) | n/a | `app/market/page.tsx` | XS | Add `redirect('/market/dashboard')` or wrap `MarketDashboardClient`. |
| `/portfolio/income` | `pages/PortfolioIncome.tsx` | 24 | `app/portfolio/income/page.tsx` | XS | Tiny — `IncomeCalendar` already ported. |
| `/learn/education` | (alias) | n/a | `app/learn/education/page.tsx` | XS | Path alias to existing `/market/education`. Add a `redirect()` page so Vite-era bookmarks survive. |

## Path normalization (informational)

The Next port currently uses some shorter paths than the Vite canonical
paths (e.g. `/strategies` instead of `/lab/strategies`). The Vite app
serves the canonical paths and falls back to the legacy ones via
`<Navigate replace>`. To preserve deep-link parity post-cutover, we plan
to add Next `redirect()` pages for the legacy shorter paths in a
follow-up PR (or as part of Batch G below). For now, both shapes coexist;
internal nav uses the Next paths.

The legacy redirects we owe but **don't** block this sprint on:

- `/lab/strategies` → `/strategies` (or vice-versa)
- `/lab/intelligence` → `/market/intelligence`
- `/learn/education` → `/market/education`
- `/settings/admin/system` → `/system-status`
- `/settings/admin/users` → `/settings/users`

Owner: founder / Track G review.

## Batch assignment for parallel sub-subagents

Each batch ships as ONE PR with all routes in the batch. The batch is
opened in its own git worktree at `/tmp/wt-pwl/wt-af-port-batch-<X>`
on a branch named `axiomfolio-next/port-batch-<X>`. Each sub-subagent
runs the established Next port pattern:

1. Copy `pages/<Foo>.tsx` → `apps/axiomfolio-next/src/components/<area>/<Foo>Client.tsx`.
2. Add `"use client";` to the new client component.
3. Replace `useNavigate` → `useRouter` from `next/navigation`.
4. Replace `react-router-dom` `Link` → `next/link` `Link`.
5. Replace `useParams` / `useSearchParams` / `useLocation` with Next equivalents.
6. Replace `import.meta.env.VITE_*` → `process.env.NEXT_PUBLIC_*`.
7. Wrap heavy chart code in `dynamic(..., { ssr: false })`.
8. Create `apps/axiomfolio-next/src/app/<route>/page.tsx` that wraps the
   client in `<RequireAuthClient>` (or `<RequireAdmin>` for admin routes;
   public pages skip the gate).
9. Use the existing `axiomfolio-next` Clerk wrapper. **Do not** rewrite
   auth — Track B2 will swap `qm_token` validation for Clerk JWT later.
10. Update `apps/axiomfolio-next/src/components/sidebar/Nav*.tsx`
    nav links if the new route should appear in the sidebar (if unsure,
    leave it for the founder review pass).

If a route uses a pattern that doesn't have a clean Next equivalent
(e.g. `useNavigate` with a callback that uses complex react-router state,
or a global `<Navigate>` that depends on multiple URL pieces), the
sub-subagent **must flag it in the PR body** rather than hacking around
it.

### Batch A — Public marketing (3 routes, ~503 LOC)

- `/why-free` → `app/why-free/page.tsx` (227 LOC, RSC candidate)
- `/invite/[token]` → `app/invite/[token]/page.tsx` (116 LOC)
- `/share/c/[token]` → `app/share/c/[token]/page.tsx` (160 LOC, public, no auth)

### Batch B — Portfolio shells & small (5 routes, ~245 LOC)

- `/portfolio` → replace stub `app/portfolio/page.tsx` with full `PortfolioTabShell` port (37 LOC)
- `/portfolio/positions` → `app/portfolio/positions/page.tsx` (69 LOC)
- `/portfolio/activity` → `app/portfolio/activity/page.tsx` (38 LOC)
- `/portfolio/income` → `app/portfolio/income/page.tsx` (24 LOC)
- `/portfolio/import` → `app/portfolio/import/page.tsx` (77 LOC)

### Batch C — Portfolio medium (3 routes, ~1605 LOC)

- `/portfolio/transactions` → `app/portfolio/transactions/page.tsx` (405 LOC)
- `/portfolio/orders` → `app/portfolio/orders/page.tsx` (479 LOC)
- `/portfolio/holdings` → `app/portfolio/holdings/page.tsx` (721 LOC)

### Batch D — Portfolio Options only (1 route, 2160 LOC)

- `/portfolio/options` → `app/portfolio/options/page.tsx` (2160 LOC)

This file is large enough to warrant a dedicated sub-subagent. Likely
needs `dynamic({ssr:false})` for chart libs and IV-rank surface.

### Batch E — Portfolio heavy (2 routes, ~2258 LOC)

- `/portfolio/categories` → `app/portfolio/categories/page.tsx` (1366 LOC)
- `/portfolio/tax` → `app/portfolio/tax/page.tsx` (892 LOC)

### Batch F — Lab + Workspace (3 routes, ~1929 LOC)

- `/lab/walk-forward` → `app/lab/walk-forward/page.tsx` (226 LOC)
- `/lab/monte-carlo` → `app/lab/monte-carlo/page.tsx` (354 LOC)
- `/market/workspace` → `app/market/workspace/page.tsx` (1349 LOC,
  PortfolioWorkspace.tsx)

### Batch G — Discovery + Home (5 routes, ~135 LOC)

- `/market/universe` → `app/market/universe/page.tsx` (19 LOC, just wraps `MarketTrackedClient`)
- `/market` → `app/market/page.tsx` (redirect to `/market/dashboard`)
- `/scanner` → replace stub with `redirect('/market/tracked?mode=scan')`
- `/learn/education` → `app/learn/education/page.tsx` (redirect to `/market/education`)
- `/` → replace stub `app/page.tsx` with full Home port (116 LOC)

### Batch H — Admin + System Status (4 routes, ~2299 LOC)

- `/settings/admin/agent` → `app/settings/admin/agent/page.tsx` (655 LOC, gate with `RequireAdmin`)
- `/settings/admin/picks` → `app/settings/admin/picks/page.tsx` (508 LOC, gate with `RequireAdmin`)
- `/settings/connections/historical-import` → `app/settings/connections/historical-import/page.tsx` (197 LOC, multi-step wizard)
- `/system-status` → replace 96-LOC stub with full SystemStatus port (939 LOC source — admin-gated in Vite, currently public in Next stub; gate with `RequireAdmin`)

## Total port effort

| Batch | Routes | LOC (Vite source) |
|---|---|---|
| A | 3 | ~503 |
| B | 5 | ~245 |
| C | 3 | ~1,605 |
| D | 1 | 2,160 |
| E | 2 | 2,258 |
| F | 3 | 1,929 |
| G | 5 | ~135 |
| H | 4 | ~2,299 |
| **Total** | **26 routes** | **~11,134 LOC** |

This excludes the 47 routes already real-ported (Track E + Track B Clerk
work). It excludes pure `Navigate` redirects in the Vite App.tsx (those
are not real routes).

## Progress checklist

Update this checklist as each batch lands:

- [ ] Batch A — Public marketing
- [ ] Batch B — Portfolio shells & small
- [ ] Batch C — Portfolio medium
- [ ] Batch D — Portfolio Options
- [ ] Batch E — Portfolio Categories + Tax
- [ ] Batch F — Lab + Workspace
- [ ] Batch G — Discovery + Home
- [ ] Batch H — Admin + System Status

After all eight batches land and a 7-day parity bake clears, Track G4
(rename, delete Vite tree, drop Render service) is unblocked.

## Items flagged for founder input

1. **Path normalization** — should we add the Vite-canonical aliases
   (e.g. `/lab/strategies` → `/strategies`) as Next `redirect()` pages,
   or migrate the Next paths to match Vite canonical (which would mean
   moving directories)? Either choice is reversible; not blocking.
2. **`/system-status` admin gate** — Vite gates SystemStatus behind
   `RequireAdmin`; the Next stub is currently public. Batch H assumes we
   restore the admin gate to match Vite. Confirm.
3. **`/why-free` RSC vs CSR** — public marketing pages should be RSC
   for SEO. Batch A defaults to RSC unless `WhyFree.tsx` uses anything
   that requires `"use client"`.
4. **PWA / `/share/c/[token]`** — the share page is the only route
   that mattered for the PWA install funnel in Vite. If we keep PWA
   under Next, this page must register the service worker. If we drop
   PWA, this is just a public chart. Defer the PWA decision but note
   it in the Batch A PR.

## Out of scope (Track G4, deferred)

The following are **not** part of this sprint and **must not** be done
by sub-subagents:

- `git mv apps/axiomfolio-next apps/axiomfolio` (rename)
- Delete `apps/axiomfolio` legacy Vite tree
- Update `render.yaml` to remove `axiomfolio-frontend`
- Update `docs/INFRA.md` and `system_graph.py` to reflect Next-only
- Decommission Render `axiomfolio-frontend` service

These are gated on a 7-day parity bake after all eight batches above
land. They are tracked in
[`NEXTJS_MIGRATION_2026Q3.md`](./NEXTJS_MIGRATION_2026Q3.md) Phase 3.
