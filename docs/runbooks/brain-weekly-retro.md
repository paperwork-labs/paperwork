---
last_reviewed: 2026-05-02
doc_kind: runbook
owner: brain
tags:
  - brain
  - autonomy
  - retrospectives
category: runbooks
summary: How Brain computes, records, and recomputes weekly self-improvement retrospectives.
---

# Brain Weekly Retro

> **Category**: brain
> **Owner**: @brain
> **Last verified**: 2026-05-02
> **Status**: active

**TL;DR:** How Brain builds the weekly retro JSON from POS, PRs, incidents, and related data. Use when you recompute a week or interpret `weekly_retros.json`.

Brain's weekly retro is the Phase G2 self-improvement loop. It turns the last seven days of PR outcomes, POS movement, incidents, candidate workstreams, objective progress, and procedural memory changes into `apis/brain/data/weekly_retros.json`.

## What Goes Into The Retro

Each retro covers the seven-day window ending at `week_ending` and records:

- POS trajectory from `operating_score.json`: `current.total - history[-2].total` when at least two history entries exist.
- Merge outcomes from `pr_outcomes.json`: PRs with `merged_at` inside the window.
- Incidents from `incidents.json`: all incidents in the window, with auto-reverts counted separately.
- Workstream candidates from `workstream_candidates.json`: proposed and promoted candidates in the window.
- Procedural memory from `procedural_memory.yaml`: rules learned in the window and stale low-confidence rules.
- Objective progress from `docs/strategy/OBJECTIVES.yaml`: percent of dependent workstreams complete.

## Reading `rule_changes`

`rule_changes` describes what Brain learned or should reconsider:

- `added`: a procedural rule has `learned_at` inside the retro window.
- `revised`: reserved for future corpus-backed rule edits.
- `deprecated`: a low-confidence rule is older than 30 days and should be reviewed before Brain keeps using it.

WS-64 does not mutate `procedural_memory.yaml` automatically. It records recommended changes in the retro so the review loop can mature with more PR and incident data.

## Manual Recompute

Use the admin endpoint when a data file was backfilled or a weekly job misfired:

```bash
curl -X POST "$BRAIN_API_URL/api/v1/admin/weekly-retros/recompute" \
  -H "X-Brain-Secret: $BRAIN_API_SECRET"
```

The recompute writes the current UTC `week_ending` and replaces any existing retro with the same `week_ending`, so repeated recomputes do not create duplicates.

## Connection To Objectives And POS

POS explains whether Brain is making the company more operationally autonomous. Objectives explain whether that work is aimed at founder-written goals. The weekly retro connects both:

- `summary.pos_total_change` shows week-over-week POS movement.
- `objective_progress` shows how many workstreams tied to each objective are complete.
- `highlights` calls out top candidates, POS pillar threshold crossings, and revert-triggering incidents.

This gives Brain a weekly memory of what it shipped, what improved, what regressed, and which procedural rules should guide the next sprint.
