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

**Phase 1 (initial sprint scope):**

- 17 stale docs retired to `docs/archive/`, 70 retained docs got standardized YAML frontmatter, 1 collision rename (`docs/axiomfolio/KNOWLEDGE.md` → `DECISIONS.md`).
- `docs/philosophy/` folder bootstrapped with 7 immutable philosophy docs (Brain, Infra, Data, AI Model, Automation, Tax, Formation) + `README.md` index, all CODEOWNERS-locked to `@paperwork-labs/founders`.
- Three-tier tracker spine: company (`docs/TASKS.md`), per-product (`docs/<product>/plans/*`), cross-cutting sprints (`docs/sprints/*`). Generator: `scripts/generate_tracker_index.py` → `apps/studio/src/data/tracker-index.json` (deterministic, content-hash, CI-gated).
- Studio: `/admin/tasks`, `/admin/products`, `/admin/products/<slug>/plan`, rebuilt `/admin/sprints`, plus `TrackersRail` on `/admin` overview. Nav reorganized into Overview / Trackers / System.
- Brain: `apis/brain/app/schedulers/cfo_friday_digest.py` (Fridays 18:00 UTC, `persona_pin=cfo`, `#cfo` channel) + `/sprint`, `/tasks`, `/plan` Slack slash commands reading the same `tracker-index.json`.
- Make helpers: `make tracker-index`, `make tracker-check`, `make sprint-shipped PR=NNN`, `make plan-status`, `make docs-freshness`.
- CI gates: `tracker-index.yaml` (drift), `docs-freshness.yaml` (warn-only on `last_reviewed > 90d`), `runbook-template.yaml` (warn-only on missing required sections).
- Studio bug fixes shipped same sprint: `/admin/secrets` and `/admin/infrastructure` made `force-dynamic` (were silently statically prerendered, hiding live data); infra page extended to cover all frontends (Studio, AxiomFolio Vite, FileFree, LaunchFree, Distill) and the LaunchFree API. Sprint tracker UI rebuilt with featured-current-sprint card showing goal, outcome bullets, lessons, plans, and PR links.

**Phase 2 (extended same PR after re-scope):**

- Runbook template (`docs/RUNBOOK_TEMPLATE.md`) authored + linter (`scripts/check_runbook_template.py`) + CI gate. 7 runbooks restructured to template (`SECRETS`, AxiomFolio `ENCRYPTION_KEY_ROTATION`, `MARKET_DATA_RUNBOOK`, `PRODUCTION`, deploy + restart runbooks, `RENDER_REPOINT`); 5 docs reclassified `runbook → reference` (Dependabot, BillingVendorChecklist, BrainPRReview, EFinFiling, DriveSetup) since they are checklists, not incident response.
- 6 of 7 §6 duplicate-pair merges shipped (only `VMP-SUMMARY` deferred): AxiomFolio `AUDIT_FINDINGS`, `MARKET_DATA_FLOWS`, `ROADMAP`, `TASKS`, `ROTATION_BACKLOG`, and the 2026-04-22 medallion wave-0 handoff all folded into canonical targets with verbatim archive copies under `docs/archive/`.
- Crispness pass (TL;DR blocks + cross-links + stale-flag comments) on the 5 highest-traffic docs: `PRD`, `ARCHITECTURE`, `BRAIN_ARCHITECTURE` ↔ `BRAIN_PHILOSOPHY`, `INFRA` ↔ `INFRA_PHILOSOPHY`, `AI_MODEL_REGISTRY` ↔ `AI_MODEL_PHILOSOPHY`. Architecture/Philosophy pairs now consistently split "how" from "why / non-goals".
- `generate_axiomfolio_integration_doc.py` now emits frontmatter — fixes the only doc that was failing the freshness gate by being auto-generated without a `last_reviewed`.

**Phase 3 (architecture / DAG UX, infra honesty):**

- `/admin/architecture` redesigned: medallion (bronze / silver / gold) is now a **3-column primary row** at top; operational lanes (execution / frontend / platform / infra) are full-width swim-lanes below, each in a 2-/3-/4-col grid. Cards no longer get squashed at 22 nodes. Click still opens the right drawer.
- `/admin/workflows` Graph tab: every n8n DAG card is now click-to-zoom. Modal opens at 88vh, larger node radius, readable labels, ESC + click-outside to close, with deep-link to source on GitHub. Fixes the "I can't read the DAGs" feedback.
- `/admin/infrastructure` honesty fix: AxiomFolio API was reporting "Healthy (db: disconnected)" — Studio was reading a `db_connected` field that AxiomFolio's `/health` doesn't expose. Probe now shows `Healthy v<version>` and only appends `(db: connected/disconnected)` when the field is actually a boolean. Brain, FileFree, LaunchFree, AxiomFolio all benefit.
- F-6 added to [`docs/infra/RENDER_INVENTORY.md`](../infra/RENDER_INVENTORY.md) and a new section in [`RENDER_REPOINT.md`](../infra/RENDER_REPOINT.md): `brain-api`'s live Render config has `dockerContext: apis/brain` but the Dockerfile uses monorepo-root paths (`.cursor/rules/`, `apis/brain/requirements.txt`). Every push to `main` since the monorepo cutover has produced `build_failed` deploys silently — Brain is still serving from PR #140's commit. Fix is one operator click: clear Root Directory in `brain-api` settings.

## Tracks

| Track | Lane | What shipped |
|---|---|---|
| C1 | Docs Phase 1 | Frontmatter inject, 17 retirements, philosophy folder + 7 stubs |
| C2 | Docs Phase 2 — runbooks | `RUNBOOK_TEMPLATE.md`, linter, 7 restructured + 5 reclassified, CI gate |
| C3 | Docs Phase 2 — merges | 6/7 §6 duplicate pairs folded into canonical targets w/ verbatim archive |
| C4 | Docs Phase 2 — crispness | TL;DR + cross-links + stale flags on PRD / ARCHITECTURE / BRAIN / INFRA / AI_MODEL trios |
| E1 | Studio UX — architecture | Medallion-first 3-col layout, ops lanes below, no more squashed cards |
| E2 | Studio UX — DAG zoom | Click-to-zoom modal for every n8n graph (88vh, ESC-closable, labels readable) |
| E3 | Studio honesty — health probe | `db_connected` only shown when API exposes the field; otherwise `Healthy v<version>` |
| F-6 | Infra finding | `brain-api` dockerContext drift documented in `RENDER_INVENTORY.md` + `RENDER_REPOINT.md` runbook section |
| B | Trackers spine | TASKS.md, sprints/, plans/, generator + JSON, Studio pages |
| D | Brain wiring | CFO Friday digest, `/sprint` `/tasks` `/plan` slash commands |
| A | Studio fit-and-finish | Trackers nav, overview rail, force-dynamic on data pages, expanded infra probes, featured-sprint card |
| K | CI gates | tracker drift gate, docs freshness gate, runbook template gate |

## What we learned

- Server components that read env-injected data (`DATABASE_URL`, runtime probes) MUST mark `dynamic = "force-dynamic"`; otherwise Next.js prerenders them at build time and the user sees stale "not configured" forever. Caught only because the user noticed the Secrets page had silently regressed.
- A repo-native tracker beats Jira when the docs are already where work is happening — the cost was one Python script + one JSON output. CFO digest, Slack slash commands, and Studio pages all read the same file.
- Cheap-model parallel delegation (8 explore subagents) cleared the docs inventory in minutes; Sonnet then consolidated. Pattern reusable for every audit-style task.

## Follow-ups

- VMP-SUMMARY → VENTURE_MASTER_PLAN merge (the only §6 pair still pending — needs editor judgment on whether to fold or auto-regenerate from VMP via script).
- Auto-generate `docs/_index.yaml` from frontmatter so manual sync goes away (`c3c-index-generated`).
- AxiomFolio Next.js migration: 4/102 routes ported (`/`, `/system-status`, `/portfolio`, `/scanner` shells); plan target Q3, decommissions Render static hosting in favor of Vercel — see [docs/axiomfolio/plans/NEXTJS_MIGRATION_2026Q3.md](../axiomfolio/plans/NEXTJS_MIGRATION_2026Q3.md).
- Severity vocabulary review: existing 7 runbooks use yellow/red; if we want S0–S3 vocabulary across the company, that's a one-shot rename (defer until cross-product alignment).
- Promote `make runbook-check` to strict mode once we backfill the missing `docs/runbooks/HISTORICAL_IMPORT_IBKR.md` referenced from `GAPS_2026Q2`.
- `mark_sprint_shipped.py PR=142` once #142 merges to flip this sprint's status.
- **F-6 (operator)**: clear `brain-api` Root Directory in [Render dashboard](https://dashboard.render.com/web/srv-d74f3cmuk2gs73a4013g/settings) → next push to `main` deploys cleanly. Brain is still serving PR #140's code until this happens.
- **Studio enhancement (next sprint)**: surface Render deploy status (`live` / `build_failed`) per service inline in `/admin/infrastructure` so F-6-style silent build breakage cannot happen again. `RENDER_API_KEY` is already wired.
