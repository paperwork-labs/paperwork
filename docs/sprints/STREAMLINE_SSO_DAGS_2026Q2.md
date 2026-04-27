---
title: Streamline + SSO + Real DAGs (2026 Q2)
owner: engineering
last_reviewed: 2026-04-26
doc_kind: sprint
domain: company
status: active
sprint:
  start: 2026-04-25
  end: 2026-05-09
  duration_weeks: 2
opened: 2026-04-25
target_close: 2026-05-09
related_prs:
  - 146
  - 147
  - 148
  - 149
  - 150
  - 151
  - 152
  - 153
  - 154
  - 155
  - 156
  - 157
  - 160
  - 167
  - 168
  - 169
  - 170
  - 197
  - 198
  - 200
  - 199
  - 201
  - 204
---

# Streamline + SSO + Real DAGs (2026 Q2)

**Sprint window**: 2026-04-25 → 2026-05-09 (~2 weeks)
**Status**: in_progress — Track 1 cleanup PR opens the spine; Tracks 2–5 roll forward through early May.
**Predecessor**: [DOCS_STREAMLINE_AND_TRACKERS_2026Q2.md](DOCS_STREAMLINE_AND_TRACKERS_2026Q2.md) (docs + trackers + Studio architecture pass)
**PRs**: populate `related_prs` in frontmatter as merges land; deep-link here when GitHub numbers exist.

When a PR merges: append `shipped YYYY-MM-DD:` bullets to **Outcome**, bump `related_prs`, and advance tracker markers `[ ]` → `[~]` → `[x]` with the track ID called out in the PR title when practical. Drop **What we learned** bullets when a track surfaces a durable surprise (same habit as the predecessor sprint).

This sprint stacks on the docs-streamline mini-sprint: trackers, Brain CFO digest, and Studio architecture pages already exist. The five tracks below are the *product spine* work — orchestration, identity, vocabulary, operator-facing graphs, and the AxiomFolio frontend migration — so one person can reason about "what runs," "who signed in," and "which persona said it" without opening four different tools.

Sequencing intuition (not separate sections): fix **T2** slugs before bulk **T1** n8n edits so `persona_pin` renames are not done twice. **T3** Clerk Marketplace install should align with Vercel project linking before **T5** production traffic moves. **T4** can ship readability wins on current n8n exports early; labels that reflect Brain-owned schedules tighten after **T1** is live. Orchestration cutover risk: prefer shadow runs or duplicate Slack until confidence is high — a missed cron beats an ugly graph for severity.

## Goal

Ship an aggressive end-to-end streamline: one orchestration brain for scheduled work, one persona vocabulary everywhere, Clerk-backed SSO so a LaunchFree user can use FileFree without re-registering, workflow DAGs that are actually legible (and not embarrassing in demos), and AxiomFolio absorbed into the Next.js / Vercel stack when the migration shell is far enough along.

Directive to keep visible: *"could do a way better job with the workflow dags and make them less fugly!"*

Non-goals for this window: rewriting every n8n workflow on day one (strangler moves are fine), or finishing all 100+ AxiomFolio routes — the absorb track is *directionally correct progress* plus hosting alignment, not a big-bang cutover unless risk says otherwise.

Acceptance theme for the window: operators can name the single system that fires crons, engineers can grep one slug vocabulary, founders can demo SSO across two products without apologizing for the graph view, and AxiomFolio's Next.js trajectory is unambiguous in `render.yaml` + Vercel inventory.

## Outcome

- _Tracking — updates as each track ships_
- 2026-04-26: Track K — `brain_data_source_monitor` cutover (LA tz, `BRAIN_OWNS_DATA_SOURCE_MONITOR=true`)
- 2026-04-26: Track K — `brain_data_deep_validator` cutover (LA tz, `BRAIN_OWNS_DATA_DEEP_VALIDATOR=true`)
- shipped 2026-04-25: **T1.1** — Per-job `SCHEDULER_N8N_MIRROR_<ID>` flags (uppercased n8n mirror job id) with global fallback, `agent_scheduler_runs` history for each shadow execution, and `GET /api/v1/admin/scheduler/n8n-mirror/status` for last run + 24h success/error counts. Runbook: [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md). Migration: `apis/brain/alembic/versions/002_agent_scheduler_runs.py`. PRs #148, #153.
- shipped 2026-04-25: **T1.2** — First real Brain APScheduler job for the **Brain Daily Trigger** n8n flow: `BRAIN_OWNS_DAILY_BRIEFING` enables `brain_daily_briefing` (07:00 UTC) calling `agent.process` + `#daily-briefing`, and suppresses `n8n_shadow_brain_daily` so the mirror cannot double with production. Code: `apis/brain/app/schedulers/brain_daily_briefing.py`. Runbook: [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md). PR #160; builds on PR #153 (per-job mirror flags + `agent_scheduler_runs`).
- shipped 2026-04-26: **T1.5 — Brain Weekly Trigger** — `BRAIN_OWNS_BRAIN_WEEKLY` enables `brain_weekly_briefing` (Sundays 18:00 UTC, `0 18 * * 0`), same `agent.process` + Slack shape as `infra/hetzner/workflows/retired/brain-weekly-trigger.json` (`#all-paperwork-labs`), and suppresses `n8n_shadow_brain_weekly`. Code: `apis/brain/app/schedulers/brain_weekly_briefing.py`. Runbook: [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md). PR #199.
- shipped 2026-04-26: **T1.4** — `BRAIN_OWNS_CREDENTIAL_EXPIRY` + `brain_credential_expiry` cut the **Credential Expiry Check** n8n cron to Brain (same vault + `#alerts` Slack as `retired/credential-expiry-check.json`); `n8n_shadow_credential_expiry` suppressed. Pattern: same as T1.2 / T1.3 (#160, #166). Code: `apis/brain/app/schedulers/credential_expiry.py`. Runbook: [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md). PR #170.
- shipped 2026-04-26: **T1.6** — `BRAIN_OWNS_WEEKLY_STRATEGY` + `brain_weekly_strategy` cut the **Weekly Strategy Check-in** n8n cron to Brain: `agent.process` with the `strategy` persona (per Streamline T2), Slack `#all-paperwork-labs` (same as `retired/weekly-strategy-checkin.json`); `n8n_shadow_weekly_strategy` suppressed. Code: `apis/brain/app/schedulers/weekly_strategy.py`. Runbook: [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md). PR #200.
- shipped 2026-04-26: **T1 (Infra Health, interval)** — `BRAIN_OWNS_INFRA_HEALTH` + `brain_infra_health` cut **Infra Health Check** to Brain: first-party **`IntervalTrigger`** (30m, not `CronTrigger`), n8n API parity with `retired/infra-health-check.json`, fingerprint dedup + optional `INFRA_HEALTH_REMINDER_HOURS` re-alert, `n8n_shadow_infra_health` suppressed. Code: `apis/brain/app/schedulers/infra_health.py`. Runbook: [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md). PR #201.
- shipped 2026-04-25: **T1.5** — Studio admin page **`/admin/n8n-mirror`** surfaces the Brain n8n mirror status endpoint: per-job shadow on/off, last run + 24h success/error counts, cutover heuristics for T1.2/T1.3 job ids, ~30s auto-refresh. Code: `apps/studio/src/app/admin/n8n-mirror/`, `apps/studio/src/components/admin/N8nMirrorStatusClient.tsx`, `apps/studio/src/app/api/admin/n8n-mirror/status/route.ts`. Runbook: [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md#studio-admin-paperwork-studio) (Studio Admin section). PR #168.
- shipped 2026-04-25: **T2.3** — Persona vocabulary unified across Brain `PersonaSpec/`, Studio `WORKFLOW_META`, `system-graph.json` `owner_persona`, and n8n `persona_pin`. CI gate `scripts/check_persona_vocabulary.py` blocks future drift. PR #150.
- shipped 2026-04-25: **T3.1 (foundation)** — Studio has `@clerk/nextjs` with `ClerkProvider`, `sign-in` / `sign-up` catch-all routes, and `clerkMiddleware` composed with the existing Basic Auth escape hatch on `/admin` and `/api/admin` in production; public routes and `/api/secrets*` skip this gate. Operator runbook: [docs/infra/CLERK_STUDIO.md](../infra/CLERK_STUDIO.md). PR #151.
- shipped 2026-04-25: **T3.1b** — Studio Clerk pages adopt the dark-themed `studioClerkAppearance` (HSL CSS-var bridge to Clerk variables + custom `elements` Tailwind). PR #152.
- shipped 2026-04-25: **T3.2** — Clerk SDK foundation extended to LaunchFree (PR #155) and FileFree (PR #156): `<ClerkProvider>`, sign-in/up catch-alls, and `clerkMiddleware` composed with each app's existing legacy session / Basic Auth escape hatches. Runbooks: [docs/infra/CLERK_LAUNCHFREE.md](../infra/CLERK_LAUNCHFREE.md), [docs/infra/CLERK_FILEFREE.md](../infra/CLERK_FILEFREE.md).
- shipped 2026-04-26: **T3.2 (Trinkets)** — `<ClerkProvider>`, sign-in/up catch-all routes, `clerkMiddleware` (public utility app; no legacy session or Basic Auth to compose). Trinkets Clerk appearance: indigo `#6366F1` + sky cyan `#38BDF8`. Runbook: [docs/infra/CLERK_TRINKETS.md](../infra/CLERK_TRINKETS.md). PR #197.
- shipped 2026-04-26: **T3.2 (Distill)** — `@clerk/nextjs` + `<ClerkProvider>`, sign-in/sign-up catch-alls, `clerkMiddleware` on `/dashboard` only (no legacy gate), and `distillClerkAppearance` (teal `#0F766E` + burnt orange `#C2410C`). Runbook: [docs/infra/CLERK_DISTILL.md](../infra/CLERK_DISTILL.md). PR #198.
- shipped 2026-04-25: **T3.4** — AxiomFolio `axiomfolio-next` Clerk UI themed via `axiomfolioClerkAppearance` + `ClerkAuthPageShell`; `@clerk/themes` aligned with other apps. Runbook: [docs/infra/CLERK_AXIOMFOLIO.md](../infra/CLERK_AXIOMFOLIO.md#theming). PR #167.
- shipped 2026-04-25: **T4** — Replaced Studio's placeholder DAG views with `@xyflow/react` graphs that survive real persona / workflow shapes (zoom, pan, labelled edges). PR #147.
- shipped 2026-04-26: **T4 (live data)** — Studio `/admin/architecture` loads live schedule ownership from Brain `GET /api/v1/admin/scheduler/n8n-mirror/status`, tints graph nodes (Brain-first vs n8n shadow vs error), last production Vercel deploy per app, and health-probe recency; SSR falls back to bundled `system-graph.json` with a banner when Brain is unreachable; 30s cache + client refresh. Code: `apps/studio/src/lib/get-architecture-payload.ts`, `apps/studio/src/app/api/admin/architecture/route.ts`, `apps/studio/src/components/admin/LiveDataBadge.tsx`.
- shipped 2026-04-25: **T5** — AxiomFolio Next.js absorb advanced through 5 batches: public + onboarding (#146), auth flow (#149), settings shell + 5 settings pages (#154), market dashboard / education / intelligence / tracked + backtest lab (#157). Pattern: thin `page.tsx` (`RequireAuthClient` + `<Suspense>`) wrapping client components under `src/components/`, with `dynamic(..., { ssr: false })` for chart libs.
- shipped 2026-04-26: **T5 (settings ports)** — Remaining settings routes: account risk, data privacy, notifications, and users (`apps/axiomfolio-next/src/app/settings/*`, client components under `src/components/settings/`). PR #169.
- shipped 2026-04-26: **T1.x — Sprint auto-logger** — Brain APScheduler job (`sprint_auto_logger`, `*/15` UTC) batches merged PRs that declare a sprint (`Sprint:` body line and/or `sprint:*` label) into one bot PR updating `## Outcome` + `related_prs` in `docs/sprints/*.md`; gated by `BRAIN_OWNS_SPRINT_AUTO_LOGGER`. Code: `apis/brain/app/schedulers/sprint_auto_logger.py`. Runbook: [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md). PR #204.

## What we learned

- Per-job `SCHEDULER_N8N_MIRROR_*` must use the same uppercased job id as `N8N_MIRROR_SPECS` (e.g. `N8N_SHADOW_BRAIN_DAILY`, not a short name like `pr_sweep` — the in-process `pr_sweep` scheduler is separate from n8n mirror ids).
- A single `clerkMiddleware` handler can grant production admin access if either `auth().userId` (Clerk) is present or the legacy Basic `Authorization` header matches `ADMIN_EMAILS` / `ADMIN_ACCESS_PASSWORD`, while local dev can keep admin routes open by short-circuiting on `NODE_ENV === "development"`.
- A dedicated **`BRAIN_OWNS_*` env flag** can gate the first-party APScheduler job while `should_register_n8n_shadow_for_job` drops the matching `n8n_shadow_*` row — no duplicate schedules without editing n8n JSON.
- For squash-merged PRs, Vercel builds the *merge commit* SHA on `main` — NOT the PR branch's last `head.sha`. Promotion automation must resolve `pull_request.merge_commit_sha` first; the previous version of `vercel-promote-on-merge.yaml` searched only `head.sha` and silently failed for PR #156. Workflow now tries both. (See workflow header docstring for the gotcha note.)
- Subagents working on the same monorepo branch will collide on `pnpm-lock.yaml` if they install dependencies in parallel from a shared worktree. Solution: use `best-of-n-runner` to give each subagent its own isolated git worktree; each branch's lockfile diff stays tightly scoped to that PR's package.


## Tracker

Status on parent bullets: `[ ]` pending, `[~]` in progress, `[x]` shipped. Sub-bullets use the same markers.

- **T1 — Orchestration consolidation** `[~]`
  - `[~]` Brain APScheduler owns all cron-style schedules; n8n is webhook / event-only for new work. (T1.1 shadow in #148/#153; T1.2 `brain_daily_briefing` #160; T1.3 `brain_infra_heartbeat` #166; **T1.4** `brain_credential_expiry` #170; **T1.5** Brain Weekly — `BRAIN_OWNS_BRAIN_WEEKLY` + `brain_weekly_briefing` #199; **T1.6** `BRAIN_OWNS_WEEKLY_STRATEGY` + `brain_weekly_strategy` #200; **T1** `brain_infra_health` — **30m `IntervalTrigger`** for Infra Health Check, separate from daily cron `brain_infra_heartbeat`.)
  - `[x]` Persist APScheduler jobs with SQLAlchemyJobStore on Postgres so restarts do not drop work. (PR #148)
  - `[x]` Document the split: where schedules live, how to change them, and how Slack alerts dedupe. ([docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md))
  - `[~]` Migrate the existing n8n cron set with a checklist + rollback path (shadow period acceptable). (Per-job `BRAIN_OWNS_*` pattern: T1.2 daily briefing, T1.3 `BRAIN_OWNS_INFRA_HEARTBEAT` + `n8n_shadow_infra_heartbeat` suppression, T1.4 `BRAIN_OWNS_CREDENTIAL_EXPIRY` + `n8n_shadow_credential_expiry` suppression, T1.5 `BRAIN_OWNS_BRAIN_WEEKLY` + `n8n_shadow_brain_weekly` suppression, **T1.6** `BRAIN_OWNS_WEEKLY_STRATEGY` + `n8n_shadow_weekly_strategy` suppression, **T1** `BRAIN_OWNS_INFRA_HEALTH` + `n8n_shadow_infra_health` for the 30m interval health check.)

- **T2 — Single persona vocabulary** `[x]`
  - `[x]` PersonaSpec slugs under `apis/brain/app/personas/` are the only canonical persona IDs. (PR #150)
  - `[x]` Align Studio `WORKFLOW_META` role labels, `system-graph.json` `owner_persona`, and n8n `persona_pin` to those slugs verbatim. (PR #150)
  - `[x]` CI gate blocks drift between Brain specs and Studio / graph / automation references. (`scripts/check_persona_vocabulary.py` + `.github/workflows/persona-vocab.yaml`, PR #150)

- **T3 — Clerk SSO (cross-product)** `[~]`
  - `[x]` Adopt Clerk via Vercel Marketplace; auto-provisioned env vars across linked Vercel projects. (T3.1: Studio foundation — PR #151)
  - `[x]` Studio Clerk pages themed via Appearance API. (T3.1b — PR #152)
  - `[x]` LaunchFree + FileFree + **Trinkets** + **Distill** wired: `<ClerkProvider>` + sign-in/up; LaunchFree/FileFree `clerkMiddleware` with legacy gates (PRs #155, #156); Trinkets public shell (PR #197, [CLERK_TRINKETS.md](../infra/CLERK_TRINKETS.md)); Distill `/dashboard` Clerk-only (PR #198, [CLERK_DISTILL.md](../infra/CLERK_DISTILL.md)).
  - `[~]` Roll out per-product theming (Appearance API) while preserving a single identity graph. (T3.3 — Studio done; LaunchFree + FileFree in flight as B5-T3.3.)
  - `[x]` **T3.4** — AxiomFolio (`axiomfolio-next`) per-app Clerk theming: `axiomfolioClerkAppearance` (Appearance API + `@clerk/themes` dark), `ClerkAuthPageShell` on `/sign-in` and `/sign-up`, `ClerkProvider` `appearance` for `UserButton` and global Clerk UI. ([docs/infra/CLERK_AXIOMFOLIO.md](../infra/CLERK_AXIOMFOLIO.md#theming))
  - `[ ]` Plan verifier paths for AxiomFolio APIs post–Next.js migration; retire parallel JWT/session schemes safely.
  - `[ ]` Communicate session cutover; keep documented Basic Auth escape hatch for Studio until explicitly removed.
  - `[~]` **T3 consumer cutover (in flight)** — shared `@paperwork-labs/auth-clerk` package: PR [#234](https://github.com/paperwork-labs/paperwork/pull/234); `accounts.paperworklabs.com` DNS + satellite steps: [docs/infra/CLERK_ACCOUNTS_DNS_TONIGHT.md](../infra/CLERK_ACCOUNTS_DNS_TONIGHT.md) (runbook; land with Track H1).
    - FileFree: cut consumer `/auth/login` + `/auth/register` over to Clerk `/sign-in` + `/sign-up`; remove legacy session hooks/middleware once parity; FileFree API verifies Clerk JWTs.
    - AxiomFolio (`axiomfolio-next`): finish consumer auth on Clerk; APIs move from `qm_token` to Clerk JWT verification behind a short shadow window; backfill `clerk_user_id` by email where needed.
    - LaunchFree + Distill + Trinkets: adopt shared `SignInShell` + locked app-name-primary wordmark tokens from the package; drop duplicate per-app `clerk-appearance` copies when consolidated.
    - Studio: keep Clerk + `ADMIN_EMAILS` allowlist; retire Basic once operators publish a cutover date.
    - `apps/accounts/`: host Paperwork ID headline only on `accounts.paperworklabs.com` per [CLERK_SATELLITE_TOPOLOGY.md](../infra/CLERK_SATELLITE_TOPOLOGY.md) (if present) / Track H4 plan.
    - Python sidecars (FileFree, AxiomFolio, Brain as needed): use shared `paperwork_auth` / JWT verifier helpers aligned with the package’s Clerk JWKS contract.

- **T4 — Real DAGs + workflow UX** `[~]`
  - `[x]` Replace placeholder or unreadable DAG views with layouts that survive real n8n graphs (zoom, labels, swim-lanes as needed). (`@xyflow/react` adopted in PR #147)
  - `[~]` Tie visualization truth to the same orchestration story as T1 so operators are not reading fiction. (Persona slugs unified in #150; live status feed pending the full T1 cutover.)
  - `[~]` Ship incremental UX wins that directly address the "fugly DAG" feedback loop.

- **T5 — AxiomFolio Next.js absorb** `[~]`
  - `[~]` Continue route port and shared patterns from the Q3 migration plan; avoid two frontends forever. (Public/onboarding #146, auth flow #149, settings #154, market+backtest #157; signals + trade-cards + shadow-trades in flight as B5-T5.)
  - `[ ]` Coordinate hosting cutover (Vercel-first) with Clerk and infra inventory updates.
  - `[ ]` Keep API/worker contracts stable during the absorb; feature flags or strangler paths where risk is high.
  - `[ ]` Cross-check `docs/axiomfolio/plans/NEXTJS_MIGRATION_2026Q3.md` for route priority vs this sprint window.

## Follow-ups


## Related

- **Predecessor sprint** (docs spine, trackers, Studio architecture / DAG zoom pass): [DOCS_STREAMLINE_AND_TRACKERS_2026Q2.md](DOCS_STREAMLINE_AND_TRACKERS_2026Q2.md)
- **Decision Log** (SSO direction, orchestrator unification, persona vocabulary): [docs/KNOWLEDGE.md](../KNOWLEDGE.md)
- **Rules** — [.cursor/rules/agent-ops.mdc](../../.cursor/rules/agent-ops.mdc) (models, personas, agent wiring), [.cursor/rules/secrets-ops.mdc](../../.cursor/rules/secrets-ops.mdc) (vault, Clerk secrets, rotation), [.cursor/rules/infra-ops.mdc](../../.cursor/rules/infra-ops.mdc) (Vercel/Render, Marketplace linking), [.cursor/rules/legal.mdc](../../.cursor/rules/legal.mdc) (ToS/Privacy surfaces for SSO)
