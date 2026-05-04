---
last_reviewed: 2026-05-04
doc_kind: audit
domain: brain
status: active
audience: founder
authored_by: composer-2-fast subagent (principal-engineer persona, second-pass review)
product: [brain, platform, studio]
---

# Q2 Master Plan — Principal Engineer Review v2

**Subject:** [`~/.cursor/plans/paperwork_2026q2_master_plan_f9ce7c63.plan.md`](file:///Users/paperworklabs/.cursor/plans/paperwork_2026q2_master_plan_f9ce7c63.plan.md)
**Reviewer:** Principal Engineer persona (composer-2-fast subagent dispatch)
**Date:** 2026-05-04
**Companion:** [Q2_MASTER_PLAN_PRINCIPAL_REVIEW_2026-05-03.md](Q2_MASTER_PLAN_PRINCIPAL_REVIEW_2026-05-03.md) (round 1)

---

## Executive verdict

**Approve with conditions.** The patched plan in `~/.cursor/plans/paperwork_2026q2_master_plan_f9ce7c63.plan.md` correctly absorbs round 1's P0s: **T1.0d** (Conversations Postgres, lines 202–203), **T2.0** goals unification (243), **T1.2** acceptance fixed to `/internal/schedulers` + dispatches (204), **015/016 serialization** for T2.4/T1.5 (249), **T2.10a** before snapshot kill (259–260), **T4.2a–c** gateway split (373–378), **T3.1-pre** vault scopes (337), **T3.11/T3.12** staging + backup (358–361), **T2.13** PII (284–285), **T3.13** Sentry + rotation (361–365), **T2.11** before `workstreams.json` kill (261–262), **T5.5** XL + off critical path (392, 470–474). Founder ground truth (141–150) and labels block (154–190) sharpen execution. Top concerns: **internal sequencing inconsistency** (mermaid puts **T1.6 before T1.0d** while carry-forward lists **T1.0d first**, lines 417–436 vs 553–555), **T2.20 tarball/JSONL trust boundary** under-modeled (307–313), and **Hetzner-as-canonical-build** without **runner disaster playbook** (148, 353–357).

---

## Verification of round 1 findings

| ID | Status | How (T#. + plan path) | Quality of fix vs `no-silent-fallback.mdc` |
|----|--------|------------------------|---------------------------------------------|
| **F1** | ADDRESSED | **T1.0d** — `~/.cursor/plans/paperwork_2026q2_master_plan_f9ce7c63.plan.md` L202–203 | Robust if acceptance strictly forbids disk canonicality and proves row counts; good explicit `open()`/`sqlite3` zero targets. |
| **F2** | ADDRESSED | **T2.0** — same file L243 | Robust: one table, delete `goals.json`, OBJECTIVES overlay; aligns with anti-split-brain. |
| **F3** | ADDRESSED | **T1.2** — L204 | Robust: replaces wrong `/admin/health` story with schedulers + dispatches + `/admin/autopilot` header + Neon pool note. |
| **F4** | ADDRESSED | **T2.4** note — L249; **T1.5** L207 migration 016 | Robust: serial merge + `alembic heads` check. |
| **F5** | ADDRESSED | **T2.10a** — L259–260; **T2.10** table L263–280 | Robust if T2.10a acceptance is "endpoint live before snapshot PR". |
| **F6** | ADDRESSED | Critical path **T10d → T41** — L449 | Robust: RLS after Postgres-canonical conversations. |
| **F7** | ADDRESSED | **T4.2a/b/c** — L373–378 | Robust split; avoids single "L" monolith. |
| **F8** | PARTIALLY ADDRESSED | **T1.0a** L199 (PR #689) | **Band-aid risk** until merged: acceptance should **prove** `Workstream` accepts `epic-ws-82-studio-hq` (round 1 test); plan does not restate that test in T1.0a text. |
| **F9** | ADDRESSED | **T3.1-pre** — L337 | Robust: scope proof before drift coding. |
| **F10** | ADDRESSED | **T5.5** L392; mermaid **T55** off-path L470–474 | Robust: XL + explicit non-blocker for L4/L5. |
| **F11** | PARTIALLY ADDRESSED | **T2.5** L250–251 ("endpoint verified") | **Still vague:** does not explicitly require **path alignment** Studio proxy ↔ Brain `persona-reply` route (round 1 root cause). Risk of **silent 404** if "verified" means smoke only. |
| **F12** | PARTIALLY ADDRESSED | **T3.9** L353–357 | Mentions "~50" `ubuntu-latest` and audit; **does not** repeat round 1's **`.yaml` + `.yml`** inventory warning — naive audit can still miss `.yml` workflows. |
| **M1** | ADDRESSED | Same as F1 (**T1.0d**) | — |
| **M2** | ADDRESSED | **T3.11** L358–359 | Robust with explicit health URL acceptance. |
| **M3** | ADDRESSED | **T3.12** L360–361 | Robust if PITR tier is validated (not assumed). |
| **M4** | ADDRESSED | **T2.13** L284–285 | Robust as explicit per-surface + CI guard. |
| **M5** | ADDRESSED | **T3.13** bullet 1 L362; ties to **T3.7** L351 | Good: forces observable error pipeline. |
| **M6** | ADDRESSED | **T1.2** tail L204 (`max_connections`, ≤20 jobs) | Robust headroom check. |
| **M7** | ADDRESSED | **T3.13** L362–365 | Policy + scheduler + `alert` tag — visible degradation path. |
| **M8** | ADDRESSED | **T2.11** L261–262 | Explicit ordering before T2.10; aligns with no-silent-fallback for auto-close. |

**Escalation:** None to P0 from round 1 leftovers; **F11** is the closest (treat as **P1** if T2.5 ships without path parity test).

---

## New round 2 findings

**F13 — P1 — Critical path vs carry-forward contradict on early-week order**
**What:** Mermaid shows `T1.0a-c → T1.6 → T1.0d` (`paperwork_2026q2_master_plan_f9ce7c63.plan.md` L419–421) while "Next-chat carry-forward" lists **T1.0d first** among Week 1 serial items (L553–555). Data-loss window favors **T1.0d** as early as possible; **T1.6** first only makes sense for fleet discipline, not for Postgres canonicality. **Where:** same file L417–436, L553–555. **Recommendation:** Pick one order, document rationale (e.g. "T1.0d day 1 orchestrator-only; T1.6 before any cheap-agent T1.0d assist"). Update mermaid **or** carry-forward so they match.

**F14 — P2 — Migration **017** vs **015** "decisions already labeled""
**What:** Foundational labels section says **`decisions` created in T2.4 migration 015 with the four columns** (L169) while **T2.16** is "add 4 columns … to all existing D65 tables" (L290). Either 017 is a no-op for `decisions` or Alembic must use idempotent `ADD COLUMN IF NOT EXISTS` — plan says "one migration ~50 lines" (L171) but does not spell out **per-table skip list**. **Where:** L167–171, L290. **Recommendation:** In T2.16 acceptance, list tables touched by 017 **excluding** any table already migrated in 015/016, or mandate idempotent ops.

**F15 — P2 — **T1.6** hook bootstrap / merge chicken-and-egg**
**What:** Three new **fail-closed** `subagentStart` hooks (L211–216) must merge via a process that may itself dispatch subagents; first deploy risks **self-block** or **temporary disable**. **Where:** L211–216. **Recommendation:** Add acceptance: "Bootstrap PR for T1.6 merged from orchestrator session with hooks disabled in Cursor settings **or** explicit one-time waiver documented in PR body; re-enable immediately post-merge."

**F16 — P1 — **T2.20** cross-machine ingest trust boundary**
**What:** **POST `/api/v1/admin/transcripts/import`** accepts tarball of `*.jsonl` (L307–312), `BRAIN_INTERNAL_TOKEN` auth. Threats: **zip/tar slip**, **path traversal**, **hostile JSONL** driving **prompt-injection** into **T2.18** LLM labeling, **oversized archives** (DoS). Founder token compromise = full blast. **Where:** L307–313. **Recommendation:** Add workstream bullets: max untar size, file count cap, allowlist paths under `agent-transcripts/`, strict JSON parse with **fail-closed** ingest report (`chunks_failed` surfaced per bible D67 pattern in `BRAIN_BIBLE_GAP_AUDIT_2026-05-03.md` L158), optional **virus scan** deferral note, security review checkbox.

**F17 — P1 — **T1.0c** body-text guard: plan cites line numbers; repo not patched**
**What:** Plan references `.github/workflows/auto-merge-sweep.yaml` L117–128 + 365–368 (`paperwork_2026q2_master_plan_f9ce7c63.plan.md` L201). In repo, **`tryAgentMerge`** (e.g. L353–411) merges after labels/🔴/CI but **does not** inspect `pr.body` for `HOLD FOR` / `DO NOT MERGE` / 🛑. **Where:** `.github/workflows/auto-merge-sweep.yaml` L353–411; plan L201. **Recommendation:** Treat as **pre-kickoff** gap; implement guard on **full PR body** (and optionally title) before merge; add regression fixture PR.

**F18 — P1 — Founder ground truth **#4** without Hetzner failure mode**
**What:** Hetzner is canonical for builds (plan L148; **T3.9** L353–357). No runbook slice for **VM loss**, **disk corruption**, **GitHub runner disconnect**, or **temporary fallback to `ubuntu-latest`** with explicit **visibility** (per `no-silent-fallback.mdc`: observers must see degradation). **Where:** L148, L353–357. **Recommendation:** Extend **T3.9** or **T3.3** with `docs/runbooks/HETZNER_RUNNER_FAILOVER.md`: RTO, manual `runs-on` override policy, alerting via Conversation `alert` when self-hosted queue depth > N.

**F19 — P2 — **F12** tail: `.yml` workflows still easy to miss**
**What:** **T3.9** does not restate round 1's "38 files / `*.yml` glob" lesson (`Q2_MASTER_PLAN_PRINCIPAL_REVIEW_2026-05-03.md` L164–166). **Where:** plan T3.9 L353–357. **Recommendation:** One sentence: "`scripts/check_workflow_runners.py` must glob **all** `.github/workflows/*.{yml,yaml}`."

**F20 — P2 — "Pre-dev / pre-user" vs live debt**
**What:** Founder lock **#6** (plan L150) claims ideal timing for labels; same plan presupposes **deleting** `apis/filefree/tax-data/` (**T5.1** L388) and **2,449 lines** TS in `packages/filing-engine` (**T5.5** L392, confirmed by `wc`). **Where:** L150, L388, L392. **Recommendation:** Qualify in plan intro: "Pre-user **for Brain company-os corpus**; product monorepo already contains multi-year debt surfaces."

---

## Risks to L4 handoff timeline

**Top 3 schedule risks**
1. **T1.0d** scope: `apis/brain/app/services/conversations.py` is **~786+ lines** with JSON/SQLite/FTS — rewrite + backfill + `tsvector` is **M+**, not a slam dunk; slip here slides **T4.1**, **T2.x**, and "Spine done".
2. **T2.10a** (eight endpoints) + **T2.17/T2.18** labeling fleet: parallel composer batches still need **orchestrator** merge queue (**cheap-agent-fleet.mdc** L97–107); **~69 workstreams** (plan L533) is **~33% more** than round 1's ~46 — honest calendar stretch **16+ weeks** if merge/review saturation hits.
3. **T4.1** RLS + **T3.11** staging: **L**-shaped security work rarely lands in **"one burn-in weekend"**; tenant script **T4.6** (L382–383) depends on staging + RLS both true.

**Top 3 silent-failure risks**
1. **T2.5** persona-reply: UI unflag without **route parity** → **200/404** that looks like "AI slow" (**F11** residual).
2. **T2.11** incomplete repoint: **`workstreams.json` deleted** while code path still `open()` → **empty epics** or swallowed errors (**violates** `no-silent-fallback.mdc` if not logged).
3. **T2.18** labeling: **`label_confidence` fake-high** via LLM cheerleading — queue **T2.19** never drains; **"labels complete"** gate (L490) is falsely green.

**Top 3 sequencing risks**
1. **Mermaid vs carry-forward** (**F13**): teams literally disagree on Week 1 order.
2. **T2.16 after T2.4/T1.5**: any new **`op.create_table`** for D65 between **015–017** without four columns breaks **enforce-d65-labels** intent (plan L187–189) — needs **gating** in dispatch prompts.
3. **T4.2b** after **T1.4**: gateway MCP path stalls if **brain_user_vault** wiring slips; **T5.4** consumed early could look "done" with **hardcoded** tokens (**doctrine violation**).

---

## Approval recommendation

**APPROVE WITH CONDITIONS**

1. **Reconcile T1.0d vs T1.6 ordering** in diagram + carry-forward (**F13**).
2. **T2.5 acceptance**: explicit **HTTP path contract test** Studio ↔ Brain (**F11**).
3. **Land T1.0c** body guard before relying on agent auto-merge; verify line-**semantic** match, not line numbers (**F17**).
4. **T2.20**: add **size/path/parse** limits and failed-chunk visibility (**F16**).
5. **T3.9 + runbook**: Hetzner **SPOF / fallback** with visible degradation (**F18**).
6. **Monitoring**: `GET /internal/schedulers` includes **`brain_autopilot_dispatcher`** after **T1.2**; enforce **`alembic heads`** log on every migration merge (**T2.4**/**T1.5**/**T2.16**).

---

*All 6 conditions addressed in plan patches landed 2026-05-04. See [`docs/KNOWLEDGE.md`](../KNOWLEDGE.md) D94.*
