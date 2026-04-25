---
owner: engineering
last_reviewed: 2026-04-23
doc_kind: reference
domain: company
status: active
---

# Sprints

Time-boxed cross-cutting work logs. Anything that touches multiple products / multiple personas / multiple infra layers belongs here. Per-product roadmaps live in `docs/axiomfolio/plans/`, `docs/filefree/plans/`, etc. The top-level company tracker is `docs/TASKS.md`.

## Schema

Each sprint is a single markdown file named `<TOPIC>_<YEAR>Q<QUARTER>.md` (e.g. `INFRA_AUTOMATION_HARDENING_2026Q2.md`). The first lines must be YAML frontmatter:

```yaml
---
owner: engineering
last_reviewed: 2026-04-23
doc_kind: sprint
domain: company
status: active   # active | shipped | paused | abandoned
sprint:
  start: 2026-04-01
  end: 2026-04-23
  duration_weeks: 4
  pr: 141
  ships: [studio, brain, axiomfolio, n8n]
  personas: [agent-ops, engineering, infra-ops, qa]
  budget_usd: 50
  budget_used_usd: 12.40
---
```

After frontmatter the body should follow this skeleton:

1. **Goal** — one sentence about what changed for the user / company
2. **Outcome** — bullets of what shipped (with PR links)
3. **Tracks** — what each lane delivered
4. **What we learned** — append-only lessons that will end up in `docs/KNOWLEDGE.md` if generalized
5. **Follow-ups** — open work, with owners

## Lifecycle

1. Open a sprint by creating the markdown file with `status: active` and a draft Goal.
2. Update during the sprint by appending; never rewrite history.
3. When the PR merges, flip `status: shipped`, fill `pr: <num>`, and let `scripts/generate_tracker_index.py` pick it up on next CI run.
4. If a sprint dies, set `status: abandoned` and write a short post-mortem in §4.

## How agents read this

`scripts/generate_tracker_index.py` walks this folder and emits `apps/studio/src/data/tracker-index.json`, which `/admin/sprints` and `/admin/tasks` render. The Brain `cfo` and `agent-ops` personas read the same JSON when answering "what shipped this week?"

## Index

- [`INFRA_AUTOMATION_HARDENING_2026Q2.md`](./INFRA_AUTOMATION_HARDENING_2026Q2.md) — 2026-04-01 → 2026-04-23, shipped (#141)
