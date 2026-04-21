# Session Handoff — 2026-04-20 Midnight Merge Storm

> **Companion to `2026-04-21-g22-shipped-next-g23.md`.** That doc covers the G22 sync-completeness work and the deploy-pipeline-broken discovery. *This* doc covers the feature-PR cleanup thread that ran immediately before G22 — the 5 PRs that landed in a 3-hour window on 2026-04-20 and roughly doubled `main`'s feature surface area between 17:00 and 20:50 UTC. Read both together before picking up the next PR.

Authored by the Opus instance that ran the merge-storm thread (transcript `b27538e2-015c-4160-ac22-397505132008`). That session merged from "5 feature branches with dirty conflicts and flaky CI" to "main is clean, auto-merge armed, handoff to the G22 session." It is also the thread whose final merge (#377 at 19:48 UTC) coincides exactly with Render's `build_failed` streak start — see "Evidence for D120" below.

---

## TL;DR — the 30-second pickup

- **5 feature PRs shipped to main in this session**, none of them deployed to prod due to the deploy-pipeline break documented in `2026-04-21-g22-shipped-next-g23.md` section "CRITICAL".
- **Alembic chain was re-sequenced 4 times** as the PRs landed. Final state is clean; if you're opening a new PR today, chain off the new head which depends on where G22 (`0053`) ends up after the next prod deploy.
- **#377 (multi-tenant hardening) merged at exactly 19:48 UTC** — the same minute Render's `build_failed` streak started. That is either a coincidence or a lead. The G22 handoff assumes billing / build-minutes; nobody has yet bisected whether #377 itself (or #379 right after) ships a change that causes Render to reject the build at queue time. **Check this before accepting the billing-only diagnosis.**
- **Delegation pattern that worked**: `composer-2-fast` subagents for keep-both-additive conflict resolution; Opus for alembic chain math, flaky-test root cause, and judging semantic (non-additive) conflicts. Auto-merge queue beat every custom cascade-merge orchestrator we tried.
- **#292 closed** (stale audit, never intended to merge code). **#353 left open** (Dependabot frontend-minor bump × 17; the `Auto-merge (Dependabot only)` workflow is failing — close and let Dependabot reopen in smaller batches, or fix the workflow).

---

## What shipped (merge-storm session, 17:00–20:50 UTC)

| PR | Squash SHA | Merged (UTC) | Scope | Migration added |
|----|-----------|--------------|-------|-----------------|
| #370 | `63705d6d` | 19:30 | MCP server — per-user bearer-token JSON-RPC (6 read-only tools), Settings UI to mint/revoke tokens | `0044_add_mcp_tokens.py` |
| #373 | `261349ad` | 19:41 | Walk-forward optimizer — Optuna, per-regime, tier-gated, routed to `heavy` queue, `backtest.walk_forward_run` endpoint | `0046_add_walk_forward_studies.py` |
| #377 | `4e139e5f` | **19:48** | Multi-tenant hardening — per-tenant rate limits, GDPR export/delete jobs, cost rollup, incidents | `0050_add_multitenant_hardening.py` |
| #379 | `9b742b78` | 19:53 | Generic OAuth broker foundation + E*TRADE sandbox adapter (extensible for Schwab / Fidelity / Tasty) | `0043_add_broker_oauth_connections.py`, `0051_broker_oauth_unique_coalesce.py` |
| #376 | `6a96cc27` | 20:50 | Trade Decision Explainer — LLM "why this trade" drawer on executed orders, tier-gated Pro+, caches per `order_id` | `0052_add_trade_decision_explanations.py` |

PR #292 was **closed as intentional** (old market-data audit findings, never meant to merge as code). PR #353 (Dependabot: 17 frontend-minor-and-patch bumps) was **left open** — the `Auto-merge (Dependabot only)` workflow is failing; the next agent can either fix that workflow or close-and-reopen in smaller batches.

### Final alembic chain on main (after #385 landed)

```
…0040 ← 0047 ← 0049 ← 0048 ← 0044 ← 0045 ← 0046 ← 0050 ← 0043 ← 0051 ← 0052 ← 0053
```

The chain was re-sequenced **four times** during this session because each merge invalidated the in-flight PRs' `down_revision`. Pattern for future sprints: when `test_migration_chain.py::test_single_head` fails with `Expected 1 head, got 2: ['00XX', '00YY']`, don't patch blindly — compute the new head on main, renumber your PR's migration file if the number already exists upstream, and update `revision = "00NN"` and `down_revision = "<current main head>"` together. Two concrete collisions that required renumbering in this session:

- #377 shipped `0050_add_multitenant_hardening.py`; #379's in-flight migration was also numbered `0050_broker_oauth_unique_coalesce.py`. Renumbered #379's to `0051_*` after #377 merged.
- #376's in-flight migration was numbered `0051_add_trade_decision_explanations.py`; after #379's `0051_broker_oauth_unique_coalesce.py` landed on main, #376's was renumbered to `0052_*`.

---

## Evidence for D120 / G28 that's tighter than the G22 handoff captured

**The Render `build_failed` streak began at 19:48 UTC** — the exact minute PR #377 squash-merged. The G22 handoff (`2026-04-21-g22-shipped-next-g23.md` section CRITICAL) treats this as a billing / build-minutes issue and proposes the founder clear it in the Render dashboard. That may well be the root cause. But before accepting it:

- Did #377's new `backend/tasks/multitenant/gdpr.py` + `backend/tasks/multitenant/cost_rollup.py` + `heavy` queue routing trip a `render.yaml` worker pickup mismatch?
- #377 added `TenantRateLimit`, GDPR job tables, and `IncidentRow` models. Is there a new Redis prefix or env var that Render's build step imports but we didn't define on both `axiomfolio-api` and `axiomfolio-worker` services?
- #379 (OAuth) added its own env var set for E*TRADE sandbox credentials. Confirm they're defined (or tolerate-absent) on both services.

**If the root cause is code, not billing, D120 needs a correction** — its decision text currently treats Render queue rejection as the failure class; a build that never starts because of a malformed `render.yaml` or an `ImportError` at boot is a different class. G28's polling probe should distinguish them (Render's deploy API exposes both `status` and a `logs` URL; the logs will show whether the build entered Docker build or was rejected pre-build).

**Suggested triage before unblocking prod**: read the Render build logs for the first two `build_failed` deploys (19:48 and whatever came right after) via `GET /v1/services/{id}/deploys/{id}/logs`. Ten minutes of log-reading may save several PRs' worth of speculation. If the logs are empty / show queue-rejection only, billing is the answer. If they show a stack trace, revert-bisect #377 → #379 → #376 in that order.

---

## Deploy risk when prod unblocks

First successful deploy after the unblock ships **11 migrations (`0043` → `0053`) and ~5 PRs' worth of new code simultaneously**. That is a fat delta for an environment that hasn't received a deploy in 8+ hours and whose most recent live SHA is `261349ad` (PR #373). Recommend a staged restart rather than letting Render auto-deploy both services concurrently:

1. **Migrate first** via `alembic upgrade head` on `worker-heavy` in isolation, or via a one-shot migration job.
2. **Restart API only.** Confirm `/health/full` reports `0053` and every new column is present (`account_syncs.warnings`, `account_syncs.expected_sections`, `account_syncs.received_sections`, `account_syncs.missing_sections`, `account_syncs.section_row_counts`, plus the MCP, walk-forward, multi-tenant, OAuth, trade-explainer tables).
3. **Restart worker + worker-heavy.** Confirm Beat picks up the new scheduled tasks: `daily_corporate_actions`, `explain_recent_trades`, `walk_forward_optimizer_run`, `backend.tasks.multitenant.gdpr.*`, `backend.tasks.multitenant.cost_rollup.*`, `backend.tasks.data_quality.scheduled_quorum_check`.
4. **Only then** run the founder's IBKR re-sync — G22 needs `0053` live, which needs all of the above first.

Validation: `/admin/health` should report green across every dimension after step 3; any red dimension indicates a migration or env-var mismatch from one of the merge-storm PRs.

---

## New surface area on main the next agent should know exists

Several pieces intersect the G23/G24/G25 bundle the G22 handoff points to next:

- **MCP tokens** (#370): `backend/models/mcp_token.py`, `backend/mcp/tools/portfolio.py`. If G23 exposes historical-import status over an API, consider whether MCP needs read access too. The security fix-up during the session added `Position.quantity > 0` + `SecurityType.STOCK` filters to `get_holdings()` and a `user_id` filter to `get_recent_explanations()`; don't regress either.
- **Multi-tenant rate limits** (#377): every new route should be checked against `TenantRateLimit` enforcement. G23's bulk-upload / CSV-import endpoints are high-cardinality and will need explicit limits.
- **GDPR export/delete** (#377): any new table G23/G24/G25 adds (`historical_import_run`, per-account strategy overrides, etc.) must be added to the GDPR walker in `backend/tasks/multitenant/gdpr.py` — otherwise rows leak on account deletion.
- **OAuth broker foundation** (#379): the IBKR path stays FlexQuery-based, but E*TRADE / Schwab / Fidelity / Tasty adapters landing on top of #379 will populate accounts via OAuth. G25's auto-discovery should derive `account_type` from whichever source is authoritative — Flex XML `accountType` for IBKR, OAuth adapter metadata for others — and reconcile rather than overwrite.
- **Trade Decision Explainer** (#376): reads `MarketSnapshot` + `MarketRegime` at-or-before each order's timestamp. G23's historical backfill will populate older orders; the explainer's Beat task (`explain_recent_trades`) only looks at the past 24h, so historical orders won't auto-explain. Fine, but worth flagging so the founder isn't surprised only recent trades have "Why?" buttons.

---

## Delegation pattern that worked (save tokens next sprint)

The merge-storm used `composer-2-fast` subagents for mechanical work and Opus for sequencing + math. What actually worked:

### Fast subagents did well on

Keep-both-additive conflicts in: `backend/models/__init__.py`, `backend/api/main.py`, `backend/api/routes/__init__.py`, `frontend/src/App.tsx`, `frontend/src/services/api.ts`, `frontend/src/components/layout/DashboardLayout.tsx`, `backend/tasks/celery_app.py`, `backend/tasks/job_catalog.py`.

Rule that works: **"keep both sides of every conflict block; dedupe only on exact-string line match."** Give the subagent: (a) the worktree path, (b) the branch name, (c) the list of files likely to conflict, (d) the keep-both rule spelled out. Don't let them invent cross-cutting refactors to "clean up the conflict" — that's where they go off-piste.

### Fast subagents failed on

- **Alembic chain reshuffling.** They kept re-pointing `down_revision` to stale heads because they didn't re-fetch `origin/main` before computing. Opus had to hand the subagent the target `down_revision` value explicitly (`git show origin/main:<path> | grep -E "^revision|^down_revision"`).
- **Semantic (non-additive) conflicts.** Anything where both sides edited the same logical block (not just adjacent additions) needed human judgement.

### Opus cost was best spent on

1. Computing the current alembic head after each merge.
2. Catching revision-number collisions before they hit CI (two in this session — see the chain section above).
3. Diagnosing flaky-test root causes. The `test_market_data_backfill_service.py` failures turned out to be live `yfinance.get_fundamentals_info` calls bypassing earlier mocks — fixed in PR #381 with an `autouse=True` fixture patching the bound instance method. That diagnostic required reading the test fixture tree carefully; a fast model would have slapped `@pytest.mark.flaky` on it and moved on.

### Auto-merge vs orchestrator

`gh pr merge --auto --squash --delete-branch` + GitHub's native merge queue did most of the sequencing work once each PR was MERGEABLE. Arming auto-merge on 4 PRs in parallel and letting GitHub serialize them is **dramatically cheaper** than a custom cascade-merge orchestrator script (we tried both; auto-merge won). Use the orchestrator pattern only when you need to coordinate cross-repo merges or enforce a custom order that GitHub's queue doesn't know about.

---

## Iron Laws that got enforced in-session (don't regress)

Fixes landed in-session for various Copilot comments; the specific regressions worth watching:

- **`backend/mcp/tools/portfolio.py` — `get_holdings()`**: added `Position.quantity > 0` + `Position.security_type == SecurityType.STOCK` filters so the MCP endpoint doesn't return closed positions or options to an agent that asked for "holdings."
- **`backend/mcp/tools/portfolio.py` — `get_recent_explanations()`**: added `AutoOpsExplanation.user_id == user_id` filter; without it the MCP tool was cross-tenant-leaking explanations.
- **`backend/services/backtest/monte_carlo.py`**: added defensive input validation + Decimal coercion; the earlier version took floats and returned floats silently (Iron Law violation — monetary values are Decimal).
- **`backend/tests/backtest/test_walk_forward.py`**: `UserRole.USER` → `UserRole.VIEWER` (the enum member is `VIEWER`, not `USER`).
- **`backend/services/data_quality/quorum_service.py`**: inverted `QuorumStatus.DISAGREEMENT` vs `QuorumStatus.QUORUM_REACHED` — the earlier logic returned disagreement when quorum was reached.
- **`backend/models/symbol_master.py` + its migration**: `JSON` → `JSONB` for `old_value` / `new_value` on `SymbolHistory`; Postgres `JSON` doesn't support `=` which broke RLS-adjacent queries.
- **`WalkForwardStatus` enum + SQLAlchemy binding**: Python enum values set to lowercase to match the Postgres enum type; SQLAlchemy column configured with `values_callable=lambda x: [e.value for e in x]`.

---

## What's stale in the transcript reference

The G22 handoff references an earlier Opus instance's transcript UUID `9a2b88fd-…` (the 12-hour strategy thread). This session's transcript UUID is `b27538e2-015c-4160-ac22-397505132008`. Both are local-only under `agent-transcripts/`, not in the repo, per D121. Treat both as local references; neither is shareable across machines.

---

## Carry-forward additions for the next chat

Append to the G22 handoff's carry-forward prompt:

```
Also read docs/handoffs/2026-04-20-midnight-merge-storm.md. Key items:

- 5 feature PRs (#370, #373, #377, #379, #376) shipped to main between 19:30
  and 20:50 UTC on 2026-04-20 and are stuck behind the same deploy break as
  G22. When prod unblocks, first successful deploy ships 11 migrations and
  ~5 PRs of code simultaneously — stage the restart per that doc.

- Render's build_failed streak started at 19:48 UTC — the same minute #377
  (multi-tenant hardening) squash-merged. Before accepting the billing-only
  diagnosis, read the Render build logs for the first two failed deploys.
  If the logs show a stack trace instead of queue rejection, revert-bisect
  #377 → #379 → #376.

- G25's account_type auto-discovery should reconcile Flex XML accountType
  (IBKR) with OAuth adapter metadata (E*TRADE / Schwab / Tasty) rather than
  overwrite. The OAuth foundation (#379) is already on main.

- Any new table G23/G24/G25 adds must be registered with the GDPR walker in
  backend/tasks/multitenant/gdpr.py or it will leak on account deletion.

- #353 (Dependabot 17-package frontend bump) is still open; the auto-merge
  workflow is failing. Close and reopen in smaller batches, or fix the
  workflow, before resuming feature work.
```
