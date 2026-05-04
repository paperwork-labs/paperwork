# Wave 1 audit: Agent dispatch + outcomes

## TL;DR

Telemetry for cheap-agent dispatches is **spec-first but operationally hollow**: the Cursor hook blocks bad models, and Brain exposes **admin APIs + Postgres** for dispatches and **GitHub polling** for `pr_outcomes.json`, but **nothing in this repo automatically records Cursor `Task` dispatches** to `agent_dispatch_log.json` or `POST /api/v1/agents/dispatches`. The canonical JSON log in-repo is still an empty template (`dispatches: []`). **`autopilot_dispatcher.install()` is never registered** on the shared APScheduler (confirmed — only defined in `autopilot_dispatcher.py`). Migration `014` creates `agent_dispatches` and indexes/constraints as designed, but its **backfill path resolves to `apis/data/agent_dispatch_log.json`**, not `apis/brain/data/agent_dispatch_log.json`, so upgrade-time seeding likely missed real data unless a symlink/copy existed. **Prod table presence was not verified** (no DB access from this audit). Weekly self-improvement computes retros and a **Brain Improvement Index** from `pr_outcomes` + other files; it does **not** re-rank model preferences from dispatch history (WS-64-style correlation remains stubbed via `propose_rule_revisions` returning `[]`).

## Findings

### 1. DB tables

| Check | Verdict | Evidence |
| --- | --- | --- |
| `agent_dispatches` in prod | **?** | Migration defines table only; live DB not queried from this environment. |
| Schema (`id`, `t_shirt_size`, `model_used`, `subagent_type`, `pr_number`, `outcome`, `dispatched_by`, …) | **✓** | `apis/brain/alembic/versions/014_agent_dispatches.py` lines 63–94; ORM `apis/brain/app/models/agent_dispatch.py` lines 102–131. |
| `no_opus_as_subagent` | **✓** | SQL `CONSTRAINT ... CHECK ((dispatched_by != 'subagent') OR (model_used NOT LIKE '%opus%'))` at `014_agent_dispatches.py` lines 91–93; ORM `agent_dispatch.py` lines 88–90. |
| Indexes (`workstream_id`+`dispatched_at`, `t_shirt_size`, `outcome`, `dispatched_at`) | **✓** | `014_agent_dispatches.py` lines 100–107; ORM `agent_dispatch.py` lines 92–99. |

**⚠ Backfill path:** `_AGENT_DISPATCH_LOG_REL = Path(__file__).resolve().parents[3] / "data" / "agent_dispatch_log.json"` resolves to **`apis/data/agent_dispatch_log.json`** (verified via `python3 -c …`), not `apis/brain/data/agent_dispatch_log.json` where the canonical log and docs point.

### 2. Hook enforcement

| Check | Verdict | Evidence |
| --- | --- | --- |
| Script exists | **✓** | `.cursor/hooks/enforce-cheap-agent-model.sh` |
| Executable | **✓** | `stat`: `-rwxr-xr-x` |
| `hooks.json` + `failClosed` | **✓** | `.cursor/hooks.json` lines 4–9 (`subagentStart`, `failClosed: true`) |
| Allow-list | **✓** | Script lines 15–20: `composer-1.5`, `composer-2-fast`, `gpt-5.5-medium`, `claude-4.6-sonnet-medium-thinking` |
| Opus block | **✓** | Script lines 72–76: case-insensitive `*opus*` substring deny |

### 3. Logging from Cursor / Task tool

| Check | Verdict | Evidence |
| --- | --- | --- |
| Where Task dispatch is logged | **✗ / none in-repo** | No codebase path found that writes dispatch rows when Cursor runs `Task`. Hook only **allows/denies** startup (stdin JSON); it does not append logs. |
| Wrapper → JSON + DB | **✗** | DB insert path is explicit HTTP `POST /api/v1/agents/dispatches` with `X-Brain-Secret` (`apis/brain/app/routers/agent_dispatches.py` lines 184–212). No Cursor-side caller located. |
| `stamp_preflight` | **⚠** | `apis/brain/app/services/agent_dispatcher.py` implements helper; comment lines 5–6 say **Future:** append helpers “can call” it — **no integration found**. |

**Evidence — empty canonical log:** `apis/brain/data/agent_dispatch_log.json` lines 27–28 show `"dispatches": []`.

### 4. JSON ↔ DB sync

| Check | Verdict | Evidence |
| --- | --- | --- |
| Migration backfill runs on upgrade | **✓** if migration applied | `upgrade()` calls `_backfill_from_jsonl()` at `014_agent_dispatches.py` line 111. |
| Backfill reads correct file | **⚠ / likely wrong path** | Targets `apis/data/agent_dispatch_log.json` (see §1). Function name/docstring say “jsonl” but implementation reads **single JSON** with `dispatches` array (`014_agent_dispatches.py` lines 114–119, 121–127). |
| Runtime sync job JSON ↔ DB | **✗** | No scheduled or service loop found that mirrors new JSON entries into `agent_dispatches`. |
| Source of truth | **⚠ split brain** | Operational docs and Studio read **`agent_dispatch_log.json`** (`dispatches` array). **`autopilot_dispatcher`** appends **`agent_dispatch_log.jsonl`** (`autopilot_dispatcher.py` lines 67–73, 212–220) — **different filename/format** from the canonical JSON contract. |

### 5. autopilot_dispatcher wiring

| Check | Verdict | Evidence |
| --- | --- | --- |
| Module + `install()` exist | **✓** | `apis/brain/app/schedulers/autopilot_dispatcher.py` lines 338–356 |
| `install()` called from `schedulers/__init__.py` | **✗** | Full file `apis/brain/app/schedulers/__init__.py` — installs many modules; **no** `autopilot_dispatcher`. |
| Called from `pr_sweep.start_scheduler` | **✗** | `rg autopilot` under `apis/brain` — only `autopilot_dispatcher.py`, tests, admin persona routes; **not** in `pr_sweep.py` install chain. |

Brain lifespan calls `app.schedulers.start_scheduler()` → `pr_sweep.start_scheduler()` then package installs (`apis/brain/app/main.py` line 124; `apis/brain/app/schedulers/__init__.py` lines 25–114).

### 6. PR outcome tracking

| Check | Verdict | Evidence |
| --- | --- | --- |
| `pr_outcomes.json` exists | **✓** | `apis/brain/data/pr_outcomes.json` (glob hit). |
| Append on merge | **✓** (when job runs + token) | `pr_outcome_recorder.run_once` → `pr_outcomes.record_merged_pr` (`pr_outcome_recorder.py` lines 302–324; `pr_outcomes.py` `record_merged_pr`). |
| Scheduled job | **✓** | `pr_outcome_recorder.install` registered from **`pr_sweep.start_scheduler`** (`pr_sweep.py` lines 206–211), same scheduler instance extended by `schedulers/__init__.py`. |
| 1h / 24h / 7d updates | **⚠ partial** | Schema has `h1`, `h24`, `d7`, `d14`, `d30` (`schemas/pr_outcomes.py` lines 26–31). **Scheduler only fills `h24`** in `run_once` (`pr_outcome_recorder.py` lines 370–392; only `update_outcome_h24`). **`update_outcome_h1` / `update_outcome_lagging` unused outside tests** (`rg` → `test_pr_outcomes.py` + service defs only). |
| “Failed CI” without merge | **?** | Poller uses **merged** PR search path; open PR CI failure is **not** the same code path as merge outcomes (not deeply traced beyond merge recorder scope). |

### 7. UI surfacing

| Surface | Verdict | Evidence |
| --- | --- | --- |
| Admin cost / DB rollups | **✓** | Studio `apps/studio/src/app/admin/cost/page.tsx` — fetches `${auth.root}/agents/dispatches/cost-summary` (Brain API). |
| Dispatch log / activity | **✓** (JSON + Brain proxy) | Overview + personas use `agent_dispatch_log.json` or `GET .../admin/agent-dispatch-log` — e.g. `apps/studio/src/lib/personas.ts` lines 128–132, 624–691; `apps/studio/src/app/admin/overview-pulse-attention-client.tsx` lines 141–174. |
| T-shirt / workstream rollup from DB | **✓** | `agent_dispatches.py` `cost-summary` aggregates by size and workstream (lines 300–417). |
| Acceptance rate | **⚠** | Personas derive labels from **JSON** dispatch outcomes (`personas.ts` `approvalRateLast30dLabel`), not from `agent_dispatches.outcome` counts. |
| Procedural memory from PR feedback | **⚠** | Self-improvement / learning tabs reference procedural memory files and dispatch meta (`learning-tab.tsx`, `self-improvement.ts`); **no** dedicated “PR review comment ingest → rules” UI traced in this pass beyond existing procedural YAML / weekly retro narrative. |

### 8. Calibration loop (WS-64)

| Check | Verdict | Evidence |
| --- | --- | --- |
| `self_improvement` scheduler | **✓** | `apis/brain/app/schedulers/self_improvement.py` — Mondays 08:30 UTC; calls `compute_weekly_retro` + `record_retro`. |
| Re-rank dispatch preferences from outcomes | **✗** | `compute_weekly_retro` aggregates merges/reverts/candidates/rules (`self_improvement.py` lines 445–495). **`propose_rule_revisions` explicitly returns `[]`** (lines 526–533: “stub … returns no revisions”). |
| `compute_brain_improvement_index` | **✓** (different scope) | Uses **acceptance rate from `h24`**, promotions, rules count, retro POS — **not** per-model dispatch ranking (`self_improvement.py` lines 599–705). |
| Last run | **?** | Requires runtime logs / `weekly_retros.json` inspection on deployed host; not checked here. |
| Cost calibration job | **⚠ stub** | `cost_calibration_scheduler.py` documents “Stub for Wave L”; only `find_uncalibrated_rows` + logging (`lines 1–7`, `40–59`). |

## Gap list

```yaml
gaps:
  - id: dispatch-gap-1
    severity: critical
    surface: logging
    description: Cursor Task dispatches are not persisted to agent_dispatch_log.json or agent_dispatches by any automated path in-repo.
    evidence: apis/brain/data/agent_dispatch_log.json:27-28 (empty dispatches); agent_dispatcher.py:5-6 (Future-only stamp_preflight)
    fix_size: M

  - id: dispatch-gap-2
    severity: high
    surface: scheduler
    description: autopilot_dispatcher.install() is never registered; the 5-minute dispatch loop never runs in production Brain.
    evidence: schedulers/__init__.py (full register list, no autopilot); autopilot_dispatcher.py:338-356 (install defined only)
    fix_size: S

  - id: dispatch-gap-3
    severity: high
    surface: sync
    description: Migration 014 backfill resolves to apis/data/agent_dispatch_log.json, not apis/brain/data/agent_dispatch_log.json.
    evidence: 014_agent_dispatches.py:27-29; python resolved path = .../apis/data/agent_dispatch_log.json
    fix_size: XS

  - id: dispatch-gap-4
    severity: medium
    surface: sync
    description: autopilot writes agent_dispatch_log.jsonl while the rest of Brain/Studio expects agent_dispatch_log.json with a dispatches array.
    evidence: autopilot_dispatcher.py:67-73,212-220 vs personas.ts:128-132
    fix_size: M

  - id: dispatch-gap-5
    severity: medium
    surface: outcomes
    description: pr_outcome_recorder fills h24 only; h1 and lagging horizons (d7/d14/d30) are never updated by schedulers.
    evidence: pr_outcome_recorder.py:386-391; rg update_outcome_h1 → tests only
    fix_size: M

  - id: dispatch-gap-6
    severity: medium
    surface: calibration
    description: WS-64-style rule proposals from incidents are stubbed (empty list); no model×workstream re-ranking implemented.
    evidence: self_improvement.py:526-533
    fix_size: L

  - id: dispatch-gap-7
    severity: low
    surface: calibration
    description: Monthly cost calibration job does not write actual_cost_cents; only discovers rows needing calibration.
    evidence: cost_calibration_scheduler.py:1-7,40-59
    fix_size: M

  - id: dispatch-gap-8
    severity: high
    surface: db
    description: Production agent_dispatches table existence and migration 014 apply state were not verified (no live DATABASE_URL query).
    evidence: audit constraint — read-only, no prod DB
    fix_size: XS
```

## "Implemented but not wired" call-outs

1. **`autopilot_dispatcher.install`** — Full `install()` + job id `brain_autopilot_dispatcher` exists; **never added** to `pr_sweep` or `schedulers/__init__.py` chains.
2. **Cursor → Brain dispatch telemetry** — Hook enforces model; **no** companion writer to JSON or `POST /api/v1/agents/dispatches`.
3. **`stamp_preflight`** — Implemented; **no** dispatch-append pipeline invokes it before persistence.
4. **`update_outcome_h1` / `update_outcome_lagging`** — Implemented in `pr_outcomes.py`; **schedulers never call** them (only tests).
5. **`cost_calibration_scheduler` “calibration”** — Job runs monthly but **only logs** uncalibrated rows; billing fill deferred (“Phase H”).
6. **`propose_rule_revisions`** — WS-64 hook returns **`[]`** until corpus threshold logic is implemented (`self_improvement.py`).

**Related mis-wiring (not “dormant code,” but broken path):** Migration **014 backfill** targets **`apis/data/`** instead of **`apis/brain/data/`**, undermining the intended JSON → DB seed on upgrade.

---

**Honest scope:** This audit is static analysis + file-path verification only. No production DB queries, no Render logs, no `/internal/schedulers` call against a running Brain instance.
