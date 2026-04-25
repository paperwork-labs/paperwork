---
owner: engineering
last_reviewed: 2026-04-24
doc_kind: sprint
domain: company
status: active
sprint:
  start: 2026-04-24
  end: 2026-04-26
  duration_weeks: 1
  pr: 142
  prs: [142]
  ships: [studio, docs, brain]
  personas: [agent-ops, engineering, cfo, qa]
  plans:
    - docs/DOCS_STREAMLINE_2026Q2.md
    - docs/sprints/README.md
---

# Docs Streamline + Trackers Spine — 2026 Q2

**Sprint window**: 2026-04-24 → 2026-04-26 (~3 days, mini-sprint)
**Status**: active — PR #142 open, GH Actions green, awaiting merge
**Plan**: [DOCS_STREAMLINE_2026Q2.md](../DOCS_STREAMLINE_2026Q2.md)
**PRs**: [#142](https://github.com/paperwork-labs/paperwork/pull/142)

## Goal

Land Phase 1 of the docs streamline, give the company a repo-native long-term tracker (no Jira / Notion), and wire Brain into both so a CFO digest and Slack slash commands work off the same JSON the UI reads.

## Outcome

- 17 stale docs retired to `docs/archive/`, 70 retained docs got standardized YAML frontmatter, 1 collision rename (`docs/axiomfolio/KNOWLEDGE.md` → `DECISIONS.md`).
- `docs/philosophy/` folder bootstrapped with 7 immutable philosophy docs (Brain, Infra, Data, AI Model, Automation, Tax, Formation) + `README.md` index, all CODEOWNERS-locked to `@paperwork-labs/founders`.
- Three-tier tracker spine: company (`docs/TASKS.md`), per-product (`docs/<product>/plans/*`), cross-cutting sprints (`docs/sprints/*`). Generator: `scripts/generate_tracker_index.py` → `apps/studio/src/data/tracker-index.json` (deterministic, content-hash, CI-gated).
- Studio: `/admin/tasks`, `/admin/products`, `/admin/products/<slug>/plan`, rebuilt `/admin/sprints`, plus `TrackersRail` on `/admin` overview. Nav reorganized into Overview / Trackers / System.
- Brain: `apis/brain/app/schedulers/cfo_friday_digest.py` (Fridays 18:00 UTC, `persona_pin=cfo`, `#cfo` channel) + `/sprint`, `/tasks`, `/plan` Slack slash commands reading the same `tracker-index.json`.
- Make helpers: `make tracker-index`, `make tracker-check`, `make sprint-shipped PR=NNN`, `make plan-status`, `make docs-freshness`.
- CI gates: `tracker-index.yaml` (drift), `docs-freshness.yaml` (warn-only on `last_reviewed > 90d`).
- Studio bug fixes shipped same sprint: `/admin/secrets` and `/admin/infrastructure` made `force-dynamic` (were silently statically prerendered, hiding live data); infra page extended to cover all frontends (Studio, AxiomFolio Vite, FileFree, LaunchFree, Distill) and the LaunchFree API.

## Tracks

| Track | Lane | What shipped |
|---|---|---|
| C | Docs Phase 1 | Frontmatter inject, 17 retirements, philosophy folder + 7 stubs |
| B | Trackers spine | TASKS.md, sprints/, plans/, generator + JSON, Studio pages |
| D | Brain wiring | CFO Friday digest, `/sprint` `/tasks` `/plan` slash commands |
| A | Studio fit-and-finish | Trackers nav, overview rail, force-dynamic on data pages |
| K | CI gates | tracker drift gate, docs freshness gate |

## What we learned

- Server components that read env-injected data (`DATABASE_URL`, runtime probes) MUST mark `dynamic = "force-dynamic"`; otherwise Next.js prerenders them at build time and the user sees stale "not configured" forever. Caught only because the user noticed the Secrets page had silently regressed.
- A repo-native tracker beats Jira when the docs are already where work is happening — the cost was one Python script + one JSON output. CFO digest, Slack slash commands, and Studio pages all read the same file.
- Cheap-model parallel delegation (8 explore subagents) cleared the docs inventory in minutes; Sonnet then consolidated. Pattern reusable for every audit-style task.

## Follow-ups

- Phase 2 docs: merge duplicate pairs called out in `DOCS_STREAMLINE_2026Q2.md` §6, runbook templating pass.
- Auto-generate `docs/_index.yaml` from frontmatter so manual sync goes away (`c3c-index-generated`).
- `mark_sprint_shipped.py PR=142` once #142 merges to flip this sprint's status.
