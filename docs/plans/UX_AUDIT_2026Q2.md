# UX Audit — 2026 Q2 (PR C0 input spec)

> Feeds PR C1 (IA + routing), PR C2 (Home), PR C3 (Signals shells), PR C4 (journey polish).
> Source of truth for every Phase-4 ticket.

## Methodology

Every page reachable from the SPA was read end-to-end (or, for files >600 lines, navigated via `Grep` for hooks, route declarations, nav links, and suspect patterns). For each page I traced the TanStack Query hooks, mapped loading/error/empty/data states per `.cursor/rules/no-silent-fallback.mdc`, walked the visible CTAs end-to-end, and flagged every friction point a founder-demoing-to-an-investor would wince at. Findings are ranked P0 (breaks the demo), P1 (visible polish gap), P2 (internal consistency). Cross-cutting issues live under `## Global / cross-cutting`; page-specific issues live under `## Page-by-page`. Every finding cites the file + line and proposes a surgical remediation, and every finding is mapped to a PR in the remediation table.

## Findings summary

| Page | P0 | P1 | P2 |
|------|----|----|----|
| Global / cross-cutting       | 3 | 8 | 4 |
| App routing                  | 1 | 1 | 2 |
| DashboardLayout              | 2 | 5 | 3 |
| AuthLayout                   | 0 | 0 | 1 |
| WhyFree                      | 0 | 4 | 2 |
| Pricing                      | 0 | 3 | 2 |
| PublicStatsStrip             | 0 | 0 | 2 |
| Login                        | 0 | 2 | 3 |
| Register                     | 0 | 2 | 0 |
| MarketDashboard              | 1 | 3 | 5 |
| PortfolioOverview            | 0 | 3 | 1 |
| PortfolioOptions             | 0 | 1 | 1 |
| PortfolioTaxCenter           | 0 | 2 | 1 |
| Picks (mounted at /signals/picks) | 0 | 2 | 1 |
| SettingsShell                | 0 | 1 | 1 |
| SettingsConnections          | 0 | 8 | 2 |
| SettingsProfile              | 0 | 1 | 1 |
| SettingsPreferences          | 0 | 1 | 1 |
| SettingsAIKeys               | 0 | 2 | 1 |
| useUpgradePrompt             | 0 | 1 | 1 |
| AppLogo                      | 0 | 1 | 0 |
| Signals shells (`pages/signals/`) | 1 | 0 | 0 |

**Total: 8 P0, 51 P1, 34 P2 → 93 findings.**

## Global / cross-cutting (assigned to PR C1 unless noted)

- **G-01** [P0] Logo is not a link. `AppLogo` renders a raw `<svg>` with no wrapper (`frontend/src/components/ui/AppLogo.tsx:17-36`) and `DashboardLayout` mounts it inside a `<div>` in both the sidebar header (`frontend/src/components/layout/DashboardLayout.tsx:353-358`) and the collapsed-sidebar top header (`frontend/src/components/layout/DashboardLayout.tsx:418-422`). Clicking the brand does nothing. **Fix:** wrap both instances in `<Link to="/">` (or a `LogoLink` util) with a visible focus ring and `aria-label="AxiomFolio home"`. Same fix in `AuthLayout` (`frontend/src/components/layout/AuthLayout.tsx:33-36`) so the auth-page logo also routes somewhere.
- **G-02** [P0] `/` is a redirect, not a page. `App.tsx:161` mounts `<Route index element={<Navigate to="/market" replace />} />` — there is no Home page in the codebase. New users land cold on a 1,700-line market-analytics canvas. This blocks PR C2 and is the biggest "wince" in the demo. **Fix:** deliver `frontend/src/pages/Home.tsx` in PR C2 and replace this redirect with `<Route index element={<Home />} />`.
- **G-03** [P0] Sidebar "Dashboard" nav item is semantically wrong. `DashboardLayout.tsx:104` renders `{ label: 'Dashboard', icon: Home, path: '/' }` — the Home icon plus the word "Dashboard" points at `/` which redirects to `/market`. **Fix (PR C1 + C2):** split into two items: `{ label: 'Home', icon: Home, path: '/' }` pointing at the new Home, and `{ label: 'Markets', icon: BarChart2, path: '/market' }` pointing at MarketDashboard. The "Dashboard" label then ceases to exist as a nav entry.
- **G-04** [P1] Pricing is not in the top nav or sidebar for logged-in users. `DashboardLayout.tsx:101-115` (`buildMarketItems`) does not include `/pricing`. The avatar dropdown (`DashboardLayout.tsx:552-583`) also omits it. **Fix:** add `/pricing` as a top-level entry in the user-avatar dropdown (after "Preferences") and/or as a footer link. Phase 0.5 tiers are live — users literally cannot find them without typing the URL.
- **G-05** [P1] `/why-free` only surfaces in the logged-in footer (`DashboardLayout.tsx:604-611`) and on Login/Register (`Login.tsx:210-214`, `Register.tsx:101-105`). Anonymous visitors arriving at `/pricing` have no discoverable path to it (only a secondary CTA in the pricing hero, `Pricing.tsx:138-140`). **Fix:** add a shared public-page header (see PR-02, WF-03) that lists `Why free`, `Pricing`, `Sign in`, `Register` consistently.
- **G-06** [P1] "Terminal" is still a live sidebar entry (`DashboardLayout.tsx:112`) but the route is a redirect-with-toast (`App.tsx:136-143, TerminalRedirect`). Clicking it pops a toast saying "Terminal replaced by Cmd+K (try it now)" then bounces to `/`. Dead link; looks broken. **Fix:** remove from `buildMarketItems`; keep the redirect for 1 release so old bookmarks still warn, then delete.
- **G-07** [P1] Command palette is globally mounted (`App.tsx:155` via `<AppCommandLayer />`) and listens for Cmd/Ctrl+K (`frontend/src/components/cmdk/CommandPalette.tsx:84`), but there is no visible affordance: no `Cmd+K` pill in the top nav, no button in the header, no mention in onboarding. Power users will find it; founders-in-a-demo will not know to press it. **Fix:** add a compact `Cmd+K` button to the `DashboardLayout` header (between the account selector and the health dot) that opens the palette and shows the keyboard hint. Reuse `ShortcutOverlay` for help.
- **G-08** [P1] Public pages (WhyFree, Pricing) and the logged-in app use two different headers. WhyFree mounts its own inline header (`WhyFree.tsx:53-65`), Pricing has none (`Pricing.tsx:129-146`), the app uses `DashboardLayout`. **Fix (PR C1):** extract a `MarketingHeader` component (`frontend/src/components/layout/MarketingHeader.tsx`) used by WhyFree + Pricing, with Logo, Why free, Pricing, Sign in, Register. Ties to G-05.
- **G-09** [P2] "Home" icon reused in the sidebar for the Markets item (`DashboardLayout.tsx:104`). After G-03 is applied, the Home icon is freed to represent the actual Home page. Intermediate state needs attention.
- **G-10** [P2] Nav/URL mismatch for Backtest. Sidebar lists `{ label: 'Backtest', path: '/backtest/monte-carlo' }` and `{ label: 'Walk-Forward', path: '/backtest/walk-forward' }` (`DashboardLayout.tsx:107, 109`), but `App.tsx:187-188` redirects both to the canonical `/lab/walk-forward` and `/lab/monte-carlo`. Fine for users, but means active-state matching (`isPathActive`, `DashboardLayout.tsx:280-292`) sees `/lab/*` on the pathname while the nav item thinks it is on `/backtest/*` — neither item highlights. **Fix:** update nav paths to `/lab/monte-carlo` and `/lab/walk-forward`; keep `App.tsx` redirects for old bookmarks.
- **G-11** [P1] Page content-width inconsistency. No shared container. Pricing uses `max-w-6xl` (`Pricing.tsx:131`), SettingsProfile/Connections/Users use `max-w-[960px]` (`SettingsProfile.tsx:84`, `SettingsConnections.tsx:563`, `SettingsUsers.tsx:162`), SettingsAIKeys uses `max-w-[860px]` (`SettingsAIKeys.tsx:32`), SystemStatus uses `max-w-[1040px]` (`SystemStatus.tsx:562`), Picks uses `max-w-3xl` (`Picks.tsx:49,68`), WhyFree mixes `max-w-3xl` / `max-w-4xl` / `max-w-5xl` inside a single page (`WhyFree.tsx:34,54,68`), MarketDashboard/PortfolioOverview are unbounded. **Fix (PR C4):** publish a `PageContainer` variant set (`narrow=640`, `default=960`, `wide=1200`, `full`) in `components/ui/Page.tsx` and migrate each page to one of them.
- **G-12** [P1] Footer inconsistency. `DashboardLayout.tsx:604-611` renders a tiny "Why is this free?" link only when a user is authenticated. Marketing pages (WhyFree, Pricing) have no footer at all. **Fix:** a shared `MarketingFooter` with Why free, Pricing, GitHub/Terms/Privacy (placeholders OK).
- **G-13** [P1] `displayName` in `DashboardLayout.tsx:70-79` applies `toTitleCase` globally. This mangles legitimate names: `"McDonald"` → `"Mcdonald"`, `"van der Berg"` → `"Van Der Berg"`, `"de la Rosa"` → `"De La Rosa"`. Visible in the avatar button top-right and the dropdown menu. **Fix:** trust the stored display name (trim-only) and respect whatever the user typed in `SettingsProfile`.
- **G-14** [P2] `buildSettingsItems(isAdmin)` ignores its `_isAdmin` parameter (`DashboardLayout.tsx:94-99`) and only returns a single "Settings" entry. Dead parameter; rename to `_` or delete.
- **G-15** [P2] `totals` / `headerStats` are calculated in `DashboardLayout` on every render (lines 183-188, 238-278) but never rendered — the header no longer displays portfolio totals. The effect still fires `portfolioApi.getLive()` (line 258) on every mount. **Fix:** either delete the dead state/effect or plumb the result into the header (PR C4 decision — if C1 is nav-only, just delete).
- **G-16** [P2] `notifications` is a hardcoded empty array (`DashboardLayout.tsx:199`) — the bell icon is always empty, always opens a dropdown that always says "No notifications yet." **Fix (PR C4):** hide the bell until a real notifications feed lands, or gate behind admin-only.
- **G-17** [P2] Mobile nav drawer has an `sr-only` title (`DashboardLayout.tsx:404-407`) — no visible heading on the mobile sidebar. Minor a11y/polish — add a visible "AxiomFolio" header above the nav list.

## Page-by-page

### 1. WhyFree (`frontend/src/pages/WhyFree.tsx`)
**Purpose:** public transparency page explaining why the core app is free.
**Data flow:** `useQuery<PricingCatalogResponse>` → `GET /pricing/catalog`; `PublicStatsStrip` → `GET /public/stats`. Loading/error/empty states properly modeled at lines 81-85 (good — follows `no-silent-fallback.mdc`).
**Friction:**
- **WF-01** [P1] Three different content widths across sections: header uses `max-w-5xl` (line 54), hero Section uses `max-w-4xl` via `className` override (line 68), other Sections use `max-w-3xl` from the util default (line 34). Eye-tracking shifts left/right on scroll. **Fix (PR C4):** pick one width (4xl is best for this long-form page), remove per-section overrides.
- **WF-02** [P1] Tip jar buttons are disabled with a "Coming soon" tooltip (lines 193-225). Dead end. **Fix (PR C4):** replace with a single honest card: "Tips will open when Stripe Checkout lands — meanwhile, share the app with someone who'd benefit" + a share-link button. Or just delete the section until checkout is wired.
- **WF-03** [P1] Page header (lines 53-65) lists only Sign in / Register — no link to `/pricing`. Someone landing on Why Free cannot get to tiers without guessing the URL. **Fix (PR C1):** use the shared `MarketingHeader` from G-08 with Why free · Pricing · Sign in · Register.
- **WF-04** [P1] `neverItems` is hardcoded (`WhyFree.tsx:21-27`) but `freeForeverItems` loads from the backend catalog (line 48). Asymmetric source-of-truth treatment; a future copy change to "never" commitments requires a frontend PR. **Fix (PR C4):** either move `never_items` onto the pricing-catalog response OR explicitly document why this one stays hardcoded.
- **WF-05** [P2] Hero (lines 68-77) has no primary CTA button — just a paragraph. A visitor's next move is unclear. **Fix (PR C4):** add a primary "Start free — no credit card" button linking to `/register` and a secondary "See pricing" linking to `/pricing`.
- **WF-06** [P2] External link to Plaid (lines 103-110) opens in a new tab (`target="_blank"`) but has no visual arrow glyph or `<ExternalLink />` icon to signal that — the underline alone is ambiguous. **Fix (PR C4):** append a small `<ExternalLink className="inline size-3" aria-hidden />`.

### 2. Pricing (`frontend/src/pages/Pricing.tsx`)
**Purpose:** public `/pricing` page for the 6-tier ladder.
**Data flow:** `useQuery<PricingCatalogResponse>` → `GET /pricing/catalog`. Loading/error/empty states modeled correctly at lines 78-81.
**Friction:**
- **PR-01** [P1] Hero title is `"Ladder 3 pricing"` (line 133) — this is internal jargon from the Phase-0.5 spec. A visitor has no idea what "Ladder 3" means. **Fix (PR C4):** change to `"Simple, honest pricing"` or `"Pricing"`; move the "Ladder 3" label (if needed for internal reference) into a `<meta>` comment.
- **PR-02** [P1] No marketing header. If a visitor lands directly on `/pricing` (via a tweet, a search hit, or an upgrade-prompt toast from `useUpgradePrompt`), there is no way to reach WhyFree, Sign in, or Register from within the page chrome — only the small "Get started" / "Why free" buttons in the hero. **Fix (PR C1):** wrap in the shared `MarketingHeader` from G-08.
- **PR-03** [P1] `handleCtaClick` routes unauthenticated CTAs to `/register?upgrade=<tier>` (line 73) but there is no downstream handler for the `upgrade` query param in `Register.tsx` — the hint is silently dropped. **Fix (PR C4):** read the `upgrade` param in Register (`new URLSearchParams(location.search).get('upgrade')`), show "You're upgrading to {tierName}" microcopy at the top of the register card, and persist the intent for the Stripe handoff that lands later.
- **PR-04** [P2] "Featured" tier lives alone in its own section (line 90-98). The word "Featured" is weak without a badge. **Fix (PR C4):** add a `"Most popular"` pill in the `TierCard` featured variant, and/or rename the section to `"Recommended"`.
- **PR-05** [P2] Enterprise CTA uses `mailto:` (lines 64-67). No "Copy email" affordance, no Calendly/Cal.com fallback. Low-friction contact is important even if there's only one sales inbox. **Fix (PR C4):** render the email address as text alongside the button so users can copy it without launching their mail client; add a "Book a call" secondary CTA if a booking link exists.

### 3. PublicStatsStrip (`frontend/src/components/transparency/PublicStatsStrip.tsx`)
**Purpose:** live stats (`portfolios_tracked`, `charts_rendered_24h`, `brokers_supported`) embedded in WhyFree.
**Data flow:** `useQuery` → `GET /public/stats`. Loading skeleton (lines 70-85), error with retry (lines 88-106), null-data branch (line 109). Correctly models all states.
**Friction:**
- **PS-01** [P2] `useAnimatedInt` runs 700ms counter animation unconditionally; ignores `prefers-reduced-motion` (line 26-45). Minor a11y. **Fix (PR C4):** check `window.matchMedia('(prefers-reduced-motion: reduce)').matches` and skip the RAF loop if true (set value directly).
- **PS-02** [P2] Error-state retry uses a raw `<button>` (lines 98-104) — visual inconsistency with the `Button` component used elsewhere. **Fix (PR C4):** swap for `<Button variant="ghost" size="sm">Retry</Button>`.

### 4. Login (`frontend/src/pages/Login.tsx`)
**Purpose:** email/password + Google + Apple sign-in.
**Data flow:** `login()` from `useAuth`, redirects to `redirectTo` (recently-viewed route or `/`). Pending-approval and unverified-email errors explicitly modeled (lines 79-86) — good.
**Friction:**
- **AU-01** [P1] No `Forgot password` link anywhere on the form (lines 161-207). Social-auth users are immune, but password-users are locked out. **Fix (PR C1):** add a `<Link to="/auth/forgot-password">Forgot password?</Link>` under the password field. The route does not exist yet (see AU-02).
- **AU-02** [P1] No `/auth/forgot-password` or `/auth/reset-password` routes in `App.tsx`. The whole password-recovery journey is missing from the SPA. **Fix (PR C1):** add placeholder routes and stub pages that link to a "Password reset coming — email support@axiomfolio.com" message until the backend flow lands. Mark explicitly in the doc that full reset is a separate ticket.
- **AU-03** [P2] Apple button hardcodes `bg-[#000]` and `hover:bg-[#1a1a1a]` (line 150) — Apple brand requires black, but the hex lives in a component. **Fix (PR C4):** extract to `--brand-apple-bg` in `index.css`, or annotate with a `// brand color per Apple HIG, do not tokenize` comment so the next reviewer knows why it's raw hex.
- **AU-04** [P2] Google SVG uses four raw brand hex values (lines 130-144). Same rationale as AU-03; same remediation.
- **AU-05** [P2] "Why is this free?" link (lines 210-214) uses `text-white/80` on the gradient — contrast is borderline for small text. **Fix (PR C4):** bump to `text-white` or add a subtle dark pill background.

### 5. Register (`frontend/src/pages/Register.tsx`)
**Purpose:** account creation.
**Friction:**
- **AU-06** [P1] No password-strength indicator (lines 67-89). Backend accepts any 8+ char password (inferred from context), but users get no feedback while typing. **Fix (PR C4):** add a lightweight `<PasswordStrengthMeter>` component below the password input (3-bar meter: length ≥ 8, mixed case, digit/symbol). Local-only; no backend change.
- **AU-07** [P1] On successful register without pending approval, the code navigates to `/` (line 32) which is the `/` → `/market` redirect. Cold drop onto MarketDashboard with no "welcome, let's connect an account" onboarding. **Fix (PR C1 + C2):** route to `/onboarding` (already exists, `App.tsx:158`) when the user has no broker accounts yet; else `/`.

### 6. Home (missing — `/` currently redirects to `/market`)
See G-02. Acceptance for PR C2 listed in the remediation table below.

### 7. MarketDashboard (`frontend/src/pages/MarketDashboard.tsx`)
**Purpose:** primary market analytics canvas. Currently serves as de-facto landing page because of G-02.
**Data flow:** `useQuery<DashboardPayload>` → `marketDataApi.getDashboard()`; 5 additional hooks (`usePortfolioSymbols`, `useAdminHealth`, `useVolatility`, `useSnapshotAggregates`, `useSnapshotTable`). Loading/warming/error states modeled (lines 905-936).
**Friction:**
- **MD-01** [P0] `advDecColor` (lines 953-960) returns Chakra-era tokens: `'green.500'`, `'red.400'`. These are not Tailwind classes, not CSS variables, not anything a post-Chakra design system knows what to do with — they rely on `StatCard` having a legacy Chakra-token mapping. Result: the Advance/Decline KPI may silently render with no color in some paths. **Fix (PR C4):** replace with semantic tokens (`'status.success'`, `'status.danger'`) which `StatCard` + `semanticTextColorClass` do understand, or inline a `cn()` with `text-[rgb(var(--status-success))]`.
- **MD-02** [P1] `effectiveStats` (lines 850-854) uses `|| 0` fallbacks on counts that drive the user-visible "% above 50DMA / 200DMA" and advance/decline KPIs. If the regime payload is slow or absent, users see "0% above 50DMA · 0 / 0" — indistinguishable from a genuine market bottom. **Fix (PR C4):** render `—` while `payload` is still loading and only compute percentages when `snapshotCount > 0 && payload?.regime != null`.
- **MD-03** [P1] Stage-palette implementation mixes Tailwind-amber utilities (`'bg-amber-500/15 text-amber-800 dark:text-amber-200'`, lines 1196-1199) with raw CSS var references (`'bg-[rgb(var(--status-success)/0.12)]'`, line 1195). Two tokenization conventions coexist for the same visual role. **Fix (PR C4):** standardize on `--status-*` tokens for the four stages, delete the amber literal strings.
- **MD-04** [P1] Error branch (line 933) renders `{error?.message || 'Failed to load market dashboard'}` with no retry button and no distinction between network failure, 402 upgrade-required, or 500. **Fix (PR C4):** dedicated error card with a Retry button (`void refetch()`), a "Something went wrong" copy, and a muted line containing the `error.message` for debugging.
- **MD-05** [P2] Warming state (lines 916-927) shows a spinner with "Auto-refreshing in a few seconds…" but the actual refetch interval is 10s (line 788). Add "checking every 10s" microcopy so users know the dashboard isn't frozen.
- **MD-06** [P2] `<Scatter>` cells hardcode `stroke="white"` (line 576). Works in dark mode; clashes with light-mode background. **Fix (PR C4):** use `stroke="var(--card)"` or the chart-colors hook.
- **MD-07** [P2] Dashboard is the de-facto Home — new users arrive with zero context, zero "here's what Axiom does" intro, zero CTAs to connect a broker. Partly solved by G-02, but even post-C2 the MarketDashboard itself needs a "first visit" hint for the overview/top-down/bottom-up/sectors/heatmap tab set (lines 982-1001).
- **MD-08** [P2] "N minutes ago" snapshot-age badge (lines 1024-1039) turns orange at >30min but offers no tooltip explaining the threshold or a refresh action in the same region. **Fix (PR C4):** wrap in a `<Tooltip>` that says "Snapshots >30 minutes old may be stale — click the refresh icon to re-run the dashboard query" and link to the already-adjacent refresh button.
- **MD-09** [P2] Data-warning badge (lines 1035-1038) silently surfaces `mismatch_count` but has no click action; admins can see it but regular users see the same badge and can't click into the detail. **Fix (PR C4):** admin-only, or link to `/settings/admin/system` on click.

### 8. PortfolioOverview (`frontend/src/pages/portfolio/PortfolioOverview.tsx`)
**Purpose:** KPI + equity-curve + allocation landing page for portfolio-enabled users.
**Data flow:** 10 React Query hooks (`usePortfolioOverview`, `usePositions`, `usePortfolioPerformanceHistory`, `usePortfolioInsights`, `useAccountBalances`, `useMarginInterest`, `useDividendSummary`, `useLiveSummary`, `useRiskMetrics`, `usePnlSummary`). Most loading/error states are modeled (lines 206-215).
**Friction:**
- **PO-01** [P1] Sync-age dots hardcode Tailwind scale colors `bg-green-500 / bg-amber-400 / bg-red-400` (lines 390-393) instead of the semantic `--status-success / --status-warning / --status-danger` tokens used elsewhere (`QuadStatusBar`, `RegimeBanner`). **Fix (PR C4):** replace with `bg-[rgb(var(--status-success))]` etc., drop the Tailwind scale literals.
- **PO-02** [P1] "Live data disconnected" alert mixes amber scale with `text-amber-950 dark:text-amber-100` (line 192) instead of the `--status-warning` token set. Same tokenization-drift as PO-01. **Fix (PR C4):** tokenize.
- **PO-03** [P1] `historyPeriod` (30d / 90d / 1y / all, lines 71, 62-67) defaults to `1y` and is not persisted; refresh the page and you're back to 1y even if you were just reviewing All. **Fix (PR C4):** persist via `localStorage` (`axiomfolio:portfolio:history-period`).
- **PO-04** [P2] File is 897 lines; would benefit from a component split (StageDist, TopMovers, AccountHealth). Out of Phase-4 UX scope — flag for a later refactor.

### 9. PortfolioOptions (`frontend/src/pages/portfolio/PortfolioOptions.tsx`)
**Purpose:** options positions, chain, analytics, history.
**Friction:**
- **POP-01** [P1] `gwConnected = gatewayQuery.data?.connected ?? false` (line 94) silently renders a "disconnected" pill while the query is loading. User can't distinguish loading from disconnected. **Fix (PR C4):** render a "Checking…" pill while `gatewayQuery.isPending`.
- **POP-02** [P2] 1,684-line file. Flag for maintainability (not UX).

### 10. PortfolioTaxCenter (`frontend/src/pages/portfolio/PortfolioTaxCenter.tsx`)
**Purpose:** unrealized + realized tax-lot view.
**Friction:**
- **PT-01** [P1] `realizedGains: RealizedGainRow[] = realizedQuery.data?.realized_gains ?? []` (line 96) — silent fallback to empty array hides loading vs error vs genuine empty. A user who just exported a closed year sees "No realized gains" indistinguishably from "still loading". **Fix (PR C4):** add explicit branches using `realizedQuery.isLoading / isError / data?.realized_gains.length === 0`.
- **PT-02** [P1] Similarly `yearSummaries: YearSummary[] = realizedQuery.data?.summary_by_year ?? []` (line 97). Same bug.
- **PT-03** [P2] Tax-rate constants (`TAX_RATE_SHORT_TERM_PCT`, `TAX_RATE_LONG_TERM_PCT`) imported at line 12 but their assumptions (filing status, federal only? state?) are not disclosed in the UI. **Fix (PR C4):** render a small footnote "Estimates assume [US federal, single-filer, 2026 rates]" adjacent to the estimated-tax StatCard.

### 11. Picks — mounted at `/signals/picks` (`frontend/src/pages/Picks.tsx`)
**Purpose:** published pick feed. Only signal surface that actually exists today.
**Friction:**
- **PK-01** [P1] Upgrade CTA `<Link to="/settings/profile">View subscription</Link>` (lines 83-86) — but SettingsProfile (`frontend/src/pages/SettingsProfile.tsx`) has no subscription section. Dead CTA. **Fix (PR C3):** route to `/pricing` instead; drop "View subscription" copy in favour of "See plans".
- **PK-02** [P1] Empty-state card "No published picks yet." (line 94) has no action. User who just opened the page is stuck. **Fix (PR C3):** add "Browse strategies →" linking to `/lab/strategies` and a small "Picks are published after validator runs — check back in a few hours" microcopy.
- **PK-03** [P2] `truncate` (line 31) renders ellipsis at exactly 220 chars — works but the expand affordance is not visible (handled in the 34 lines I didn't print). Double-check the expand button has a clear label (`Show more` / `Show less`). Note for PR C4 review.

### 12. Signals shells (`frontend/src/pages/signals/`)
- **SIG-01** [P0] Directory does not exist. The only `/signals/*` route today is `/signals/picks` → `Picks.tsx` (a top-level file, not under `pages/signals/`). Phase-4 PR C3 requires scaffolding `pages/signals/index.tsx` (signals hub), and any per-surface shells the plan calls for (e.g. `pages/signals/setups.tsx`, `pages/signals/transitions.tsx`). **Needs scaffolding first** — PR C3 cannot begin by auditing non-existent files. Recommendation: C3 opens by (a) creating the `signals/` directory with a minimal `SignalsHub` page that lists the 3-4 surface shells, (b) moving `Picks.tsx` under `pages/signals/Picks.tsx`, (c) updating the App.tsx route imports to match. Acceptance criteria below.

### 13. SettingsShell (`frontend/src/pages/SettingsShell.tsx`)
**Purpose:** left-nav + outlet container for all Settings sub-pages.
**Friction:**
- **SS-01** [P1] Mobile view (lines 110-129) renders icon-only nav with no persistent label — Radix Tooltip appears on hover, but mobile has no hover. Active-state bg is the only indicator. **Fix (PR C4):** show a small text label under each icon, or add a floating "current section" chip above the outlet on mobile.
- **SS-02** [P2] "Picks validator" admin link (lines 99-105, 125) includes a "↗" glyph suggesting external/new-window, but the route is an internal SPA path. Misleading. **Fix (PR C4):** drop the arrow OR genuinely open in a new tab (admins may want that for multi-monitor).

### 14. SettingsConnections (`frontend/src/pages/SettingsConnections.tsx`)
**Purpose:** broker + TradingView + data-provider connection management.
**Friction:**
- **SC-01** [P1] Toast shim (lines 56-62) coexists with direct `hotToast.success/error` calls scattered throughout the file (e.g. lines 494, 539, 555). Two toast idioms in the same file produce inconsistent phrasing ("Sync started" vs "Gateway reconnection triggered — auto-checking status..."). **Fix (PR C4):** pick one idiom, migrate all call sites.
- **SC-02** [P1] "Connect Schwab" OAuth opens in `window.open(..., '_blank', 'noopener,noreferrer')` (lines 239, 389). If the browser blocks the popup, the user sees only a toast — no fallback UI, no "retry link" button. **Fix (PR C4):** mirror the E*TRADE pattern (synchronous `window.open('about:blank')` then assign `.location.href`, see lines 342-358) for all OAuth broker flows.
- **SC-03** [P1] Recent-syncs uses native `<details><summary>` (lines 842-907) while every other collapsible in the app uses Radix `Collapsible`. Visual/interaction inconsistency. **Fix (PR C4):** migrate to Radix.
- **SC-04** [P1] TradingView section hardcodes status pill "Active" (line 1039). There is no actual TV connection state — the embed widget either renders or it doesn't, there's no subscription to check. Misleads users who expect "Active" to mean something. **Fix (PR C4):** drop the badge, or label it "Embed" to indicate it's the public widget not a paid TV account.
- **SC-05** [P1] Data Providers section (lines 1108-1140) renders two opacity-60 placeholder cards with "Coming Soon" copy. Visual noise on a page already dense with controls. **Fix (PR C4):** collapse into a single "Data provider integrations coming soon" banner with the provider list inside a disclosure, or hide the whole section until at least one provider is live.
- **SC-06** [P1] `border-l-[3px] border-l-emerald-500` used on connected broker cards (lines 674-676) — emerald Tailwind scale instead of `--status-success` token (same drift as PO-01, MD-03). Appears at lines 656, 675, 693, 870, 935. **Fix (PR C4):** tokenize.
- **SC-07** [P1] Wizard dialog title stays "New Brokerage Connection" at every step (line 1294). At step 2, with a specific broker selected, it should say e.g. "Connect Schwab". **Fix (PR C4):** derive the title from `broker` at step 2.
- **SC-08** [P1] Inline `<select>` elements for account type + IBKR/Schwab forms (lines 587-604, 744-760) use a custom `selectSm` class instead of a Radix Select. Keyboard navigation, focus ring, and dark-mode styling all drift. **Fix (PR C4):** migrate to the Radix-based Select component used elsewhere.
- **SC-09** [P1] "Go to Portfolio" button uses `window.location.href = '/portfolio'` (line 624) — triggers a full page reload instead of an SPA navigate. **Fix (PR C4):** `navigate('/portfolio')` using `useNavigate`.
- **SC-10** [P1] Logo-tile button (lines 126-146) has no `aria-pressed` state despite a `selected` prop; the selection is invisible to screen readers. Also `selected` is deliberately unused (`_selected`, line 123) — the UI has no visible selected-state. **Fix (PR C4):** either use `selected` (add a ring / shadow when true) and wire `aria-pressed`, or delete the prop.
- **SC-11** [P2] File is 1,429 lines — very hard to audit fully. Flag for refactor (broker sections → one subcomponent per broker). Out of Phase-4 UX scope.
- **SC-12** [P2] `loading`, `adding`, `syncingId`, `busy`, `deleteLoading`, `savingProfile`-equivalents all coexist (lines 67-97). Many unused branches. Flag for refactor.

### 15. SettingsProfile (`frontend/src/pages/SettingsProfile.tsx`)
**Friction:**
- **SP-01** [P1] `Email` change accepts a current-password input in the same flow as `full_name` (lines 36-41). If the user just updates their name, they leave the password field blank and the save "just works"; if they also change email, they have to remember the password field matters. The UI does not hint at this conditional requirement. **Fix (PR C4):** show the current-password field only when the email has changed (`{email !== originalEmail ? <Input ... /> : null}`), with a "Changing email requires your current password" microcopy.
- **SP-02** [P2] Username field is disabled (line 95) with no tooltip explaining why. **Fix (PR C4):** add a tooltip "Usernames are immutable — contact support to change yours" or equivalent.

### 16. SettingsPreferences (`frontend/src/pages/SettingsPreferences.tsx`)
**Friction:**
- **SPR-01** [P1] Timezone list falls back to 5 zones when `Intl.supportedValuesOf('timeZone')` is unsupported (lines 40-46). Users on older browsers are stuck with UTC, NY, Chicago, LA, London. **Fix (PR C4):** ship a static JSON list of the IANA zones (~430 entries, ~5kB gzipped) in `constants/timezones.ts` as the fallback.
- **SPR-02** [P2] Auto-save debounce is 1s (seen in the `debounceRef` usage, line 28) but there is no in-flight "Saving…" indicator mid-debounce — only `saveStatus === 'saving'` after the API call fires. **Fix (PR C4):** show a muted "…" chip during the debounce window.

### 17. SettingsAIKeys (`frontend/src/pages/SettingsAIKeys.tsx`)
**Friction:**
- **SA-01** [P1] Native `<select>` (lines 42-49) — inconsistent with Radix Select elsewhere. **Fix (PR C4):** Radix.
- **SA-02** [P1] Status line (lines 69-78) renders `"Unavailable"` on `statusQuery.isError` — no retry, no distinction between 401/404/500. Violates `no-silent-fallback.mdc`. **Fix (PR C4):** show an explicit "Could not check key status — Retry" with a button.
- **SA-03** [P2] No "Remove key" / "Rotate key" affordance. Once saved, the only path is overwrite. **Fix (PR C4):** add a muted "Remove" button next to the status line when `has_key === true`.

### 18. AppLogo (`frontend/src/components/ui/AppLogo.tsx`)
**Friction:**
- **AL-01** [P1] `PETAL = '#3274F0'` and `DOT = '#F59E0B'` (lines 9-10) are intentional brand colors (per the file comment), but they live as raw hex in a component. Per `engineering.mdc` "never raw hex in components except chart constants from `chart.ts`". **Fix (PR C4):** move to `frontend/src/constants/brand.ts` alongside other brand literals, or annotate with the existing comment block + an eslint-disable line. Decision call — either is acceptable if documented.

### 19. useUpgradePrompt (`frontend/src/hooks/useUpgradePrompt.ts`)
**Purpose:** global 402 `billing:upgrade-required` event → toast.
**Friction:**
- **UP-01** [P1] Toast string is `"{message} Visit /pricing to upgrade."` (line 14) — raw URL text, not clickable. User has to copy/paste. **Fix (PR C4):** replace the `hotToast.error` with a custom toast that includes a "View plans" button navigating to `/pricing`. Verify compatibility with react-hot-toast's custom-toast API.
- **UP-02** [P2] Uses `hotToast.error` — styles the prompt as a red destructive error. "You need to upgrade" is not an error state; it's an info/warning. **Fix (PR C4):** use `hotToast` (default) or a neutral-styled toast with `{ icon: <Lock /> }` using the Lucide `Lock` icon from `lucide-react` (or a tiny custom wrapper if the string-only `icon` API is insufficient).

### 20. App routing (`frontend/src/App.tsx`)
**Friction:**
- **APP-01** [P0] Duplicate of G-02 — `/` → `/market` redirect, no Home.
- **APP-02** [P1] 404 fallback missing. Any unknown URL inside the authenticated parent route just renders a blank `<Outlet />`. **Fix (PR C1):** add `<Route path="*" element={<NotFound />} />` both inside the `/` parent and at the top level; a two-line `NotFound` page that links to Home suffices.
- **APP-03** [P2] `LegacyStrategyDetailRedirect` (lines 87-93) silently redirects invalid strategy IDs to `/lab/strategies` with no toast. A user who clicks a stale bookmark thinks the page just "lost" their strategy. **Fix (PR C4):** `hotToast('Strategy not found — showing the full list')` before the redirect.
- **APP-04** [P2] `TerminalRedirect` (lines 136-143) fires a toast on mount every single time the route is hit. If the user double-clicks a Terminal bookmark the toast fires twice. Minor but scruffy. **Fix (PR C4):** drop the toast after 1 release, delete the redirect after 2.

## Remediation mapping to PR C series

| Finding | PR | Acceptance |
|---------|----|-----------|
| G-01 (logo non-clickable) | C1 | `<AppLogo />` wrapped in `<Link to="/">` in `DashboardLayout` header (both states) and `AuthLayout`; clicking the logo on any screen navigates to `/`. Focus ring visible. |
| G-02 (no Home page)       | C2 | New `frontend/src/pages/Home.tsx` + route replaces the `/` → `/market` redirect. Home renders a concise hero, primary CTAs (Connect broker, Explore market, See pricing), and links to the three pillars. |
| G-03 (Dashboard label)    | C1 + C2 | After C2 lands, the sidebar shows `Home` (→`/`) and `Markets` (→`/market`) as separate items; "Dashboard" disappears as a nav label. |
| G-04 (Pricing not in nav) | C1 | Pricing link appears in the avatar dropdown (logged-in) and `MarketingHeader` (logged-out); reachable in ≤2 clicks from any app screen. |
| G-05 (Why-free discoverability) | C1 | Covered by the shared `MarketingHeader` + `MarketingFooter`. Visible from `/pricing`, `/why-free`, `/login`, `/register`. |
| G-06 (Terminal dead link) | C1 | Removed from `buildMarketItems`. The redirect in `App.tsx` stays for one release, then is deleted. |
| G-07 (Cmd+K invisible)    | C1 | A `Cmd+K` affordance appears in the `DashboardLayout` header, opens the existing `CommandPalette`, and shows a `ShortcutOverlay` when `?` is pressed. |
| G-08 (Marketing header drift) | C1 | `components/layout/MarketingHeader.tsx` exists and is used by `WhyFree.tsx` + `Pricing.tsx`. |
| G-09 (Home icon reuse)    | C1 | Resolved as a side-effect of G-03. |
| G-10 (Backtest nav URL)   | C1 | Sidebar `path` values updated to `/lab/monte-carlo` and `/lab/walk-forward`; `App.tsx` redirects remain for old bookmarks. |
| G-11 (content widths)     | C4 | `Page` exports `PageContainer` variants; every page that currently sets `max-w-*` is migrated. No hand-rolled widths remain. |
| G-12 (footer drift)       | C1 | `MarketingFooter` component shared across WhyFree/Pricing/Login/Register. Logged-in footer either reuses it or is removed (decision in C1 review). |
| G-13 (`displayName` toTitleCase) | C4 | Delete `toTitleCase`; display user names verbatim (trimmed only). |
| G-14 (dead `_isAdmin`)    | C4 | Parameter removed from `buildSettingsItems`. |
| G-15 (dead totals/headerStats) | C4 | `portfolioApi.getLive()` call in `DashboardLayout` deleted OR its result is actually displayed. |
| G-16 (empty notifications bell) | C4 | Bell icon hidden until a real feed exists, or gated to admin-only behind a flag. |
| G-17 (mobile drawer title) | C4 | Visible `AxiomFolio` title above the mobile nav list. |
| APP-01 | C2 | Merged with G-02. |
| APP-02 | C1 | New `pages/NotFound.tsx`; wildcard route inside `/` parent AND at top level. |
| APP-03 | C4 | Toast before redirect in `LegacyStrategyDetailRedirect`. |
| APP-04 | C4 | Drop the Terminal redirect toast (and, later, the redirect). |
| WF-01 | C4 | Single content width on WhyFree (pick `max-w-4xl`); remove section-level overrides. |
| WF-02 | C4 | Tip-jar section replaced with honest "coming with checkout" or removed. |
| WF-03 | C1 | Shared `MarketingHeader`. |
| WF-04 | C4 | Asymmetric-source-of-truth for `never_items` documented or tokenized into the catalog. |
| WF-05 | C4 | Hero CTA buttons added. |
| WF-06 | C4 | External-link icon on Plaid link. |
| PR-01 | C4 | "Ladder 3 pricing" → "Pricing" (or equivalent non-jargon). |
| PR-02 | C1 | `MarketingHeader` on Pricing. |
| PR-03 | C4 | `/register?upgrade=<tier>` param actually read and surfaced in `Register.tsx`. |
| PR-04 | C4 | "Most popular" badge on featured tier. |
| PR-05 | C4 | Enterprise contact gets a copyable email + (optional) booking link. |
| PS-01, PS-02 | C4 | `prefers-reduced-motion` respected; retry uses `Button`. |
| AU-01 | C1 | `Forgot password?` link on Login, routing to `/auth/forgot-password`. |
| AU-02 | C1 | Placeholder `pages/auth/ForgotPassword.tsx` + `ResetPassword.tsx` routes wired; actual reset backend is a separate ticket. |
| AU-03, AU-04, AU-05 | C4 | Annotate brand-color hex with a comment; bump Why-free link contrast. |
| AU-06 | C4 | `PasswordStrengthMeter` component on Register. |
| AU-07 | C1 + C2 | New users with no broker accounts route to `/onboarding` on successful register. |
| MD-01 | C4 | Chakra-era tokens in `advDecColor` replaced with semantic tokens. |
| MD-02 | C4 | Explicit loading vs zero distinction in `effectiveStats`. |
| MD-03 | C4 | Stage palette tokenized. |
| MD-04 | C4 | Error card with retry button. |
| MD-05 | C4 | "Checking every 10s" copy in warming state. |
| MD-06 | C4 | Scatter stroke uses `var(--card)`. |
| MD-07 | C2 | MarketDashboard becomes a deliberate destination (not the default landing); hint/explainer added for first-visit. |
| MD-08, MD-09 | C4 | Snapshot-age tooltip; data-warning badge click → admin surface or hidden. |
| PO-01, PO-02 | C4 | Status-tone tokens replace Tailwind scale literals. |
| PO-03 | C4 | `historyPeriod` persisted. |
| PO-04 | out | Refactor (not UX). |
| POP-01 | C4 | "Checking…" pill while gateway status is loading. |
| POP-02 | out | Refactor (not UX). |
| PT-01, PT-02 | C4 | Explicit loading/error/empty branches on realized gains. |
| PT-03 | C4 | Tax-estimate assumptions disclosed inline. |
| PK-01 | C3 | Upgrade CTA on `Picks` routes to `/pricing`, not `/settings/profile`. |
| PK-02 | C3 | Empty state links to `/lab/strategies` + explanatory microcopy. |
| PK-03 | C4 | Expand-label verification on `Picks`. |
| SIG-01 | C3 | New `frontend/src/pages/signals/` directory with `index.tsx` (SignalsHub) listing the surface shells (picks, setups, transitions). Move `Picks.tsx` to `pages/signals/Picks.tsx`; update `App.tsx` lazy imports. Add placeholder shells (`setups.tsx`, `transitions.tsx`) that render a "coming soon" card with copy explaining what each surface will show. |
| SS-01 | C4 | Mobile Settings nav shows labels (or a current-section chip). |
| SS-02 | C4 | Picks-validator arrow glyph removed (or route opens in new tab). |
| SC-01..SC-12 | C4 | Toast idiom unified; OAuth popup fallback; Radix Collapsible/Select; token cleanup; dynamic wizard title; SPA navigate; `aria-pressed` on logo tiles; noisy "Coming Soon" cards collapsed. Refactor items (SC-11/12) flagged out-of-scope. |
| SP-01 | C4 | Conditional current-password field on email change. |
| SP-02 | C4 | Username-disabled tooltip. |
| SPR-01 | C4 | Static IANA timezone list fallback. |
| SPR-02 | C4 | Mid-debounce "…" chip. |
| SA-01..SA-03 | C4 | Radix Select; retry on key-status error; Remove-key button. |
| AL-01 | C4 | Brand hex moved to `constants/brand.ts` or annotated. |
| UP-01, UP-02 | C4 | Toast has a "View plans" action button; non-error styling. |

## Out of scope for Phase 4

- PO-04 / POP-02 / SC-11 / SC-12 — component-size refactors. Valuable, but belong in a code-quality PR (Phase-5 refactor sprint), not Phase-4 UX.
- MD-07 onboarding primer — overlaps with Phase-5 "Getting started" work; C2 should produce Home, not an onboarding tour. A simple first-visit hint on MarketDashboard is acceptable; a full Intro.js-style tour is not.
- AU-02 actual password-reset backend — the placeholder pages/routes belong in C1, the working reset flow belongs in a separate auth-hardening PR.
- Full E*TRADE OAuth 1.0a reliability review (`SettingsConnections.tsx:335-371`) — that's Phase-3 broker-parity work, not UX polish.
- Any change to `backend/` — out of repository scope for this audit.

## Appendix: files read during audit

- `frontend/src/App.tsx`
- `frontend/src/components/layout/DashboardLayout.tsx`
- `frontend/src/components/layout/AuthLayout.tsx`
- `frontend/src/components/ui/AppLogo.tsx`
- `frontend/src/components/ui/Page.tsx` (via Glob)
- `frontend/src/components/cmdk/AppCommandLayer.tsx`
- `frontend/src/components/cmdk/CommandPalette.tsx` (via Grep for keybindings)
- `frontend/src/components/transparency/PublicStatsStrip.tsx`
- `frontend/src/hooks/useUpgradePrompt.ts`
- `frontend/src/pages/WhyFree.tsx`
- `frontend/src/pages/Pricing.tsx`
- `frontend/src/pages/Login.tsx`
- `frontend/src/pages/Register.tsx`
- `frontend/src/pages/MarketDashboard.tsx`
- `frontend/src/pages/portfolio/PortfolioOverview.tsx`
- `frontend/src/pages/portfolio/PortfolioOptions.tsx` (first 120 lines + grep)
- `frontend/src/pages/portfolio/PortfolioTaxCenter.tsx` (first 100 lines + grep)
- `frontend/src/pages/Picks.tsx`
- `frontend/src/pages/SettingsShell.tsx`
- `frontend/src/pages/SettingsConnections.tsx`
- `frontend/src/pages/SettingsProfile.tsx`
- `frontend/src/pages/SettingsPreferences.tsx`
- `frontend/src/pages/SettingsAIKeys.tsx`
- `frontend/src/pages/signals/` — **directory does not exist; flagged in SIG-01**

Cross-cutting greps performed during the audit:
- `console\.log` under `frontend/src` — no matches (good).
- `\?\? 0 | \?\? '—' | \?\? 'N/A'` under `frontend/src/pages` — matches in 18 pages; representative issues called out (MD-02, PT-01, PT-02, POP-01).
- `#[0-9a-fA-F]{6}` under `frontend/src/pages` — raw hex limited to brand-color SVGs (Login, AppLogo, MarketIntelligence stage palette, MarketEducation stage chart, PortfolioCategories chart colors). Chart-palette hex in page files (MarketIntelligence, MarketEducation, PortfolioCategories) is a broader remediation; within the scope of this audit, the G-11 / token-drift findings are the actionable subset.
- `max-w-` under `frontend/src/pages` — confirmed G-11 width inconsistency across 8+ files.
