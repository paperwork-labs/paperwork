# WS-69 — Studio IA Reorg + Sprint/Plan Data Reconcile

**Status**: brief / not yet planned
**Priority**: medium (founder-noticed UX rot, no $$ bleed)
**Blocked by**: nothing
**Related**: WS-67 (Brain coach), tracker-index spine (PR #144)
**Authored**: 2026-04-28 — captured at end of cost-bleed-stop chat for clean handoff

---

## Why this exists

Founder observation 2026-04-28 (verbatim):

> we have a lot of things in command-center now.. I am not sure if sprints are aligned properly everywhere or if accurate.. like overview one says random stuff
> reorg the nav list - pr pipeline and founder actions (are these accurate?) should be part of tracker
> all n8n persona trackers stuff should get streamlined we delete old stuff
> possibly we switch to plan mode if you want basically you have tracker, architecture - status & docs + automation

The Studio admin nav has grown to **16 items in 3 groups** during the L4/L5 blitz. Tiles on `/admin` overview disagree with the values on the dedicated tracker pages. n8n-era persona scaffolding still ships in nav even though the persona work moved into Brain.

## Three sub-problems

### 1. Data accuracy / single-source-of-truth audit

**Confirmed inconsistency** (verified at the diff level):
- `apps/studio/src/app/admin/_components/trackers-rail.tsx` line 24-25 uses **raw** `s.status === "active" | "shipped"`.
- `apps/studio/src/app/admin/sprints/page.tsx` line 102-103 uses **reconciled** `isSprintActiveForUi()` / `isSprintShippedForUi()` from `apps/studio/src/lib/sprint-reconcile.ts`.
- Same JSON source, different numbers. That's why Overview says "0 + 3 shipped" while Sprints page can show different counts.

**Suspected inconsistencies** (need a 30-min audit):
- "active plans" count uses `status === "active"`, but plan files set status to `in_progress`, `draft`, `planned`. Likely the count is structurally always 0.
- "Tasks (company)" uses `!/done|complete/i.test(d.status)` — probably correct, but the label `critical dates open in docs/TASKS.md` is jargon-y.
- Workstreams page has its own KPI computer (`computeKpis` in `workstreams-client.tsx`); never cross-checked against tracker-index.

**Fix shape**: a single reconciler function used by every page that surfaces these numbers. Probably extend `sprint-reconcile.ts` to a generic `tracker-reconcile.ts` exposing `activeSprints()`, `shippedSprints()`, `activePlans()`, `openCriticalDates()`. Delete the inline filters everywhere else.

### 2. Nav reorg

**Current** (`apps/studio/src/app/admin/admin-layout-client.tsx:42-78`):

```
(no label)
  Overview

Trackers
  Tasks (company)
  Products
  Sprints
  Workstreams

System
  Architecture
  PR pipeline
  Workflows
  n8n cron mirror
  Docs
  Automation
  Analytics
  Infrastructure
  Brain learning
  Secrets
  Founder actions
```

**Proposed** (founder-stated taxonomy: `tracker / architecture - status & docs / automation`):

```
(no label)
  Overview

Trackers (work-in-flight things you can act on)
  Tasks (company)
  Products
  Sprints
  Workstreams
  PR pipeline                 ← moved up from System
  Founder actions             ← moved up from System

Architecture (system truth + reference)
  Architecture                ← landing page
  Docs
  Infrastructure
  Brain learning
  Secrets
  Analytics                   ← optional; arguably its own bucket

Automation (running engines)
  Workflows
  n8n cron mirror             ← decommission candidate (see #3)
  Automation
```

That's still 14 items. Could go to 12 if `n8n cron mirror` is folded into `Automation` and `Brain learning` is folded into `Architecture` as a sub-tab. Decide in plan mode.

### 3. n8n persona-tracker decommission

The n8n era spawned several scaffolds that are now dead-or-dying after the move to Brain:
- n8n cron mirror page (do we even run cron in n8n anymore?)
- Persona-keyed dashboards
- Workflow tagging UI
- Old "tracker" docs in `docs/n8n/` if still around

Do an inventory: which `apps/studio/src/app/admin/n8n*` and `apps/studio/src/app/admin/workflows*` pages actually serve a current operating need vs are vestigial? Delete the dead ones; keep the ones that actually drive an action.

## Audit checklist (rough scope estimate: 1-2 days)

- [ ] Grep for every place that filters tracker JSON inline (`s.status === "..."`); list them.
- [ ] Verify every counter on `/admin` overview against the value on its dedicated page; document each delta.
- [ ] Choose a reconciliation policy per status type (sprints, plans, tasks, workstreams) — write it once, in code, in `lib/tracker-reconcile.ts`.
- [ ] Refactor every consumer to call the reconciler; delete inline filters.
- [ ] Inventory `apps/studio/src/app/admin/n8n*`, `workflows*`, `automation*` — KEEP / DELETE / MERGE.
- [ ] Reorg nav per proposal above; settle on 3-bucket vs 4-bucket (Analytics call).
- [ ] Re-label tiles for plain-English: "Tasks (company)" → "Company tasks · 11 open"; "active plans across products" → "in-flight product plans · 0 of 5"; "cross-cutting work logs" → "Sprints · 0 active · 3 shipped".
- [ ] Add a docs/sprint for this so Brain's tracker-index picks it up after merge.

## Out of scope (do separately)

- Studio mobile responsiveness — already a known gap.
- Workstream KPI alignment with sprint reconciler — surfaces here, but is its own follow-up.
- Brand/colour pass on the admin shell — see brand.mdc.

## Suggested execution

This is *not* a cost-bleed crisis. Don't dispatch yet. Open a fresh chat in **plan mode** with this file as context (`@docs/strategy/STUDIO_IA_REORG_BRIEF.md`), let plan mode produce the actual PR-by-PR decomposition, then dispatch cheap agents per the resulting plan.

Estimated PR count: 3-4
- PR A: tracker reconciler + Overview tile fixes
- PR B: nav reorg + label cleanup
- PR C: n8n / persona / workflow page decommission
- (PR D: optional Analytics bucket decision)

## Acceptance

- Every counter shown on `/admin` overview matches the count on its dedicated page (or has a deliberately documented difference).
- Nav has ≤ 12 items in 3 groups; every item maps to either an in-flight thing the founder can act on (Trackers), a piece of system truth (Architecture), or a running engine (Automation).
- All n8n persona scaffolding pages are either deleted or have a stated reason to exist.
