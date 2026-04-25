---
owner: agent-ops
last_reviewed: 2026-04-23
doc_kind: audit
domain: company
status: active
---

# Docs Streamline 2026 Q2 — Audit & Migration

**Sprint:** Infra & Automation Hardening (Buffer)
**Driver:** Two-tier tracker work needs every retained doc to carry standardized frontmatter so `scripts/generate_tracker_index.py` can parse status, owner, and freshness from a single schema.

**Method:** 8-lane cheap-model fan-out (composer-2-fast) over 100% of `docs/`, then human (Sonnet) consolidation. Every markdown file in `docs/` (102 total) was classified into one of five buckets: canonical / merge_into / retire / split / unchanged.

---

## Bottom line

| Bucket | Count | Action |
|---|---|---|
| canonical (current, load-bearing — keep) | 60 | Inject standard frontmatter |
| unchanged (low-priority, archive sanity passed) | 12 | Inject standard frontmatter |
| retire (move to `docs/archive/`) | 17 | `git mv` via `scripts/migrate_docs.sh` |
| merge_into (content folds into another doc) | 7 | Deferred — needs content extraction (manual review) |
| split (too large/multi-purpose) | 5 | Deferred — needs editor judgment |
| collisions / renames | 1 | `docs/axiomfolio/KNOWLEDGE.md` → `DECISIONS.md` |
| philosophy stubs to author | 7 | New files in `docs/philosophy/` |
| **Total markdown files audited** | **102** | |

Retirements + collision rename + frontmatter + philosophy bootstrap ship immediately in this PR. Merges and splits ship in a follow-up so reviewers can scrutinize the content extractions one at a time without drowning in mv noise.

---

## Architecture ↔ Philosophy gap matrix

Every domain should have a paired (Architecture = mutable "how", Philosophy = immutable "why / what we won't do") set of canonical docs. The L8 cross-cut audit found these gaps:

| Domain | Architecture (mutable) | Philosophy (immutable) | Gap | Stub created |
|---|---|---|---|---|
| company | `docs/ARCHITECTURE.md` | `docs/VENTURE_MASTER_PLAN.md` | none | — |
| brain | `docs/BRAIN_ARCHITECTURE.md` | **missing** | philosophy | `docs/philosophy/BRAIN_PHILOSOPHY.md` |
| infra | `docs/INFRA.md` | **missing** | philosophy | `docs/philosophy/INFRA_PHILOSOPHY.md` |
| data | `docs/axiomfolio/MARKET_DATA.md` | **missing** | philosophy | `docs/philosophy/DATA_PHILOSOPHY.md` |
| trading | `docs/axiomfolio/TRADING.md` | `docs/axiomfolio/TRADING_PRINCIPLES.md` | none | — (linked from `docs/philosophy/README.md`) |
| tax | **missing** | **missing** | both | `docs/philosophy/TAX_PHILOSOPHY.md` (architecture deferred — FileFree PRD covers most, see Phase 1 of streamline follow-up) |
| formation | **missing** | **missing** | both | `docs/philosophy/FORMATION_PHILOSOPHY.md` (architecture deferred — LaunchFree PRD covers most) |
| personas | `docs/BRAIN_PERSONAS.md` | `docs/GROUND_TRUTH.md` (de-facto) | partial | flagged — `GROUND_TRUTH` is verifiable claims log, not a philosophy doc; needs explicit `PERSONAS_PHILOSOPHY.md` later |
| automation | `docs/DEPENDABOT.md` + `docs/BRAIN_PR_REVIEW.md` | **missing** | philosophy | `docs/philosophy/AUTOMATION_PHILOSOPHY.md` |
| design | `docs/axiomfolio/DESIGN_SYSTEM.md` | **missing** | philosophy | flagged — defer until Studio + AxiomFolio + FileFree design systems are unified (active work) |
| ai-models | `docs/AI_MODEL_REGISTRY.md` | **missing** | philosophy | `docs/philosophy/AI_MODEL_PHILOSOPHY.md` |

**Net:** 7 new philosophy stubs ship now (BRAIN, INFRA, DATA, TAX, FORMATION, AUTOMATION, AI_MODEL). 2 deferred (PERSONAS, DESIGN) with rationale captured.

---

## Duplicates & collisions found

| Pair | Action | Rationale |
|---|---|---|
| `docs/AXIOMFOLIO_INTEGRATION.md` vs `docs/AXIOMFOLIO_INTEGRATION.generated.md` | Retire `.md` | `.generated.md` is CI-guarded YAML-driven contract; hand-written one drifts |
| `docs/AXIOMFOLIO_HANDOFF.md` vs `docs/axiomfolio/PAPERWORK_HANDOFF.md` | Retire both; the migration is done | Both are point-in-time; integration contract = `.generated.md` |
| `docs/axiomfolio/RENDER_INVENTORY.md` vs `docs/infra/RENDER_INVENTORY.md` | Retire AxiomFolio copy | Self-deprecates; `docs/infra/` is monorepo SoT |
| `docs/KNOWLEDGE.md` vs `docs/axiomfolio/KNOWLEDGE.md` | Rename AxiomFolio to `DECISIONS.md` | Same filename, different audiences (org memory vs ADR log) — collision |
| `docs/VENTURE_MASTER_PLAN.md` vs `docs/VMP-SUMMARY.md` | Defer merge | Summary is read-only excerpt for cheap models; either regenerate from VMP via script or deep-link only |

---

## Phase 1 (this PR) — retirements

Move to `docs/archive/` (17 files, all stale or superseded):

**Root-level**
- `docs/AXIOMFOLIO_HANDOFF.md` — already retired stub; integration contract lives in `.generated.md`
- `docs/AXIOMFOLIO_INTEGRATION.md` — superseded by `.generated.md`
- `docs/PHASE2-COMPOSER-HANDOFFS.md` — ephemeral Composer prompts; superseded

**AxiomFolio**
- `docs/axiomfolio/RENDER_INVENTORY.md` — self-deprecates to `docs/infra/RENDER_INVENTORY.md`
- `docs/axiomfolio/PAPERWORK_HANDOFF.md` — pre-monorepo handoff; integration contract = `.generated.md`

**AxiomFolio plans / agent-automation (5)**
- `docs/axiomfolio/plans/agent-automation/00-repo-move.md` — Phase 0 done
- `docs/axiomfolio/plans/agent-automation/00-repo-move-preflight-snapshot.md` — pre-transfer snapshot
- `docs/axiomfolio/plans/agent-automation/01-axiomfolio-side.md` — superseded by Path A pivot
- `docs/axiomfolio/plans/agent-automation/02-paperwork-brain-side.md` — superseded by Path A pivot
- `docs/axiomfolio/plans/agent-automation/HANDOFF.md` — stale handoff
- `docs/axiomfolio/plans/agent-automation/preflight-data/README.md` — one-time GitHub snapshot index

**AxiomFolio handoffs (4)** — point-in-time session handoffs, not evergreen
- `docs/axiomfolio/handoffs/2026-04-20-midnight-merge-storm.md`
- `docs/axiomfolio/handoffs/2026-04-21-g22-shipped-next-g23.md`
- `docs/axiomfolio/handoffs/2026-04-21-plan-reality-check.md`
- `docs/axiomfolio/handoffs/STAGE_QUALITY_DIAGNOSIS_2026Q2.md`

**Note on `2026-04-22-medallion-wave-0-stage-setting.md`:** Decisions are folded into `MEDALLION_AUDIT_2026Q2.md` and `PLATFORM_REVIEW_2026Q2.md` (Wave 0 handoff section, 2026-04-24); the source lives in `docs/archive/2026-04-22-medallion-wave-0-stage-setting.md`.

**Design system (1)**
- `docs/axiomfolio/design-system/pages/intelligence.md` — page renamed to `MarketIntelligence` in code; spec orphaned

---

## Phase 1 (this PR) — collision renames

| From | To | Why |
|---|---|---|
| `docs/axiomfolio/KNOWLEDGE.md` | `docs/axiomfolio/DECISIONS.md` | Collides with `docs/KNOWLEDGE.md` (org memory). AxiomFolio version is an append-only ADR log (D-IDs) — `DECISIONS` is the right name. Update internal cross-refs. |

---

## Phase 1 (this PR) — frontmatter injection

Every retained doc (canonical + unchanged = 72 files) gets standard YAML frontmatter:

```yaml
---
owner: <persona-slug>
last_reviewed: <YYYY-MM-DD>
doc_kind: <architecture|philosophy|runbook|reference|plan|handoff|generated|spec|audit|template>
domain: <company|brain|infra|data|trading|tax|formation|personas|automation|design|ai-models|other>
status: <active|deprecated|generated>
---
```

Idempotent injector script: `scripts/inject_doc_frontmatter.py`. If frontmatter already present, merge missing keys without overwriting existing values. Source-of-truth for owner/domain/doc_kind = the audit JSON in `docs/generated/docs-streamline-2026q2-decisions.json` (also created by this PR).

---

## Phase 1 (this PR) — philosophy folder bootstrap

```
docs/philosophy/
  README.md                    # Index of every philosophy doc across the repo
  BRAIN_PHILOSOPHY.md          # NEW — Brain safety/trust boundaries, refusal rules
  INFRA_PHILOSOPHY.md          # NEW — tier-1/2 placement, when not to add services
  DATA_PHILOSOPHY.md           # NEW — medallion iron laws, PII retention, SoT hierarchy
  AI_MODEL_PHILOSOPHY.md       # NEW — model selection rules, when to chain, cost caps
  AUTOMATION_PHILOSOPHY.md     # NEW — when automation stops, human-merge requirements
  TAX_PHILOSOPHY.md            # NEW — non-negotiable compliance, OCR rules, what we won't claim
  FORMATION_PHILOSOPHY.md      # NEW — disclaimer rules, what LaunchFree won't auto-file
```

Plus: `CODEOWNERS` lock on `docs/philosophy/**` requiring human review (founder + agent-ops persona for any future change). These docs are intentionally low-churn.

---

## Phase 2 (follow-up PR — out of scope here)

**Merges — status:**
- ⏳ Pending: `docs/VMP-SUMMARY.md` → fold into `docs/VENTURE_MASTER_PLAN.md` (or auto-regenerate via script)
- ✅ Shipped 2026-04-24: AxiomFolio audit findings folded into [`docs/axiomfolio/DECISIONS.md`](axiomfolio/DECISIONS.md); verbatim archive at `docs/archive/AUDIT_FINDINGS_2026-04.md`.
- ✅ Shipped 2026-04-24: AxiomFolio market-data flows folded into [`docs/axiomfolio/MARKET_DATA.md`](axiomfolio/MARKET_DATA.md); verbatim archive at `docs/archive/MARKET_DATA_FLOWS.md`.
- ✅ Shipped 2026-04-24: AxiomFolio section roadmap merged into [`docs/axiomfolio/plans/MASTER_PLAN_2026.md`](axiomfolio/plans/MASTER_PLAN_2026.md); verbatim archive at `docs/archive/AXIOMFOLIO_ROADMAP.md`.
- ✅ Shipped 2026-04-24: AxiomFolio rotation backlog folded into [`docs/axiomfolio/PRODUCTION.md`](axiomfolio/PRODUCTION.md); verbatim archive at `docs/archive/ROTATION_BACKLOG.md`.
- ✅ Shipped 2026-04-24: AxiomFolio sprint `TASKS` open items merged into [`docs/axiomfolio/plans/MASTER_PLAN_2026.md`](axiomfolio/plans/MASTER_PLAN_2026.md); verbatim archive at `docs/archive/AXIOMFOLIO_TASKS.md`.
- ✅ Shipped 2026-04-24: medallion wave-0 stage-setting handoff decisions extracted into `MEDALLION_AUDIT_2026Q2.md` + `PLATFORM_REVIEW_2026Q2.md`; verbatim archive at `docs/archive/2026-04-22-medallion-wave-0-stage-setting.md`.

**Splits (need editor judgment):**
- `docs/BRAIN_ARCHITECTURE.md` — sharded by D-ID grouping for navigation
- `docs/TASKS.md` — replaced by `/admin/tasks` page reading frontmatter; consider thinning
- `docs/PRD.md` — split per-product (FileFree, LaunchFree, Distill, Brain) with shared appendix
- `docs/axiomfolio/RENDER_MIGRATION_PLAN.md` — split inventory facts to `docs/infra/RENDER_INVENTORY.md`, cutover steps to `docs/infra/RENDER_REPOINT.md`

**Architecture stubs deferred:**
- `docs/architecture/TAX_ARCHITECTURE.md` — pending FileFree PRD split
- `docs/architecture/FORMATION_ARCHITECTURE.md` — pending LaunchFree PRD split

---

## Coverage check

| Lane | Files audited | Files in tree (gold) | Coverage |
|---|---|---|---|
| L1 root | 27 | 27 | 100% |
| L2 axiomfolio core | 31 | 31 | 100% |
| L3 axiomfolio plans | 19 | 19 | 100% |
| L4 handoffs/runbooks/specs | 9 | 9 | 100% |
| L5 design-system | 5 | 5 | 100% |
| L6 infra/templates | 4 | 4 | 100% |
| L7 archive (sanity) | 8 | 8 | 100% |
| L8 cross-cut (subset of L1+L2+L6) | 60 | — | dedup pass only |
| **Total** | **102** | **102** | **100%** |

Generated coverage manifest: `docs/generated/docs-streamline-2026q2-coverage.txt`. CI gate `scripts/check_doc_coverage.py` (added in this PR) fails if `docs/**/*.md` count diverges from manifest without an explicit re-run of the streamline.

---

## Per-doc decisions

The full per-doc decision matrix is committed as machine-readable JSON at:

`docs/generated/docs-streamline-2026q2-decisions.json`

Each entry carries: `path`, `classify`, `merge_target`, `rationale`, `owner`, `domain`, `doc_kind`, `last_meaningful_change`, `summary`. The `inject_doc_frontmatter.py` script consumes this JSON to produce the standard frontmatter on every retained doc.

---

## What changes in CI after this PR

1. `scripts/check_docs_index.py` — already passes after Phase 1 mv operations
2. `scripts/check_doc_freshness.py` (NEW) — fails when a non-philosophy retained doc has `last_reviewed` more than 90 days old without an `owner` ack file in `docs/generated/owner-acks.yaml`
3. `scripts/generate_docs_index.py` (NEW) — converts hand-maintained `docs/_index.yaml` to auto-generated from frontmatter; CI guard added
4. `scripts/check_doc_coverage.py` (NEW) — guards 100% coverage manifest

---

## Owners

| Doc family | Owner persona | Backup |
|---|---|---|
| Brain (architecture + philosophy) | `agent-ops` | `engineering` |
| Infra | `infra-ops` | `engineering` |
| Data | `engineering` | `agent-ops` |
| AxiomFolio (trading) | `trading` | `engineering` |
| Tax / FileFree | `cpa` | `tax-domain` |
| Formation / LaunchFree | `legal` | `engineering` |
| Personas | `agent-ops` | `qa` |
| Design | `ux` | `engineering` |
| AI models | `agent-ops` | `cfo` (cost) |
| Company strategy | `strategy` | `cfo` |

CODEOWNERS file updated in this PR to enforce the above on PR review.
