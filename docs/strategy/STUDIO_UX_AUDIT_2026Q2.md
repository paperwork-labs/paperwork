---
owner: founders
last_reviewed: 2026-04-29
doc_kind: strategy
domain: paperwork-labs
status: living
summary: "Read-only Studio admin UX audit for WS-76 Wave L PR-A — 56 findings (P0 5, P1 32, P2 19) with file-and-line cites and a remediation table for PR-B, PR-C, and PR-D."
---

# Studio UX Audit — 2026 Q2 (WS-76 Wave L PR-A)

> Read-only audit. Methodology cribbed from `docs/axiomfolio/plans/UX_AUDIT_2026Q2.md`. All findings cite file path + lines so PR-B / PR-C / PR-D can address surgically. Severity rubric: P0 = critical (breaks demo or core flow), P1 = high (founder-noticed friction), P2 = polish.

## Executive summary

- Total findings: 56
- P0: 5 | P1: 32 | P2: 19
- Top 3 most-urgent things a founder demoing to an investor would wince at: (1) Infrastructure **outer** tab state and **inner** `InfraClient` tab state both read/write the same `tab` query param, so clicking Logs inside Services hijacks the whole page to the placeholder Logs tab; (2) open PR and CI widgets on Overview silently render empty when `GITHUB_TOKEN` is unset or GitHub errors, reading as a healthy empty repo; (3) Expenses server fetch collapses HTTP failures into an empty inbox with no banner.
- One-line verdict on Studio's current UX maturity: **~65% there** — information architecture and tab shells are ahead of many internal tools, but data-state honesty, mobile shell ergonomics, and a few routing/URL bugs undermine trust in a live demo.

## Severity rubric

- **P0 — Critical / breaks demo:** Misleading data that looks like success, broken navigation, or a control that throws the user into the wrong surface without recovery. Investor assumes the product is healthy when telemetry is absent or wrong.
- **P1 — High / founder-noticed:** Visible friction, inconsistent patterns vs venture design rules, missing error or loading distinction, dead links, accessibility gaps on primary flows, or copy that contradicts behavior.
- **P2 — Polish:** Microcopy, motion preferences, minor semantic HTML, iconography consistency, or internal consistency that does not block a competent operator.

## Methodology

- Read `docs/axiomfolio/plans/UX_AUDIT_2026Q2.md` in full and mirrored its rubric, finding shape, and remediation table style.
- Read `docs/axiomfolio/DESIGN_SYSTEM.md`, `docs/axiomfolio/FRONTEND_UI.md`, and skimmed `docs/axiomfolio/plans/MASTER_PLAN_2026.md` for cross-product context (Studio-specific gaps only; no AxiomFolio page inventory).
- Read `.cursor/rules/no-silent-fallback.mdc`, `.cursor/rules/ux.mdc`, `.cursor/rules/code-quality-guardian.mdc` and applied them to Studio admin code paths.
- Walked every route under `apps/studio/src/app/admin/` (including legacy redirects and folded routes), the shared admin shell, `command-center.ts`, `pr-pipeline.ts`, tab shell components, and representative tab implementations.
- Skimmed `apis/brain/data/procedural_memory.yaml` for UX-relevant guardrails (a11y/lighthouse labels, worktree isolation — no Studio-specific UX rules surfaced beyond general CI labeling).
- **Excluded:** customer apps (`apps/axiomfolio`, etc.), backend API behavior not reflected in Studio UI, and speculative UI for workstreams not present in files read.

## Global / cross-cutting findings

**P0**

- **F-001** [P0] `InfraClient` reads and writes the `tab` search param (`apps/studio/src/app/admin/infrastructure/infra-client.tsx:173-180`, `:285-317`) while the parent `TabbedPageShell` on `/admin/infrastructure` also keys off the same `tab` param (`apps/studio/src/components/layout/TabbedPageShellNext.tsx:93-105`, `apps/studio/src/app/admin/infrastructure/page.tsx:11-50`). Clicking inner "Logs" replaces `?tab=logs`, which swaps the **page-level** shell to the placeholder `LogsTab` and evicts the services dashboard the investor was looking at. A founder demoing to an investor would wince when the UI "teleports" to a different surface mid-sentence. **Fix (PR-B):** Namespace inner state (`infraView=services|logs`) or hoist logs into the outer shell only and delete the duplicate tablist inside `InfraClient`.

- **F-002** [P0] `getRecentPullRequests` returns `[]` when `GITHUB_TOKEN` is missing (`apps/studio/src/lib/command-center.ts:313-325`) with no typed error surface to the Overview page (`apps/studio/src/app/admin/page.tsx:21-30` passes data straight through). Open PR KPI reads as zero in both failure and success cases. **Fix (PR-B):** Return `{ pulls: [], error?: string }` or throw to layout boundary; Overview must show "GitHub not configured" vs "Zero open PRs".

- **F-003** [P0] `getRecentCIRuns` repeats the same silent-empty pattern when the token is absent (`apps/studio/src/lib/command-center.ts:548-576`). CI strip looks idle during outages or misconfig. **Fix (PR-B):** Same explicit error contract as F-002.

- **F-004** [P0] `fetchExpenses` in the Expenses page returns `{ expenses: [], total: 0 }` on any non-OK response or exception (`apps/studio/src/app/admin/expenses/page.tsx:11-26`). Operators cannot tell "Brain returned 500" from "inbox actually empty". **Fix (PR-B):** Propagate `error` / `degraded` into `ExpensesClient` with retry, matching `no-silent-fallback.mdc`.

- **F-005** [P0] `fetchJson` swallows HTTP and network failures and returns `null` (`apps/studio/src/lib/command-center.ts:215-222`), so every caller must guess whether null means "empty" or "broken". This is the root cause class behind F-002/F-003 and many Brain integrations. **Fix (PR-B):** Typed `Result<T, FetchError>` or throw with structured logging; migrate callers incrementally starting with Overview.

**P1**

- **F-006** [P1] Admin layout fetches expense pending counts and returns `0` on any failure (`apps/studio/src/app/admin/layout.tsx:9-38`), so sidebar badges lie silently. **Fix (PR-B):** Distinguish `unknown` vs `0` and render a muted warning chip instead of suppressing.

- **F-007** [P1] `Suspense` fallback is `null` for all admin children (`apps/studio/src/app/admin/layout.tsx:71-74`), so route transitions show no loading skeleton. **Fix (PR-C):** Shared `AdminRouteFallback` skeleton consistent with the People workspace `PersonasWorkspaceFallback` (`apps/studio/src/app/admin/people/page.tsx:22`).

- **F-008** [P1] Sidebar is a fixed `w-60` column with no mobile drawer pattern (`apps/studio/src/app/admin/admin-layout-client.tsx:129-131`), collapsing content on phones per `ux.mdc` mobile-first guidance. **Fix (PR-C):** Collapsible nav with focus trap and visible menu affordance.

- **F-009** [P1] Vendor footer links reuse `Settings2` for every external link (`apps/studio/src/app/admin/admin-layout-client.tsx:213-223`), a misleading icon for "Hosting" and "AI cost" destinations. **Fix (PR-D):** Use `ExternalLink` or category-appropriate icons.

- **F-010** [P1] `staticPendingCount` on `NavItem` is never populated in `buildNavGroups` (`apps/studio/src/app/admin/admin-layout-client.tsx:29-31`, `:47-88`), while comments promise "PR N wires Expenses" — dead API surface confusing future editors. **Fix (PR-B):** Remove the prop or wire real counts with explicit unknown state.

- **F-011** [P1] Pending badges use raw `red`/`amber` Tailwind scales instead of `--status-*` tokens referenced in `DESIGN_SYSTEM.md` (`apps/studio/src/app/admin/admin-layout-client.tsx:176-181`). **Fix (PR-D):** Align Studio chrome with semantic status variables.

- **F-012** [P1] Personas page wraps content in `@paperwork-labs/ui` `Page` / `PageHeader` (`apps/studio/src/app/admin/brain/personas/personas-tabs-client.tsx:52-60`) while the rest of admin uses bespoke zinc shells — visual system drift in one Brain route. **Fix (PR-C):** Either migrate all admin headers to the shared `PageHeader` pattern or remove the one-off wrapper.

- **F-013** [P1] `getBrainPersonas` returns `[]` when Brain is misconfigured (`apps/studio/src/lib/command-center.ts:245-256`) with no differentiation from "zero personas". **Fix (PR-B):** Structured error for downstream pages.

- **F-014** [P1] `getN8nWorkflows` / `getN8nExecutions` return empty arrays when n8n env is missing (`apps/studio/src/lib/command-center.ts:293-310`) without surfacing configuration gaps on Overview. **Fix (PR-C):** Banner on `OverviewClient` when upstream integrations are absent.

- **F-015** [P1] `pr-pipeline` explicitly surfaces token misconfiguration (`apps/studio/src/lib/pr-pipeline.ts:161-170`, `apps/studio/src/app/admin/pr-pipeline/page.tsx:38-42`) while Overview does not — inconsistent operator experience across two GitHub-backed pages. **Fix (PR-B):** Reuse the explicit error pattern from `pr-pipeline` inside `command-center` consumers.

**P2**

- **F-016** [P2] `UserButton` sits alone in the header row (`apps/studio/src/app/admin/admin-layout-client.tsx:232-235`) with no page title/breadcrumb context — operators lose place when deep-linking. **Fix (PR-D):** Optional `AdminTopBar` slot per route.

- **F-017** [P2] Active nav uses `border-l-2` without reserving width, causing horizontal layout shift on selection (`apps/studio/src/app/admin/admin-layout-client.tsx:160-164`). **Fix (PR-D):** Reserve border width with transparent default.

## Page-by-page findings

### `/admin` (Overview)

**P0** — see F-002, F-003, F-005 (data honesty).

**P1**

- **F-018** [P1] Quick Links still point to `/admin/workflows` (`apps/studio/src/app/admin/overview-client.tsx:654-657`) but that route permanently redirects to Architecture flows (`apps/studio/src/app/admin/workflows/page.tsx:1-6`). Clicking "Workflows" bounces away from the promised destination. **Fix (PR-C):** Update link target to `/admin/architecture?tab=flows` (or restore a workflows hub).

- **F-019** [P1] Refresh control is a raw `<button>` without an explicit focus-visible ring class beyond browser default (`apps/studio/src/app/admin/overview-client.tsx:318-325`). **Fix (PR-D):** Use shared `Button` primitive for consistent `ring-ring` treatment per `DESIGN_SYSTEM.md`.

- **F-020** [P1] `ventureHealth` flips to `yellow` when `workflows.length === 0` (`apps/studio/src/app/admin/overview-client.tsx:213-218`), which can read as "degraded" when n8n is simply not wired — same symptom as partial outages. **Fix (PR-C):** Split "not configured" from "degraded".

- **F-021** [P1] Daily briefing anchor targets generic `https://app.slack.com/client` (`apps/studio/src/app/admin/overview-client.tsx:375-382`) rather than the workspace/channel deep link promised by copy (`#daily-briefing`). **Fix (PR-C):** Configurable Slack deep link or honest neutral CTA.

**P2**

- **F-022** [P2] Activity list inserts raw Unicode glyphs for PR verdict (`apps/studio/src/app/admin/overview-client.tsx:273-279`) without `aria-label`, producing noisy screen reader output. **Fix (PR-D):** Text labels (`Approved`, `Changes requested`).

- **F-023** [P2] Traffic light card animates ping without checking `prefers-reduced-motion` (`apps/studio/src/app/admin/overview-client.tsx:335-339`), conflicting with `ux.mdc` motion rules. **Fix (PR-D):** Gate ping animation.

- **F-024** [P2] `PushSubscribeCard` swallows subscription probe errors silently (`apps/studio/src/components/pwa/PushSubscribeCard.tsx:39-41` `.catch(() => {})`). **Fix (PR-C):** Log + optional inline warning.

### `/admin/architecture`

**P1**

- **F-025** [P1] Tab shell defaults are solid, but the page mixes server `TabbedPageShell` tabs (`apps/studio/src/app/admin/architecture/page.tsx:9-44`) with heavy client-only graph loading (`apps/studio/src/app/admin/architecture/architecture-client.tsx:31-41`) — first paint can feel empty without route-level skeleton beyond tab fallback. **Fix (PR-C):** Ensure `architecture-client` exposes a skeleton state immediately.

**P2**

- **F-026** [P2] Overview tab quick links all jump to GitHub (`apps/studio/src/app/admin/architecture/tabs/overview-tab.tsx:45-75`) while other tabs stay in-app — acceptable but consider mirrored in-app docs per `docs` hub consistency.

### `/admin/infrastructure`

**P0** — see F-001.

**P1**

- **F-027** [P1] `InfraOverviewTab` copy says "click any section to navigate" but cards are static `<div>` elements with no buttons or links (`apps/studio/src/app/admin/infrastructure/tabs/overview-tab.tsx:40-63`). False affordance. **Fix (PR-C):** Wire cards to `router.push` with `?tab=` targets or rewrite copy.

- **F-028** [P1] Duplicate "Logs" concept: outer placeholder tab (`apps/studio/src/app/admin/infrastructure/tabs/logs-tab.tsx:4-18`) vs inner logs inside `InfraClient` (`apps/studio/src/app/admin/infrastructure/infra-client.tsx:319-323`). Investors get two different "Logs" experiences depending on navigation path. **Fix (PR-B):** Single logs entry point after F-001.

- **F-029** [P1] Cost tab is entirely placeholder (`apps/studio/src/app/admin/infrastructure/tabs/cost-tab.tsx:3-17`) without linking to quota panels that already render inside Services. **Fix (PR-C):** Embed quota summary or deep-link anchors into `InfraClient`'s quota section (`apps/studio/src/app/admin/infrastructure/infra-client.tsx:417-437`).

**P2**

- **F-030** [P2] `InfraClient` renders its own H1 "Infrastructure Health" inside a tab that already sits under the page H1 (`apps/studio/src/app/admin/infrastructure/infra-client.tsx:274-283`, `apps/studio/src/app/admin/infrastructure/page.tsx:42-48`) — heading hierarchy skips levels. **Fix (PR-D):** Demote inner title to `h2`.

### `/admin/sprints`

**P1**

- **F-031** [P1] `tone()` maps unknown pill strings to `paused` (`apps/studio/src/app/admin/sprints/sprints-overview-tab.tsx:85-99`), which can mis-label unusual tracker tokens. **Fix (PR-C):** Explicit `unknown` badge + telemetry when slug unseen.

**P2**

- **F-032** [P2] Expandable sprint `<summary>` relies on chevron rotation only (`apps/studio/src/app/admin/sprints/sprints-overview-tab.tsx:561-566`) — add `aria-expanded` via `details` is implicit ok, but chevron lacks text for SR; consider Radix `Collapsible` for parity with design system guidance in Axiom audit (`UX_AUDIT_2026Q2.md` SC-03 pattern).

### `/admin/workstreams`

**P1**

- **F-033** [P1] Header proclaims "Track Z · read-only" (`apps/studio/src/app/admin/workstreams/workstreams-client.tsx:155-157`) while DnD affordance remains visible (`apps/studio/src/app/admin/workstreams/workstreams-client.tsx:217-220`) — mixed message for operators. **Fix (PR-C):** Clarify when reorder ships vs read-only semantics.

- **F-034** [P1] `FilterRail` uses native `<select>` controls (`apps/studio/src/app/admin/workstreams/workstreams-client.tsx:367-393`) vs Radix `Select` recommended in `FRONTEND_UI.md` / Axiom audit patterns. **Fix (PR-D):** Migrate for keyboard + focus consistency.

**P2**

- **F-035** [P2] KPI strip values are numeric only with no semantic coloring for blocked/cancelled (`apps/studio/src/app/admin/workstreams/workstreams-client.tsx:303-335`). **Fix (PR-D):** Use `--status-*` for blocked/cancelled chips similar to Axiom `StatCard` guidance.

### `/admin/products` and `/admin/products/[slug]/plan`

**P1**

- **F-036** [P1] Plan cards truncate titles and paths aggressively without an in-page reader mode (`apps/studio/src/app/admin/products/[slug]/plan/page.tsx:78-85`). Long plan names remain awkward in a founder walkthrough. **Fix (PR-C):** Expand/collapse or side drawer preview.

**P2**

- **F-037** [P2] Static params enumerate known slugs only (`apps/studio/src/app/admin/products/[slug]/plan/page.tsx:9-17`) — adding a product requires code change; acceptable but document in-page. **Fix (PR-D):** Footnote linking to `generate_tracker_index.py`.

### `/admin/brain/personas`

**P1** — see F-012.

**P2**

- **F-038** [P2] People workspace shells can diverge from the default admin content width (`apps/studio/src/app/admin/people/page.tsx` vs `apps/studio/src/app/admin/brain/personas/personas-tabs-client.tsx`). **Fix (PR-D):** Normalize max width tokens.

### `/admin/brain/conversations`

**P1**

- **F-039** [P1] Server fetch returns `null` on any failure (`apps/studio/src/app/admin/brain/conversations/page.tsx:11-25`) and the client immediately clears the list on mount (`apps/studio/src/app/admin/brain/conversations/conversations-client.tsx:199-203`), producing a flash from SSR data to empty when Brain blips. **Fix (PR-B):** Pass explicit `loadError` prop; client should not wipe SSR payload on first effect without success.

- **F-040** [P1] `apiFetch` assumes JSON success for all responses (`apps/studio/src/app/admin/brain/conversations/conversations-client.tsx:130-133`) — non-JSON error bodies throw generic failures. **Fix (PR-C):** Guard `res.headers.get('content-type')`.

**P2**

- **F-041** [P2] Image attachments use generic `alt="attachment"` (`apps/studio/src/app/admin/brain/conversations/conversations-client.tsx:64-72`). **Fix (PR-D):** Filename-based alt text.

### `/admin/brain/self-improvement`

**P1**

- **F-042** [P1] `AuditsTabLazy` passes `NEXT_PUBLIC_BRAIN_API_SECRET` into a client tab (`apps/studio/src/app/admin/brain/self-improvement/self-improvement-client.tsx:84-88`). Even when null, this pattern invites accidental secret exposure if envs are mis-set. **Fix (PR-B):** Proxy audits through a same-origin API route; never accept browser-exposed secrets for privileged reads.

- **F-043** [P1] Copy references "PR P" append (`apps/studio/src/app/admin/brain/self-improvement/self-improvement-client.tsx:133-135`) — internal roadmap jargon on a live admin page. **Fix (PR-C):** User-facing wording ("Audits cadence").

**P2**

- **F-044** [P2] Eight tabs on a laptop width wrap heavily (`apps/studio/src/components/layout/studio-tabbed-page-shell.tsx:129-156`) — consider grouped nav or overflow scroll for dense Brain ops.

### `/admin/expenses`

**P0** — see F-004.

**P1**

- **F-045** [P1] Client fetch ignores failures silently (`apps/studio/src/app/admin/expenses/expenses-client.tsx:69-71` returns early without user-visible error). **Fix (PR-C):** Toast + retry.

- **F-046** [P1] Inbox tab uses client-side filtering for multi-status fetch (`apps/studio/src/app/admin/expenses/expenses-client.tsx:106-110`) — if API returns partial sets, counts drift from server totals. **Fix (PR-B):** Server-side multi-status query or documented guarantee.

**P2**

- **F-047** [P2] Tabs mirror bespoke pattern instead of shared `TabbedPageShell` used elsewhere (`apps/studio/src/app/admin/expenses/expenses-client.tsx:148-164`). **Fix (PR-D):** Converge on `TabbedPageShell` for URL-deep-linkable expense views.

### `/admin/pr-pipeline`

**P1**

- **F-048** [P1] Empty table copy conflates "no PRs" with "missing token" (`apps/studio/src/app/admin/pr-pipeline/page.tsx:67-71`) even though `data.error` exists — row empty state should mention token only when `data.error` absent vs present. **Fix (PR-C):** Split messaging.

**P2**

- **F-049** [P2] Docs link uses external GitHub URL inside `Link` with `target="_blank"` (`apps/studio/src/app/admin/pr-pipeline/page.tsx:194-201`) — Next `Link` is for internal navigation; should be `<a>` for clarity. **Fix (PR-D):** Swap component.

### `/admin/secrets`, `/admin/ops`, `/admin/workflows`, `/admin/automation`, `/admin/analytics`, `/admin/n8n-mirror`, `/admin/brain-learning`

**P1**

- **F-050** [P1] Multiple legacy routes permanently redirect (`apps/studio/src/app/admin/secrets/page.tsx:1-6`, `apps/studio/src/app/admin/ops/page.tsx:1-7`, `apps/studio/src/app/admin/workflows/page.tsx:1-6`, `apps/studio/src/app/admin/automation/page.tsx:1-6`, `apps/studio/src/app/admin/analytics/page.tsx:1-6`, `apps/studio/src/app/admin/n8n-mirror/page.tsx:1-6`, `apps/studio/src/app/admin/brain-learning/page.tsx:1-6`) but sidebar / overview quick links still reference old paths in places (F-018). **Fix (PR-C):** Global link audit + optional in-app "Moved" toast via middleware (optional).

### `/admin/docs`, `/admin/docs/search`, `/admin/docs/[slug]`

**P1**

- **F-051** [P1] Docs hub search form is GET without client-side loading indicator (`apps/studio/src/app/admin/docs/page.tsx:41-58`) — slow disk index reads feel like a hang. **Fix (PR-C):** `useTransition` spinner on submit for future client wrapper (or full client search).

**P2**

- **F-052** [P2] Doc viewer relies on GitHub "View on GitHub" as secondary nav (`apps/studio/src/app/admin/docs/[slug]/page.tsx:41-49`) — fine for agents, but founders may want in-repo anchor hash support. **Fix (PR-D):** Table-of-contents panel.

### `/admin/tasks` and `TrackersRail` (Overview component)

**P2**

- **F-053** [P2] `TrackersRail` shows em dash for expenses when Brain fetch fails (`apps/studio/src/app/admin/_components/trackers-rail.tsx:142-155`) — good honesty, but layout jumps between three vs four stat columns when null; consider fixed min height.

- **F-054** [P2] Expense rollup uses silent `null` catch (`apps/studio/src/app/admin/_components/trackers-rail.tsx:37-38`). **Fix (PR-B):** Align with F-006/F-004 structured errors.

### Tab shells (`TabbedPageShellNext`, `StudioTabbedPageShell`)

**P1**

- **F-055** [P1] `StudioTabbedPageShell` sets `tabIndex={-1}` on inactive triggers (`apps/studio/src/components/layout/studio-tabbed-page-shell.tsx:137-145`) but does not implement roving tabindex / arrow-key navigation required by strict WAI-ARIA tabs authoring practices. **Fix (PR-D):** Add keyboard handlers or document deviation.

**P2**

- **F-056** [P2] `TabPanelErrorBoundary` logs nothing in `componentDidCatch` (`apps/studio/src/components/layout/studio-tabbed-page-shell.tsx:59-61`). **Fix (PR-B):** `console.error` or telemetry hook per `code-quality-guardian.mdc`.

## Remediation mapping

| ID | Severity | Page | Finding (short) | Owner PR | Acceptance |
|----|----------|------|-----------------|----------|--------------|
| F-001 | P0 | /admin/infrastructure | Inner `InfraClient` and outer `TabbedPageShell` fight over `tab` query param | PR-B | Changing inner Services/Logs never swaps outer shell; URL state has single owner |
| F-002 | P0 | /admin (data) | `getRecentPullRequests` returns `[]` without `GITHUB_TOKEN` | PR-B | Overview shows explicit "GitHub token not configured" vs data |
| F-003 | P0 | /admin (data) | `getRecentCIRuns` returns `[]` without token | PR-B | Same explicit state as F-002 |
| F-004 | P0 | /admin/expenses | `fetchExpenses` maps failures to empty inbox | PR-B | Error banner + retry; non-empty only on verified success |
| F-005 | P0 | Global | `fetchJson` null on all failures | PR-B | Typed errors; callers handle degraded mode |
| F-006 | P1 | Global layout | Expense badge fetch swallows errors as zero | PR-B | Unknown badge state + tooltip |
| F-007 | P1 | Global layout | `Suspense` fallback null | PR-C | Shared skeleton component for admin routes |
| F-008 | P1 | Global layout | No responsive nav drawer | PR-C | `<md` collapsible nav meets touch target guidance |
| F-009 | P1 | Global layout | Vendor footer mis-icon | PR-D | Icon matches link semantics |
| F-010 | P1 | Global layout | `staticPendingCount` unused | PR-B | Remove prop or implement counts |
| F-011 | P1 | Global layout | Pending badges use raw Tailwind reds/ambers | PR-D | Tokenized `status-*` classes |
| F-012 | P1 | /admin/brain/personas | `Page`/`PageHeader` only here | PR-C | One shell strategy for all admin pages |
| F-013 | P1 | Global data | `getBrainPersonas` empty vs error | PR-B | Explicit configuration state |
| F-014 | P1 | /admin | n8n empty arrays hide misconfig | PR-C | Inline banner when integrations absent |
| F-015 | P1 | /admin vs /admin/pr-pipeline | GitHub error UX inconsistent | PR-B | Shared `GithubDataBoundary` component |
| F-016 | P2 | Global layout | No breadcrumb/title bar | PR-D | Optional top bar slot |
| F-017 | P2 | Global layout | Nav selection layout shift | PR-D | Reserved border gutter |
| F-018 | P1 | /admin | Quick link `/admin/workflows` is legacy | PR-C | Link targets canonical `/admin/architecture?tab=flows` |
| F-019 | P1 | /admin | Refresh button styling | PR-D | shadcn `Button` + focus ring |
| F-020 | P1 | /admin | Traffic light yellow on zero workflows | PR-C | Distinct "not configured" state |
| F-021 | P1 | /admin | Slack CTA not deep-linked | PR-C | Configurable workspace URL |
| F-022 | P2 | /admin | PR verdict glyphs SR noise | PR-D | Textual labels |
| F-023 | P2 | /admin | Ping animation ignores reduced motion | PR-D | `prefers-reduced-motion` guard |
| F-024 | P2 | /admin | Push card silent catch | PR-C | Surface probe failures |
| F-025 | P1 | /admin/architecture | Heavy client graph LCP | PR-C | Skeleton + progressive reveal |
| F-026 | P2 | /admin/architecture | External-only quick links | PR-D | Optional in-app doc preview |
| F-027 | P1 | /admin/infrastructure | Overview cards not clickable | PR-C | Click targets or copy fix |
| F-028 | P1 | /admin/infrastructure | Duplicate Logs surfaces | PR-B | Single logs IA after F-001 |
| F-029 | P1 | /admin/infrastructure | Cost tab isolated placeholder | PR-C | Cross-link quota data |
| F-030 | P2 | /admin/infrastructure | Double H1 hierarchy | PR-D | Normalize headings |
| F-031 | P1 | /admin/sprints | Unknown pill maps to paused | PR-C | Unknown badge + logging |
| F-032 | P2 | /admin/sprints | `details` pattern vs Radix | PR-D | Align collapsible primitive |
| F-033 | P1 | /admin/workstreams | Read-only vs DnD mismatch | PR-C | Copy + disabled handles when appropriate |
| F-034 | P1 | /admin/workstreams | Native selects in filters | PR-D | Radix `Select` |
| F-035 | P2 | /admin/workstreams | KPI strip lacks semantic color | PR-D | Status tokens for blocked |
| F-036 | P1 | /admin/products/[slug]/plan | Truncated plan metadata | PR-C | Drawer/expand for long titles |
| F-037 | P2 | /admin/products/[slug]/plan | Static slug list | PR-D | On-page note re generator |
| F-038 | P2 | /admin/brain/personas | Fallback width mismatch | PR-D | Align `max-w` tokens |
| F-039 | P1 | /admin/brain/conversations | SSR null + client wipe | PR-B | Preserve SSR until success |
| F-040 | P1 | /admin/brain/conversations | `apiFetch` JSON assumptions | PR-C | Content-type guard |
| F-041 | P2 | /admin/brain/conversations | Attachment alt text | PR-D | Meaningful `alt` |
| F-042 | P1 | /admin/brain/self-improvement | Client env secret props | PR-B | Server-only proxy for audits |
| F-043 | P1 | /admin/brain/self-improvement | Internal PR jargon | PR-C | Founder-facing copy |
| F-044 | P2 | /admin/brain/self-improvement | Eight tabs density | PR-D | Overflow/scroll tabs |
| F-045 | P1 | /admin/expenses | Client fetch silent failure | PR-C | Toast + retry path |
| F-046 | P1 | /admin/expenses | Multi-status client filter | PR-B | API contract documented/fixed |
| F-047 | P2 | /admin/expenses | Bespoke tabs | PR-D | `TabbedPageShell` adoption |
| F-048 | P1 | /admin/pr-pipeline | Empty copy vs token error overlap | PR-C | Context-specific empty states |
| F-049 | P2 | /admin/pr-pipeline | External docs `Link` | PR-D | Use `<a>` for external |
| F-050 | P1 | Legacy redirects | Sidebar/quick links drift | PR-C | Repo-wide link audit |
| F-051 | P1 | /admin/docs | Search submit has no progress | PR-C | Transition feedback |
| F-052 | P2 | /admin/docs/[slug] | No in-app TOC | PR-D | Anchor nav optional |
| F-053 | P2 | /admin | TrackersRail null layout | PR-D | Stable card heights |
| F-054 | P2 | /admin | TrackersRail silent catch | PR-B | Structured errors |
| F-055 | P1 | Tab shells | Incomplete keyboard tab pattern | PR-D | Arrow keys or docs waiver |
| F-056 | P2 | Tab shells | Error boundary silent | PR-B | Log + optional toast |

## WS-76 Wave L PR-C — remediation log

Land on branch `wave-l-pr-c/page-polish` via commit **`1f8052d46b3142db306168c630585d60a459a384`** ([PR #487](https://github.com/paperwork-labs/paperwork/pull/487)).

| ID | Done | Implementation note |
|----|------|---------------------|
| F-006 | ✓ | `layout` → `expensesCountsUnknown`; Expenses nav muted `…` when counts unknown. |
| F-007 | ✓ | `AdminRouteFallback` + `Suspense` in admin `layout.tsx`. |
| F-008 | ✓ | Mobile drawer + `AdminSidebarPanel` (`admin-layout-client.tsx`). |
| F-014 | ✓ | Overview n8n banner + `n8nConfigured` from `isN8nIntegrationConfigured()` (SSR + `/api/admin/overview`). |
| F-017 | ✓ | Reserved `border-l-2` on nav links. |
| F-018 | ✓ | Overview quick link → `/admin/architecture?tab=flows`. |
| F-020 | ✓ | Traffic light `standby` when n8n unwired and no workflows. |
| F-021 | ✓ | Slack deep link env: `NEXT_PUBLIC_SLACK_DAILY_BRIEFING_URL` / `SLACK_DAILY_BRIEFING_URL`. |
| F-022 | ✓ | PR activity text labels (`Approved`, etc.). |
| F-023 | ✓ | `motion-safe:animate-ping` on green traffic light. |
| F-024 | ✓ | `PushSubscribeCard`: `console.warn` on subscription probe failure. |
| F-025 | ✓ | Architecture graph dynamic-import loading skeleton. |
| F-029 | ✓ | Cost tab → Infrastructure Services `#infra-quotas`; `id="infra-quotas"` on quota section. |
| F-039–F-041 | ✓ | Conversations: `HqErrorState` + optional `HqMissingCredCard`; attachment `alt` from path/mime. |
| F-042–F-043 | ✓ | `/api/admin/brain/audits/*` proxy; `AuditsTab` same-origin fetches (no public Brain secret). |
| F-045 | ✓ | Expenses list: `HqErrorState`, retry, `toast.error` on API failure. |
| F-048 | ✓ | PR pipeline already distinguishes token vs empty (verified). |
| F-050 | ✓ | Command palette: Workflows + Secrets deep links; `/admin/ops` + `/admin/agents` redirect straight to Architecture → Flows (no workflows hop). |
| F-051 | ✓ | Docs hub: `DocsHubSearchForm` busy state. |
| F-012 | — | Personas / `PageHeader` drift — deferred. |
| F-031 | — | Sprints unknown pill — not in this PR. |
| F-033 | — | No change (workstreams read-only copy already present). |
| F-036 | — | Product plan `<details>` — not in this PR. |
| F-001–F-005 | — | P0 data-honesty / infra tab namespace — **PR-B**. |

## Out of scope (deferred)

- **No `/admin/runbook` route** — runbooks live under `docs/runbooks/` and the Docs hub (`/admin/docs`); a dedicated Studio runbook browser would be WS-77+ IA work, not this audit's implementation scope.
- **`/admin/ops/credentials`** — `/admin/ops` redirects to workflows activity (`apps/studio/src/app/admin/ops/page.tsx:1-7`); credentials UX belongs to WS-57 / Architecture > Infrastructure > Secrets per procedural memory `secrets_registry_hardening_ws57_batch_c`.
- **Customer-facing apps** (AxiomFolio, FileFree, etc.) — tracked separately via `UX_AUDIT_2026Q2.md` and product plans under `docs/axiomfolio/plans/`.
- **Full removal of Framer Motion** on Overview — optional perf pass (WS-78) once data correctness PR-B lands.
- **Brain Conversations backfill / PR-2** — audit reflects current `conversations-client.tsx` behavior; shipping backfill does not retroactively change the silent-null server fetch finding until code changes land.

## Appendix: files read

- `docs/axiomfolio/plans/UX_AUDIT_2026Q2.md`
- `docs/axiomfolio/DESIGN_SYSTEM.md`
- `docs/axiomfolio/FRONTEND_UI.md`
- `docs/axiomfolio/plans/MASTER_PLAN_2026.md` (skimmed)
- `.cursor/rules/no-silent-fallback.mdc`, `.cursor/rules/ux.mdc`, `.cursor/rules/code-quality-guardian.mdc`
- `apis/brain/data/procedural_memory.yaml` (skimmed)
- `apps/studio/src/app/admin/admin-layout-client.tsx`
- `apps/studio/src/app/admin/layout.tsx`
- `apps/studio/src/app/admin/page.tsx`
- `apps/studio/src/app/admin/overview-client.tsx`
- `apps/studio/src/app/admin/_components/trackers-rail.tsx`
- `apps/studio/src/components/pwa/PushSubscribeCard.tsx`
- `apps/studio/src/app/admin/workstreams/page.tsx`
- `apps/studio/src/app/admin/workstreams/workstreams-client.tsx`
- `apps/studio/src/app/admin/sprints/sprints-overview-tab.tsx`
- `apps/studio/src/app/admin/architecture/page.tsx`
- `apps/studio/src/app/admin/architecture/tabs/overview-tab.tsx`
- `apps/studio/src/app/admin/architecture/architecture-client.tsx` (partial)
- `apps/studio/src/app/admin/infrastructure/page.tsx`
- `apps/studio/src/app/admin/infrastructure/infra-client.tsx` (partial)
- `apps/studio/src/app/admin/infrastructure/tabs/{overview-tab,services-tab,logs-tab,cost-tab}.tsx`
- `apps/studio/src/app/admin/products/page.tsx`
- `apps/studio/src/app/admin/products/[slug]/plan/page.tsx`
- `apps/studio/src/app/admin/brain/personas/{page,personas-tabs-client}.tsx`
- `apps/studio/src/app/admin/brain/conversations/{page,conversations-client}.tsx` (partial)
- `apps/studio/src/app/admin/brain/self-improvement/{page,self-improvement-client}.tsx` (partial)
- `apps/studio/src/app/admin/expenses/{page,expenses-client}.tsx` (partial)
- `apps/studio/src/app/admin/pr-pipeline/page.tsx`
- `apps/studio/src/app/admin/{secrets,ops,workflows,automation,analytics,n8n-mirror,brain-learning}/page.tsx`
- `apps/studio/src/app/admin/docs/{page,search/page,[slug]/page}.tsx` (partial)
- `apps/studio/src/app/admin/tasks/page.tsx`
- `apps/studio/src/lib/command-center.ts` (partial)
- `apps/studio/src/lib/pr-pipeline.ts` (partial)
- `apps/studio/src/components/layout/{TabbedPageShellNext,studio-tabbed-page-shell}.tsx`
