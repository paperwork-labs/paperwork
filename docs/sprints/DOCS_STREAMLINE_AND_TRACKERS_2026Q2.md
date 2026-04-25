---
owner: engineering
last_reviewed: 2026-04-25
doc_kind: sprint
domain: company
status: active
sprint:
  start: 2026-04-24
  end: 2026-04-26
  duration_weeks: 1
  pr: 142
  prs: [142, 143]
  ships: [studio, docs, brain, infra]
  personas: [agent-ops, engineering, cfo, qa, infra-ops]
  plans:
    - docs/DOCS_STREAMLINE_2026Q2.md
    - docs/sprints/README.md
---

# Docs Streamline + Trackers Spine — 2026 Q2

**Sprint window**: 2026-04-24 → 2026-04-26 (~3 days, mini-sprint)
**Status**: active — #142 merged, follow-up #143 in flight (Render consolidation, autogen docs index, sprint living tracker)
**Plan**: [DOCS_STREAMLINE_2026Q2.md](../DOCS_STREAMLINE_2026Q2.md)
**PRs**: [#142](https://github.com/paperwork-labs/paperwork/pull/142), [#143](https://github.com/paperwork-labs/paperwork/pull/143)

## Goal

Land Phase 1 of the docs streamline, give the company a repo-native long-term tracker (no Jira / Notion), and wire Brain into both so a CFO digest and Slack slash commands work off the same JSON the UI reads.

## Outcome

**Phase 5 (PR #144 — Vercel webhook redundancy + sprint UI brief + Brain learns lessons):**

- shipped 2026-04-25: `launchfree-api` block in root `render.yaml` commented out (not deleted) with the rationale inline — frontend at `apps/launchfree/` still renders mocks, so paying $7/mo for an empty backend doesn't earn its keep yet. Re-enable workflow documented as a 10-line revert PR. F-2 closed with this decision. (PR #144)
- shipped 2026-04-25: `.github/workflows/vercel-promote-on-merge.yaml` — redundant trigger that promotes the PR's preview deployment to production after merge to `main`, idempotent (exits clean if Vercel webhook fired correctly). No rebuild, no build-credit consumption — only flips the alias via `POST /v10/projects/{id}/promote/{deploymentId}`. Two consecutive webhook misses (#142, #143) are the pattern this fixes. Setup runbook: `docs/infra/VERCEL_AUTO_PROMOTE.md`. (PR #144)
- shipped 2026-04-25: Sprint UI — every shipped/active sprint card in `/admin/sprints` is now click-to-expand with the same plan/PRs/source/living-tracker/lessons brief the featured card uses. Collapsed view shows title + dates + shipped/pending counts + lesson count + truncated goal + tags; expanding reveals the full brief. Replaces the previous "tag soup" rail bottom that was hard to read. Chevron animates -90° → 0° on open. (PR #144)
- shipped 2026-04-25: Brain ingests sprint `## What we learned` bullets as memory episodes (`source="sprint:lessons"`, `source_ref="<slug>#<sha1>"`) — searchable via the same hybrid retrieval as `seed:docs`. New `/admin/seed-lessons` endpoint, `scripts/ingest_sprint_lessons.py` CLI, `app/schedulers/sprint_lessons.py` (every 6h), and `.github/workflows/sprint-lessons-ingest.yaml` (synchronous on `docs/sprints/**` push to main). Idempotent — re-runs only insert new bullets. 7 lessons across 2 sprints land on first deploy. (PR #144)

**Phase 4 (post-#142 follow-up — PR #143):**

- shipped 2026-04-25: F-1 + F-4 — consolidated `apis/axiomfolio/render.yaml` into root `render.yaml` so all 9 Paperwork-managed Render services (FileFree API, LaunchFree API, Brain API, AxiomFolio API + 2 workers + frontend, AxiomFolio Redis, AxiomFolio DB) live in a single Blueprint. Old subtree blueprint neutered with retirement comment + dashboard-association steps. (PR #143)
- shipped 2026-04-25: Studio docs page — wired `remark-gfm` into `<ReactMarkdown>` so GitHub-flavored tables, strikethrough, task lists, and autolinks render. Also extended `prose-*` classes to style the `<table>`/`<thead>`/`<th>`/`<td>` zinc theme (`/admin/docs/[slug]`). Fixes "tables don't render in Studio docs". (PR #143)
- shipped 2026-04-25: F-2 — original PR #143 dropped the `launchfree-api` block on the assumption it was a stub; it isn't (real FastAPI app at `apis/launchfree/`, frontend at launchfree.ai). Restored the entry plus an inline rationale comment so future readers know the service is intentionally declared in the Blueprint pending provisioning. (PR #143)
- shipped 2026-04-25: F-6 runbook field-name correction — `RENDER_REPOINT.md` Path A now distinguishes Render's two separate Build & Deploy fields (Root Directory vs Docker Build Context Directory). Operator confirmed clearing the latter resolved `brain-api` build failures; Brain now serves the #142 image with persona registry, `/pr-sweep`, `/pr-merge-sweep`, `/pr-review`, `/webhooks/github`, and `/webhooks/slack/command` endpoints all live and admin-gated. (PR #143)
- shipped 2026-04-25: VMP-SUMMARY → VENTURE_MASTER_PLAN TL;DR merge (final §6 pair). Compact summary now lives at the top of the canonical plan; verbatim copy archived at `docs/archive/VMP-SUMMARY-2026-03-18.md`. (PR #143)
- shipped 2026-04-25: Auto-generate `docs/_index.yaml` from frontmatter (`c3c-index-generated`) — `scripts/generate_docs_index.py` walks `docs/**/*.md`, derives slug/title/summary/tags/owners/category from frontmatter, and treats the existing `_index.yaml` as an override registry (preserves manual entries, drops stale ones, generates new). New CI gate: `python scripts/generate_docs_index.py --check` runs in `docs-index.yaml` workflow. (PR #143)
- shipped 2026-04-25: Sprint UI — living shipped-vs-pending tracker. `/admin/sprints` now combines `outcome_bullets` and `followups` into one chronologically-sorted list with status icons (CheckCircle2 for shipped, Clock3 for pending), shipped-date badges, and PR deep-links. Sprint rail cards show inline shipped/pending counts. Replaces the earlier "Outcome" + separate "Follow-ups" split — one section, status-aware, agent-readable. (PR #143)
- shipped 2026-04-25: `scripts/sprint_promote_followup.py` — CLI helper to promote a follow-up bullet to the Outcome section with `shipped YYYY-MM-DD:` prefix and optional `(PR #N)` reference. Supports `--dry-run`, `--all`, `--pr`, `--date`. Pairs with the living tracker UI so sprint maintenance is one command per merged PR. (PR #143)

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
- All 7 §6 duplicate-pair merges shipped: AxiomFolio `AUDIT_FINDINGS`, `MARKET_DATA_FLOWS`, `ROADMAP`, `TASKS`, `ROTATION_BACKLOG`, the 2026-04-22 medallion wave-0 handoff, and (2026-04-25) `VMP-SUMMARY` → `VENTURE_MASTER_PLAN` TL;DR — all folded into canonical targets with verbatim archive copies under `docs/archive/`.
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
- Two missed Vercel webhooks in 24 hours is a pattern, not a flake. The right fix is a redundant trigger at the merge layer (GH Actions → `POST /v10/projects/{id}/promote/{id}`), not switching webhook types — promoting a preview deployment is alias-only, doesn't burn a build slot, and is idempotent if the original webhook fired correctly. Cheaper than abandoning the GitHub App's PR-comment UX.
- Sprint "lessons learned" deserve to be first-class memory, not just markdown. Lifting them into Brain episodes (`source="sprint:lessons"`, SHA1-keyed for idempotency) means the same hybrid retrieval that surfaces docs for chat questions will surface them too — without anyone having to remember which sprint a lesson lived in.

## Follow-ups

- shipped 2026-04-25: **F-1 (operator, single click)** completed — all AxiomFolio + brain-api + filefree-api services now associated with the consolidated root `render.yaml` Blueprint via Render Dashboard's "New Blueprint → Associate existing services" flow. (PR #143)
- shipped 2026-04-25: **Vercel — Studio prod redeploy of `f0255542`** — preview build for #143 manually promoted via `vercel promote` (alias-only, no build credit consumed). Stale `/admin/secrets` prerender resolved. The root cause (Vercel webhook miss) is now addressed by the redundant trigger in PR #144's `vercel-promote-on-merge.yaml`. (PR #143 + #144)
- shipped 2026-04-25: **F-2 launchfree-api decision** — commented out (not deleted) in `render.yaml` with re-enable workflow documented inline. Frontend renders mocks, $7/mo for empty backend defers. (PR #144)
- **F-3 env var naming**: reconcile `VERCEL_API_TOKEN` (root `render.yaml`) vs `VERCEL_TOKEN` (Studio) — pick one and update both ends.
- **F-5 `brain-api` `GITHUB_WEBHOOK_SECRET`**: declare with `sync: false` in `render.yaml`, then operator pastes the value once. Until then GitHub webhooks land but skip signature verification.
- **Studio `/admin/infrastructure` six-service health**: extend probes so AxiomFolio API + 2 workers + frontend + Redis + DB all show green alongside FileFree and Brain. `RENDER_API_KEY` already wired — pull `live`/`build_failed` per service so F-6-style silent breakage is impossible.
- AxiomFolio Next.js migration: 4/102 routes ported (`/`, `/system-status`, `/portfolio`, `/scanner` shells); plan target Q3, decommissions Render static hosting in favor of Vercel — see [docs/axiomfolio/plans/NEXTJS_MIGRATION_2026Q3.md](../axiomfolio/plans/NEXTJS_MIGRATION_2026Q3.md).
- Severity vocabulary review: existing 7 runbooks use yellow/red; if we want S0–S3 vocabulary across the company, that's a one-shot rename (defer until cross-product alignment).
- Promote `make runbook-check` to strict mode once we backfill the missing `docs/runbooks/HISTORICAL_IMPORT_IBKR.md` referenced from `GAPS_2026Q2`.
- `make sprint-shipped PR=143` once #143 merges to flip this sprint's status to `shipped` and bake the date.
