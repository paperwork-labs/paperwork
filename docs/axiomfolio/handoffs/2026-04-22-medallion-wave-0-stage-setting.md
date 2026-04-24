# Session Handoff — 2026-04-22 — Medallion "Wave 0" stage-setting

> **For the next chat (Claude Opus, GPT, or any successor — human or agent)**: read this file end-to-end before doing anything in `app/services/`. It captures *why* we're inserting a Wave 0 ahead of the published 16-wave roadmap, what's actually true on disk vs what the docs claim, and the exact four-phase migration plan with reversibility notes for each phase. The previous Opus session built up this thesis through a meta-architectural audit; do not re-litigate it without reading the receipts in §3.

---

## TL;DR — the 60-second pickup

- **PR #476** (`docs/platform-mckinsey-review-2026q2`) is open with three planning docs + D144 + D145. **Do not merge yet.** It's the strategic spine for everything below; Wave 0 is the first execution wave that follows.
- **Meta finding**: we are ~30% aligned with the medallion / "three pillars decoupled" story we're publishing. Bronze exists as a folder (3/6 brokers in it). Silver does not exist as a folder at all (0 files, 0 imports). Gold exists with 7 native files but ~30 more gold-shaped files still live in `strategy/`, `picks/`, `execution/`. The system-status DAG happens to lay out as bronze→silver→gold but has zero medallion labels.
- **Founder ask**: "kinda weak dont you think, architecturally as well as when marketing! we say medallion and other things, are we following?" The honest answer was no.
- **Proposed**: insert a **Wave 0 — Medallion stage-setting** before W1 (safety envelope) instead of running medallion as parallel W16 over 6 weeks. Compresses to **6–9 days focused work + 2-week passive shadow-import bake**.
- **Founder asked for the plan in detail with no implementation yet**. This handoff captures that plan plus the four pre-execution decisions still needed before any code lands.
- **Decision gates not yet answered (block execution)**:
  1. Go/no-go on Wave 0 before W1.
  2. Single atomic migration PR, or split silver-first / bronze+gold-second (recommended split).
  3. Acknowledge `execution/` as a fourth medallion layer (recommended yes).
  4. 3-day freeze window for Phase 0.C — when?
- **Do NOT touch any DANGER ZONE file** (per `.cursor/rules/protected-regions.mdc`) without explicit founder approval. Wave 0 moves three of them (`indicator_engine.py`, `stage_classifier.py`, `regime_engine.py`) — see §6.2.

---

## 1. Why this handoff exists

The Q2 2026 platform review (PR #476) introduced a Chapter 1.8 ("Medallion architecture + data-warehouse discipline") and a Wave 16 in the 16-wave execution roadmap. The founder pushed back on a meta question:

> "we say medallion and other things, are we following? we have a dag in system status — all good there too — we aligned? meta question!"

The previous Opus session ran a code audit and found the docs are ahead of the code. The honest version of "are we aligned?" is: directionally yes, mechanically no. This handoff captures the audit, the proposed compressed remediation, and the open decisions so the next chat can either execute or push back without re-doing the audit.

---

## 2. What's already shipped on PR #476 (do not redo)

Three commits on branch `docs/platform-mckinsey-review-2026q2`:

| SHA | What |
|---|---|
| `ccd78f0d` | Platform McKinsey review + broker coverage tracker + sync completeness W8 spec (3 new docs, ~1530 lines) |
| `6bf749c4` | D144 platform review commitments + cross-link `MASTER_PLAN_2026.md` |
| `ea99062e` | D145 medallion + data-warehouse iron laws + Wave 16 detail in PLATFORM_REVIEW Ch 1.8 + Ch 11 + Ch 13 |

PR is `OPEN`, +1690 / -1, docs-only, CI green expected.

The current Wave 16 in PLATFORM_REVIEW Ch 11 describes a **6-week parallel** medallion migration. **The Wave 0 proposal in this handoff supersedes that timeline if accepted by the founder.** If accepted, PLATFORM_REVIEW Ch 11 needs an amendment to renumber Wave 16 → Wave 0 and adjust the wave count from 16 back to 15 (or keep Wave 16 and call Wave 0 "pre-W1 prerequisite"). Editorial choice for next chat.

---

## 3. The receipts — what's actually true on disk (run these before believing me)

### 3.1 Bronze — 50% real

```bash
$ ls app/services/bronze/
__init__.py  coinbase/  etrade/  tradier/
```

The three NEW brokers are bronze-native ([D130](../KNOWLEDGE.md), [D132](../KNOWLEDGE.md), Coinbase). The three CORE brokers are still grandfathered:

```bash
$ ls app/services/portfolio/ | grep -E "ibkr|schwab|tastytrade"
ibkr/                              # subdir, ~6 files
schwab_sync_service.py             # 32.7K
tastytrade_sync_service.py         # 25.3K
```

None of the grandfathered files carry a `medallion: bronze` docstring tag. A reader landing in the repo cold cannot tell they are bronze.

### 3.2 Silver — 0% real

```bash
$ ls app/services/silver/ 2>&1
ls: app/services/silver/: No such file or directory

$ rg "from app.services.silver" backend/
(no matches)
```

What we call "silver" lives in `app/services/market/`, `app/services/portfolio/portfolio_analytics_service.py`, `app/services/portfolio/closing_lot_matcher.py`, `app/services/tax/*`. Roughly 25 files, zero docstring tags, zero physical layout.

### 3.3 Gold — 60% real

```bash
$ ls app/services/gold/
__init__.py  conviction_pick_generator.py  options_chain_surface.py
peak_signal_engine.py  pick_quality_scorer.py  pick_scorer_config.py
tax_aware_exit_calculator.py  trade_card_composer.py  winner_exit_advisor.py
```

7 native gold files. But the older gold-shaped code is in `app/services/strategy/` (rule evaluator, backtest, walk-forward, signal generator, AI strategy builder) and `app/services/picks/candidate_generator.py` plus `app/services/picks/generators/`.

### 3.4 Execution — orthogonal to medallion (currently mis-classified)

```bash
$ ls app/services/execution/
approval_service.py  broker_adapter.py  broker_base.py  broker_router.py
exit_cascade.py  ibkr_executor.py  order_manager.py  paper_executor.py
risk_gate.py  runner_state_service.py  shadow_mark_to_market.py
shadow_order_recorder.py  slippage_tracker.py
```

These don't fit bronze/silver/gold cleanly. They read gold outputs and write orders to real money. **Recommendation in §6.6**: declare `execution/` a fourth layer. Cleaner story than forcing it into gold.

### 3.5 The DAG accidentally already shows medallion

`frontend/src/components/pipeline/PipelineDAG.tsx` row layout (lines 33–88):

| Row | Stage IDs | In medallion terms |
|---|---|---|
| 0 | `constituents` → `tracked_cache` → `daily_bars` | bronze |
| 1 | `regime` · `indicators` · `exit_cascade` | silver (+ gold straggler) |
| 2 | `scan_overlay` · `strategy_eval` · `snapshot_history` | gold + silver ledger |
| 3–4 | `digest` · `health_check` · `mv_refresh` · `audit` · `warm_dashboard` | observability / ops |

Architecturally correct, rhetorically invisible: zero labels, zero color bands, no legend. Adding swimlane bands behind the existing node grid would make the DAG the **living org chart of the warehouse** with no data-model change. ~80 lines of JSX in Phase 0.A.

### 3.6 Pillars vs medallion are orthogonal framings

The PRD + ARCHITECTURE.md prose describes "Three Pillars deliberately decoupled":
- **Portfolio** (read-only sync) — actually mixes bronze (sync) + silver (analytics).
- **Intelligence** (indicators) — mostly silver.
- **Strategy** (rules + execution) — gold + execution-as-fourth-layer.

We've been writing as if Pillars and Medallion are the same thing. They aren't. Phase 0.A prose sweep makes the mapping explicit instead of implied.

---

## 4. The Wave 0 proposal (4 phases, 6–9 days + 2-week bake)

> **Status**: founder reviewed the detail level and asked for it captured in a handoff doc on this PR. **No implementation has begun.** All file paths and counts below are accurate as of `ea99062e` on this branch.

### Phase 0.A — Rhetorical honesty + mechanical tags (1 day)

1. Module-level docstring tag on every file under `app/services/<dir>/`: `"""medallion: bronze"""` / `silver` / `gold` / `execution` / `ops`. ~100 files. `sed`-able. Zero behavior change.
2. `PipelineDAG.tsx` gets four horizontal swimlane bands (bronze / silver / gold / ops) behind the existing node grid, with a legend. Design tokens from `frontend/src/constants/chart.ts`. ~80 lines JSX.
3. Prose sweep mapping pillars ↔ layers:
   - `docs/ARCHITECTURE.md` Three Pillars + Medallion Architecture sections.
   - `docs/plans/PLATFORM_REVIEW_2026Q2.md` Ch 1.8.
   - `docs/PRD.md` system overview.
   - `AGENTS.md` Three Pillars table.
4. New doc `docs/plans/MEDALLION_AUDIT_2026Q2.md`: one row per file, current path → target layer → move risk → blocker (e.g. "referenced in `job_catalog.py` task_path"). This is the input to Phase 0.C.
5. D127 + D145 entries amended with current-state numbers (3/6 brokers in bronze, 0 files in silver, 7 files in gold native + ~55 grandfathered).

**Reversibility**: trivial. Revert one PR. Docstrings + swimlanes vanish; nothing else changes.

### Phase 0.B — Silver scaffold + CI gate (1–2 days)

1. `app/services/silver/__init__.py` created with module docstring defining the layer contract.
2. Custom lint rule (Ruff plugin if its plugin API supports import-graph rules; else pylint custom checker via astroid). Enforces:
   - `app/services/bronze/**` cannot import from `silver/`, `gold/`, `strategy/`, `picks/`, `execution/`.
   - `app/services/silver/**` cannot import from `gold/`, `strategy/`, `picks/`, `execution/`.
   - Anything outside `gold/` / `strategy/` / `picks/` cannot write to gold tables (data-layer rule, deferred to W3.5 — see §6.5).
3. Wired into `pre-commit` + GH Actions CI. `make lint` fails on violations.
4. Tested with 3–4 deliberate violations (one per kind), then removed.
5. Exception mechanism: `# medallion: allow cross-layer for <reason>` magic comment for the ≤5 known technical-debt imports the ARCHITECTURE.md already flags.

**Reversibility**: trivial. Revert one PR. Rule removed, silver folder empty and harmless.

### Phase 0.C — Automated atomic migration (3–5 days)

The compression-pays-off phase. **Requires founder freeze window** (§6.1).

1. **Migration script** at `scripts/medallion_migrate.py`:
   - Input: `medallion_move_map.yaml` with `{old_path: new_path}` per file.
   - `git mv` in one pass.
   - Rewrites every `from app.services.X.Y import ...` and `import app.services.X.Y` across `backend/`, `tests/`, `alembic/`, `tasks/`.
   - Rewrites `task_path="app.tasks...."` and `"app.services...."` strings in `job_catalog.py`, Celery Beat schedules, `agent/tools.py` dotted-path lookups.
   - Updates relative imports.
   - Runs `ruff --fix`, `isort`, `black`.
   - `python -c "import app.api.main"` to catch import-time failures.
   - `pytest --collect-only` to catch test-import failures.
   - Exits non-zero on any failure.

2. **Move order** (dependency-safe):
   - **Pass 1** — leaf utilities: `market/dataframe_utils.py`, `market/atr_series.py`, `market/coverage_utils.py` → `silver/math/`.
   - **Pass 2** — silver core: `market/indicator_engine.py`, `stage_classifier.py`, `regime_engine.py`, `portfolio/portfolio_analytics_service.py`, `portfolio/closing_lot_matcher.py`, `tax/*` → `silver/`.
   - **Pass 3** — bronze core: `portfolio/ibkr/*`, `portfolio/schwab_sync_service.py`, `portfolio/tastytrade_sync_service.py`, `portfolio/broker_sync_service.py` → `bronze/<broker>/`.
   - **Pass 4** — gold stragglers: `strategy/` → `gold/strategy/`, `picks/` → `gold/picks/`.
   - **Pass 5** — `execution/` stays put; tagged as fourth layer (§6.6).

3. **Shadow re-exports** for the 2-week bake. Every old location keeps a minimal `__init__.py`:
   ```python
   """medallion: grandfathered shim; remove after 2026-05-13. See D145."""
   from app.services.silver.indicator_engine import *  # noqa: F401,F403
   import warnings
   warnings.warn(
       "app.services.market.indicator_engine is moving to app.services.silver; "
       "update imports by 2026-05-13 (D145).",
       DeprecationWarning, stacklevel=2,
   )
   ```
   External callers (Brain, future plugins) keep working through the bake. Internal callers all updated by the script in the same PR.

4. **PR strategy** — recommended split (decision §6.2):
   - **PR A**: Phase 0.C Pass 1 + Pass 2 (silver moves) + shims.
   - **PR B**: Phase 0.C Pass 3 + Pass 4 (bronze + gold moves) + shims.
   Each PR independently green on `make test-all`, `npm run type-check`, `docker compose up` smoke.

5. **Celery `task_path` registration**: deploy with both old + new paths registered for 1 week. Beat schedules updated to new paths. Old paths emit `warnings.warn` but still execute. Prevents in-flight scheduled tasks from 404'ing on first post-deploy Beat tick.

### Phase 0.D — Shadow removal + final cleanup (1 day, 2 weeks after 0.C lands in prod)

1. Shadow `__init__.py` shims deleted.
2. Old `task_path` registrations removed.
3. CI rule upgrades from "warn + tagged exceptions" to "strict; no exceptions without an approved issue reference."
4. `docs/plans/MEDALLION_AUDIT_2026Q2.md` closed out — every file verified at target path.
5. `PLATFORM_REVIEW_2026Q2.md` Ch 11 Wave 16 rewritten as Wave 0, completed.

---

## 5. Compressed timeline

| Day | Phase | What ships | Reversible |
|---|---|---|---|
| 1 | 0.A | Tags + DAG swimlanes + prose + MEDALLION_AUDIT.md + D127/D145 honesty update | Trivially |
| 2 | 0.B | `silver/` folder + CI lint rule + tests | Trivially |
| 3 | 0.C Pass 1 | Leaf utilities moved (~10 files) | Revert one PR |
| 4 | 0.C Pass 2 | Silver core moved (~25 files) + shadow shims | Revert one PR |
| 5 | 0.C Pass 3 | Bronze core moved (~15 files) + shadow shims + danger-zone approval | Revert one PR |
| 6 | 0.C Pass 4 | Gold stragglers moved + `strategy/` + `picks/` relocated | Revert one PR |
| 7 | 0.C verification | Full `make test-all`, prod deploy, Render watch for 24hrs | Roll back deploy |
| ~Day 21 | 0.D | Shadow shims removed, CI gate strict | Revert one PR |

**Real elapsed**: 7 focused days + 2-week passive bake before final cleanup.

---

## 6. Risks and mitigations (do not skip)

### 6.1 Parallel agent conflict — BLOCKING

The founder mentioned a parallel agent during the PR #476 session ("there is an agent in parallel but not writing these docs but access to same code"). Wave 0.C is ~55 file renames across `app/services/`. Any open branch touching `app/services/market/*` or `app/services/portfolio/*` during Wave 0.C will have painful rebases.

**Mitigation**: explicit 3-day freeze window. Founder coordinates with the parallel agent: no new PRs against `app/services/` for the duration of 0.C. Worst case, we rebase-help open branches by running the migration script against them.

**This is decision gate #4** — founder must specify the freeze window before 0.C begins.

### 6.2 Danger-zone approvals

`app/services/market/indicator_engine.py`, `stage_classifier.py`, `regime_engine.py` are **danger zones** per `.cursor/rules/protected-regions.mdc`. Moving them requires founder approval. The diff is zero-content (just a path change), but approval is still required.

**Mitigation**: pre-approval conversation before Phase 0.C Pass 2, with `git diff --stat` proof showing only path-header changes.

PR strategy choice (single atomic PR vs split — decision gate #2):
- **Single atomic PR**: one approval, one CI cycle, one revert button. Higher blast radius.
- **Split** (recommended): silver in PR A, bronze+gold in PR B. Two approvals, two CI cycles, half the blast radius. Adds ~1 day calendar.

### 6.3 Celery `task_path` drift

If any string reference is missed, scheduled tasks silently stop running. Direct violation of `.cursor/rules/no-silent-fallback.mdc`.

**Mitigation**: migration script has explicit coverage for `task_path=` strings + post-migration check that runs `python -c "import app.tasks.<x>"` for every module listed in `job_catalog.py`. Also: 1-week dual-registration window for Celery tasks (both old and new paths registered).

### 6.4 Shadow shims masking real regressions

During the 2-week bake, someone could add a new import to an old path and not get caught.

**Mitigation**: shims emit `DeprecationWarning` that CI treats as error in **new** code via `pytest -W error::DeprecationWarning` against a `tests/test_no_new_grandfathered_imports.py` file. Old code paths keep their warnings soft so existing tests stay green.

### 6.5 Database `gold_plugin` partition doesn't exist yet

The plugin-write gold rule can't be enforced via Postgres grants today; we don't have a `gold_plugin` schema.

**Mitigation**: defer the data-layer gold-write rule to Wave 3.5 when the plugin SDK ([D110](../KNOWLEDGE.md)) lands. Phase 0.B ships **import-layer rules only**.

### 6.6 `execution/` doesn't fit bronze/silver/gold

It reads gold outputs and writes orders to real money. Forcing it into gold collapses two very different danger profiles.

**Resolution**: officially declare `execution/` a **fourth layer** (not a sublayer of gold). Update D127 + D145 + ARCHITECTURE.md + PLATFORM_REVIEW Ch 1.8 to describe four layers: **bronze → silver → gold → execution**. Cleaner danger-zone story; honest about the safety envelope. **This is decision gate #3.**

### 6.7 Two-week bake vs immediate cleanup

Could skip the bake and remove shims in the same PR as the moves. Cheaper, riskier for external callers (Brain, future plugins).

**Recommendation**: keep the bake. 2 weeks of passive waiting, not active engineering. Worst case we shorten to 1 week if bake is uneventful.

---

## 7. Decision gates blocking execution

Founder must answer all four before Phase 0.A begins:

| # | Question | Recommendation | Why it matters |
|---|---|---|---|
| 1 | Wave 0 before W1 (this proposal) or parallel W16 (current PR #476 plan)? | **Wave 0 before W1** | W1 lands against stable layout; plugin SDK designed against real `silver/` + `gold/`; marketing story backed by code day 1 |
| 2 | Single atomic migration PR or split silver-first / bronze+gold-second? | **Split** | Half blast radius per PR for one extra calendar day |
| 3 | Acknowledge `execution/` as a fourth medallion layer? | **Yes** | Cleaner danger-zone story than forcing into gold |
| 4 | 3-day freeze window for Phase 0.C — when? | **TBD by founder** | Parallel agent conflict on `app/services/` is the only true blocker |

If founder answers "yes / split / yes / [date X]" the next chat starts with Phase 0.A as the next commit on PR #476.

If founder answers "no" to gate #1, this handoff becomes a record of the path not taken; PR #476 ships as-is with parallel W16 over 6 weeks.

---

## 8. What changes elsewhere if Wave 0 is approved

Files to amend on PR #476 (or in a follow-up commit) once gate #1 = yes:

1. `docs/plans/PLATFORM_REVIEW_2026Q2.md`:
   - Ch 11 — rename "Wave 16" to "Wave 0 (pre-W1 prerequisite)"; reduce timeline 6 weeks → 6–9 days + 2-week bake.
   - Ch 13 — restate commitment #5 as "16 waves total (Wave 0 + W1–W15); W3.8 conditional; Wave 0 mandatory pre-W1."
   - Ch 1.8 — add "four-layer model" subsection if gate #3 = yes.
2. `docs/KNOWLEDGE.md`:
   - D127 — amend with current-state numbers + reference to Wave 0.
   - D145 — amend timeline + add four-layer-model reference.
   - New D146 if gate #3 = yes — formalizes execution as fourth layer.
3. `docs/plans/MASTER_PLAN_2026.md` — cross-link Wave 0 + new D146.
4. `docs/ARCHITECTURE.md` — Three Pillars table maps to four layers; Medallion Architecture section reflects current-state honesty + Wave 0 timeline.
5. `AGENTS.md` — Three Pillars table maps pillars ↔ layers.

---

## 9. Resume prompt for next chat

If this handoff is being read by a fresh session:

```
Continue work on branch `docs/platform-mckinsey-review-2026q2` (PR #476).

Read first: docs/handoffs/2026-04-22-medallion-wave-0-stage-setting.md (this file).
Then: docs/plans/PLATFORM_REVIEW_2026Q2.md Ch 1.8 + Ch 11 Wave 16.
Then: docs/KNOWLEDGE.md D127 + D145.

State of play:
- PR #476 has 3 commits (ccd78f0d, 6bf749c4, ea99062e) — strategic spine docs only.
- Founder asked for a Wave 0 medallion-stage-setting plan in detail; this handoff captured it.
- Founder has NOT yet answered the four decision gates in §7. Do not begin Phase 0.A
  implementation until gate #1 = yes.
- If gate #1 = no, archive this handoff and ship PR #476 as-is.

If gate #1 = yes:
  1. Confirm freeze window (gate #4) with founder before any app/services/ changes.
  2. Begin Phase 0.A (docstring tags + DAG swimlanes + prose + MEDALLION_AUDIT.md + D127/D145 amendments).
  3. Open as next commit on the same PR #476 branch (do not branch off).

Workspace context:
- Worktree at /tmp/afo-review on branch docs/platform-mckinsey-review-2026q2.
- Main workspace at /Users/axiomfolio/development/axiomfolio (DO NOT write here; parallel
  agent has been observed git-resetting; use the worktree).

Open questions to validate before any code:
- Has the parallel agent stopped touching app/services/?
- Has founder confirmed the freeze window dates?
- Does pylint/ruff plugin choice for the CI gate (Phase 0.B) match what we already use elsewhere?
  (Check pyproject.toml and existing pre-commit config before implementing.)
```

---

*Last updated: 2026-04-22. Author: Opus session that followed PR #476 (commit `ea99062e`). Next review: when founder answers decision gates §7, or 7 days from now (2026-04-29) if no answer received.*
