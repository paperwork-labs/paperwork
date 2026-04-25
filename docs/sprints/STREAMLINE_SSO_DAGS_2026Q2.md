---
title: Streamline + SSO + Real DAGs (2026 Q2)
owner: engineering
last_reviewed: 2026-04-25
doc_kind: sprint
domain: company
status: in_progress
sprint:
  start: 2026-04-25
  end: 2026-05-09
  duration_weeks: 2
opened: 2026-04-25
target_close: 2026-05-09
related_prs:
  - 151
  - 153
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
- shipped 2026-04-25: **T1.1** — Per-job `SCHEDULER_N8N_MIRROR_<ID>` flags (uppercased n8n mirror job id) with global fallback, `agent_scheduler_runs` history for each shadow execution, and `GET /api/v1/admin/scheduler/n8n-mirror/status` for last run + 24h success/error counts. Runbook: [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md). Migration: `apis/brain/alembic/versions/002_agent_scheduler_runs.py`.
- shipped 2026-04-25: **T3.1 (foundation)** — Studio has `@clerk/nextjs` with `ClerkProvider`, `sign-in` / `sign-up` catch-all routes, and `clerkMiddleware` composed with the existing Basic Auth escape hatch on `/admin` and `/api/admin` in production; public routes and `/api/secrets*` skip this gate. Operator runbook: [docs/infra/CLERK_STUDIO.md](../infra/CLERK_STUDIO.md).

## What we learned

- Per-job `SCHEDULER_N8N_MIRROR_*` must use the same uppercased job id as `N8N_MIRROR_SPECS` (e.g. `N8N_SHADOW_BRAIN_DAILY`, not a short name like `pr_sweep` — the in-process `pr_sweep` scheduler is separate from n8n mirror ids).
- A single `clerkMiddleware` handler can grant production admin access if either `auth().userId` (Clerk) is present or the legacy Basic `Authorization` header matches `ADMIN_EMAILS` / `ADMIN_ACCESS_PASSWORD`, while local dev can keep admin routes open by short-circuiting on `NODE_ENV === "development"`.


## Tracker

Status on parent bullets: `[ ]` pending, `[~]` in progress, `[x]` shipped. Sub-bullets use the same markers.

- **T1 — Orchestration consolidation** `[ ]`
  - `[ ]` Brain APScheduler owns all cron-style schedules; n8n is webhook / event-only for new work.
  - `[ ]` Persist APScheduler jobs with SQLAlchemyJobStore on Postgres so restarts do not drop work.
  - `[ ]` Document the split: where schedules live, how to change them, and how Slack alerts dedupe.
  - `[ ]` Migrate the existing n8n cron set with a checklist + rollback path (shadow period acceptable).

- **T2 — Single persona vocabulary** `[ ]`
  - `[ ]` PersonaSpec slugs under `apis/brain/app/personas/` are the only canonical persona IDs.
  - `[ ]` Align Studio `WORKFLOW_META` role labels, `system-graph.json` `owner_persona`, and n8n `persona_pin` to those slugs verbatim.
  - `[ ]` CI gate blocks drift between Brain specs and Studio / graph / automation references.

- **T3 — Clerk SSO (cross-product)** `[~]`
  - `[x]` Adopt Clerk via Vercel Marketplace; auto-provisioned env vars across linked Vercel projects. (T3.1: Studio foundation — PR #151)
  - `[ ]` Roll out per-product theming (Appearance API) while preserving a single identity graph.
  - `[ ]` Plan verifier paths for AxiomFolio APIs post–Next.js migration; retire parallel JWT/session schemes safely.
  - `[ ]` Communicate session cutover; keep documented Basic Auth escape hatch for Studio until explicitly removed.

- **T4 — Real DAGs + workflow UX** `[ ]`
  - `[ ]` Replace placeholder or unreadable DAG views with layouts that survive real n8n graphs (zoom, labels, swim-lanes as needed).
  - `[ ]` Tie visualization truth to the same orchestration story as T1 so operators are not reading fiction.
  - `[ ]` Ship incremental UX wins that directly address the "fugly DAG" feedback loop.

- **T5 — AxiomFolio Next.js absorb** `[ ]`
  - `[ ]` Continue route port and shared patterns from the Q3 migration plan; avoid two frontends forever.
  - `[ ]` Coordinate hosting cutover (Vercel-first) with Clerk and infra inventory updates.
  - `[ ]` Keep API/worker contracts stable during the absorb; feature flags or strangler paths where risk is high.
  - `[ ]` Cross-check `docs/axiomfolio/plans/NEXTJS_MIGRATION_2026Q3.md` for route priority vs this sprint window.

## Follow-ups


## Related

- **Predecessor sprint** (docs spine, trackers, Studio architecture / DAG zoom pass): [DOCS_STREAMLINE_AND_TRACKERS_2026Q2.md](DOCS_STREAMLINE_AND_TRACKERS_2026Q2.md)
- **Decision Log** (SSO direction, orchestrator unification, persona vocabulary): [docs/KNOWLEDGE.md](../KNOWLEDGE.md)
- **Rules** — [.cursor/rules/agent-ops.mdc](../../.cursor/rules/agent-ops.mdc) (models, personas, agent wiring), [.cursor/rules/secrets-ops.mdc](../../.cursor/rules/secrets-ops.mdc) (vault, Clerk secrets, rotation), [.cursor/rules/infra-ops.mdc](../../.cursor/rules/infra-ops.mdc) (Vercel/Render, Marketplace linking), [.cursor/rules/legal.mdc](../../.cursor/rules/legal.mdc) (ToS/Privacy surfaces for SSO)
