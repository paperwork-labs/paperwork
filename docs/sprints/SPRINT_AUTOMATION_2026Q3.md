---
title: Sprint Automation (2026 Q3)
owner: engineering
last_reviewed: 2026-04-26
doc_kind: sprint
domain: company
status: in_progress
sprint:
  start: 2026-04-26
  end: 2026-06-30
  duration_weeks: 10
opened: 2026-04-26
target_close: 2026-06-30
related_prs: []
---

# Sprint Automation (2026 Q3)

**Sprint window**: 2026-04-26 → 2026-06-30 (Q3 umbrella for automation loops)
**Status**: in_progress — first slice is Brain-owned **sprint auto-logger** (merged PRs → `docs/sprints/*.md` via batched bot PRs).

## Goal

Close the **“Studio shows sprint progress automatically”** loop: Brain appends shipped lines to sprint markdown under `## Outcome`, Studio’s living tracker reads the same files, and the founder sees sprint cards move without hand-copying PR titles.

Design note: **single source of truth stays in git** (markdown + `related_prs`), not a shadow DB projection, so Studio and operators never drift from what’s on `main`.

## Acceptance criteria

- [ ] At least **three** future merged PRs are auto-logged into the correct `docs/sprints/*.md` files (body `Sprint:` line and/or `sprint:*` label).
- [ ] **No duplicate** outcome bullets for the same PR# across **one week** of ticks (idempotent re-runs).
- [ ] `agent_scheduler_runs` shows consistent `success` rows for `job_id = sprint_auto_logger` after `BRAIN_OWNS_SPRINT_AUTO_LOGGER=true` in prod.

## Outcome

- _Tracking — Brain `sprint_auto_logger` + operator runbook_
- shipped 2026-04-26: **SPRINT_AUTO_LOGGER** — Brain APScheduler job (`*/15 * * * *` UTC) batches merged PRs with explicit sprint markers into one bot PR that updates `## Outcome` and `related_prs`; gated by `BRAIN_OWNS_SPRINT_AUTO_LOGGER`. Code: `apis/brain/app/schedulers/sprint_auto_logger.py`, CLI: `python -m app.cli.sprint_auto_logger_cli`. Runbook: [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md).

## What we learned

- _(empty — fill in as the sprint runs)_

## Tracker

- [ ] Enable `BRAIN_OWNS_SPRINT_AUTO_LOGGER=true` on `brain-api` after one clean staging window; confirm no duplicate bot PRs.
- [ ] Document label/body convention for PR authors (`Sprint: docs/sprints/…md` or `sprint:STEM`).
- [ ] After three auto-logged PRs, mark acceptance criteria checkboxes above and link PR numbers in `related_prs`.
