# Session Handoff — 2026-04-21

> **For the next chat (Claude Opus or any successor)**: read this file end-to-end before doing anything else. It captures *why* the work matters, not just *what* shipped, so you can resume with the same conviction the founder and the previous Opus instance built up over a 12+ hour deep-dive session.

---

## CRITICAL — read before any prod-touching work (added 2026-04-20 23:50 PT)

**Prod deploys have been silently broken for 8+ hours.** Every Render deploy from 2026-04-20 19:48 UTC through 03:10 UTC the next day has status `build_failed` with `finishedAt - createdAt ≈ 1–2s` — i.e. the build never started; Render rejected it at queue time (billing / build-minutes / account-state issue, NOT a code defect). This means:

- `main` is at `b65a695c` but prod API + worker are both stuck on `261349ad` (PR #373, walk-forward optimizer from 19:41 UTC yesterday).
- **G22 is NOT live in prod yet.** Prod alembic is at `0046`; migration `0053` has not run. The `account_syncs.warnings / expected_sections / received_sections / missing_sections / section_row_counts` columns do not exist in the prod schema.
- Any IBKR sync that runs in prod right now uses pre-G22 code and will silently mark `SUCCESS` with empty data — the exact bug G22 was built to kill.
- PRs #353, #376, #382, #383, #384, plus OAuth foundation and multi-tenant rate-limits commits are all stuck behind this.

**Action required before doing anything else:**

1. Founder checks `https://dashboard.render.com/billing` for payment / build-minutes issues and clears the block.
2. Push any no-op commit to `main` (or trigger a manual "Deploy latest commit" from the Render dashboard on both `axiomfolio-api` and `axiomfolio-worker`) to re-queue the build.
3. Verify `main` lands: `curl https://axiomfolio-api.onrender.com/health` should return the new build's SHA once deploy completes; `alembic current` must be `0053`.
4. Only then is G22 actually enforcing completeness in prod. Until then, the yellow PARTIAL badge + `last_sync_completeness` response field are still in code-only state.

**Never again**: merging to `main` + green CI is not equivalent to "shipped in prod." `.cursor/rules/production-verification.mdc` was correct; it was not operationally enforceable because nothing alarms when a deploy fails to start. **G28** in `docs/plans/GAPS_2026Q2.md` captures the fix (Beat job polling the Render API, `/admin/health` dimension, PR pre-merge assertion). **D120** in `KNOWLEDGE.md` codifies the decision.

---

## TL;DR — the 30-second pickup

- **G22 (sync completeness validation) is merged to main** as PR #383 (commit `ccedcf69`), but **not yet live in prod** — see the CRITICAL section above. Once prod deploys unblock, silent partial-success sync bugs become mathematically impossible: `BrokerAccount.sync_status` only says SUCCESS when every required FlexQuery section was present and every pipeline writer succeeded. PARTIAL is a first-class state with a yellow UI badge, structured warnings persisted to `account_syncs`, and a non-misleading message that surfaces both `missing_required` sections AND `pipeline_step_errored` writer failures.
- **All 14 Copilot review comments across PRs #382, #383, and #384 are resolved and merged.** PR #382 (gap docs G1–G27, decisions D113–D119) was already on main when the session started (commit `618f6db6`); the Copilot comments on it arrived post-merge and were addressed in follow-up PR #384 (`b0b29693`). PR #383 carried 3 backend comments addressed in commit `88e26ca8`.
- **The single biggest discovery this session is not a code bug — it is a product thesis pivot.** AxiomFolio is no longer "the discipline layer that prevents unrealized losses" (D113). It is "the **dual-mode return-maximization platform**" (D116) that does both — cuts losers via G14 (Position Health Auditor) AND scales winners at peaks via G15 (Peak/Profit-Taking Signal Engine), with G16 (Tax-Aware Exit) and G17 (Margin/Leverage Risk Surface) as load-bearing economic-reality engines. The founder's own portfolio (peak $1.85M on 2025-10-31, would have been ≥$2.4M with disciplined peak-scaling, currently $1.4M) is the canonical replay corpus per D118.
- **The next PR you should open is the G22→G23→G24→G25 bundle** — see "Next Up" below. The branch name is suggested: `feat/v1-phase-0-sync-correctness-g23-g24-g25`.
- **Do NOT touch any DANGER ZONE file** (see `.cursor/rules/protected-regions.mdc`) without explicit founder approval. The IBKR sync work is adjacent to but does not require modifying any protected file.

---

## What just shipped (last 24 hours)

| PR | Branch | Commit on main | Scope | Status |
|----|--------|----------------|-------|--------|
| **#382** | `feat/ibkr-multi-account-historical-import` | `618f6db6` | Docs only — `GAPS_2026Q2.md` (G1–G27), `KNOWLEDGE.md` (D113–D119), `MASTER_PLAN_2026.md` (Phase 2 trajectory widget). Pre-session merge by founder. | merged |
| **#383** | `feat/v1-g22-sync-completeness-validation` | `ccedcf69` | G22 — IBKR FlexQuery sync completeness validation end-to-end (validator module, migration `0053`, model JSON columns, pipeline integration, broker_sync_service status mapping, Celery task persistence, API exposure, UI yellow PARTIAL badge). 49 tests passed, 1 skipped, 0 failed. | merged |
| **#384** | `docs/copilot-review-d113-d119-emoji-cleanup` | `b0b29693` | Post-merge Copilot doc cleanup for #382 (decision-row reorder, emoji → text, [sic] markers, MASTER_PLAN companion-line reformat). | merged |

### Files added on main in this session (G22 only)

```
backend/services/portfolio/ibkr/sync_validator.py   (NEW — 250 lines, no DB, pure XML→CompletenessReport)
backend/alembic/versions/0053_add_account_sync_completeness.py  (NEW)
backend/tests/test_ibkr_sync_completeness.py        (NEW — 23 tests)
```

### Files modified on main in this session (G22 only)

```
backend/models/broker_account.py            (+5 JSON columns on AccountSync)
backend/services/portfolio/ibkr/pipeline.py (validate_completeness call + status branching)
backend/services/portfolio/broker_sync_service.py (PARTIAL handling + _build_partial_sync_message helper)
backend/tasks/portfolio/sync.py             (persist completeness payload + use shared helper)
backend/api/routes/settings/account.py      (expose last_sync_completeness on /sync-status)
frontend/src/pages/SettingsConnections.tsx  (yellow PARTIAL badge with tooltip)
```

---

## The strategic context you need (read this before coding)

The previous Opus instance and the founder spent ~12 hours together unwinding the AxiomFolio thesis from first principles using the founder's own portfolio as the live test case. The transcript is at `/Users/axiomfolio/.cursor/projects/Users-axiomfolio-development-axiomfolio/agent-transcripts/9a2b88fd-d11a-4577-b702-cd3b00951c16/9a2b88fd-d11a-4577-b702-cd3b00951c16.jsonl` if you want to read the original conversation. The cliff notes:

### The founder's profile (calibrate every recommendation against this)

- **High-net-worth Bay Area couple, ~$1M/yr W-2 income**, top federal + CA tax brackets. Tax friction is the dominant cost on every realized gain in taxable accounts; tax-deferred accounts (IRA) are where rapid trading lives.
- **Two brokers**: Schwab (long-term equity sleeve — AMZN, GOOGL, GOOG held "forever due to tax reason") + IBKR (active short-term sleeve, options, leverage).
- **Two IBKR accounts under one Flex Query**: `U15891532` (Traditional IRA, primary tax-sheltered active sleeve) and `U19490886` (Joint Taxable, primary). Only one is currently being detected by our sync (G25).
- **Self-identified failure mode**: "inability to close when winning" (founder's own words on 2026-04-20). 191 unique symbols, 1666 trades, peak $1.85M → current $1.4M = $450k of unrealized gains evaporated. This is the explicit acceptance criterion for G15 (G26).
- **Available margin**: $1.67M. Total buying power ~$3.07M at ~2x leverage. Founder asserts $3M year-end is reachable; D119 codifies the discipline-bounded counter — unleveraged $1.95M–$2.5M, with-leverage $2.5M–$3.0M, speculative-aggressive $3.0M–$3.5M, and beyond $3.5M = breaks discipline regardless of leverage. **$4M = lottery, not a plannable target.**
- **Founder explicitly chose higher volatility for higher expected return**. Do not try to convince them to allocate to index funds. The product's job is to manage that volatility responsibly, not to preach it down.

### The product thesis (D116)

AxiomFolio is the **dual-mode return-maximization platform** that:

1. Cuts losers via **G14 — Position Health Auditor**
2. Scales winners at peaks via **G15 — Peak/Profit-Taking Signal Engine**
3. Eliminates the tax-deferral friction in (1) and (2) via **G16 — Tax-Aware Exit Calculator**
4. Caps portfolio leverage per market regime via **G17 — Margin/Leverage Risk Surface**
5. Supports both Active-trading and Conviction-holding modes per position via **G18 — Two-Mode Sleeve System**
6. Feeds multi-year buy/hold ideas into the Conviction sleeve via **G19 — Conviction Pick Generator**

Success metric: **alpha vs SPY at the user's chosen volatility**, not Sharpe-maximization.

Anti-goal: another robo-advisor recommending boring index funds.

### The acceptance corpus (D118)

The founder's portfolio is the canonical replay corpus for every engine in the discipline-layer family (G14 / G15 / G16). Every PR that touches one of those engines must include a CI replay test that fails the build if the new version regresses real-world counterfactual P&L vs the prior version on the founder corpus. **G23 (historical XML/CSV backfill) is a hard prerequisite** because without it we don't have the corpus to replay against.

### The 27 gaps and where they live

Full spec: `docs/plans/GAPS_2026Q2.md` (1668 lines). The numbering is stable; never renumber. Severity:

- **P0 (must ship before v1)**: G1, G2, G3, G4, G6, G7, G9, G10, G14, G15, G16, G17, G18, G22 (done), G24, G25, G26
- **P1 (v1.5)**: G5, G8, G11, G12, G13, G19, G20, G21, G23, G27
- **P2 (v2)**: nothing yet

---

## Immediate next work — `feat/v1-phase-0-sync-correctness-g23-g24-g25`

The user wants you to bundle G23 + G24 + G25 into a single PR because they're co-dependent and they all unblock the founder-portfolio replay (G21) which unlocks G14 / G15 evaluation. Don't ship G27 in this PR — wait until G24/G25 land.

### G23 — Historical Data Backfill / Multi-Period Sync (P1, but bumped to Phase 0 because corpus-blocker)

**What**: Today's IBKR sync only fetches the configured Flex Query period (typically Last 365 Days or YTD). The founder has 5+ years of pre-AxiomFolio history that we need imported once for the replay corpus. IBKR Flex Web Service caps each request at 365 days, so multi-year imports require chunked requests.

**Architecture**:

- New `IBKRHistoricalImporter` service in `backend/services/portfolio/ibkr/historical_import.py`
- Accepts a date range, chunks it into ≤365-day windows, calls Flex Web Service `SendRequest` with `&fd=YYYYMMDD&td=YYYYMMDD` per chunk, polls `GetStatement`, deduplicates rows by Flex's natural keys (TradeID, ConID+date for positions, transactionID for cash), persists.
- New `POST /api/v1/accounts/{id}/historical-import` route that accepts `{from_date, to_date}` and dispatches a Celery task `backend.tasks.portfolio.historical_import.run_historical_import`.
- New UI wizard at `/settings/connections/{id}/import-history`: date picker, progress bar streaming chunk-by-chunk status from the Celery task, post-completion summary showing row counts per section.
- **Also accept CSV files** (per founder's local CSVs `U15891532_*.csv`, `U19490886_*.csv`): `POST /api/v1/accounts/{id}/historical-import-csv` multipart endpoint. Same downstream pipeline; CSV parser produces the same row dicts the XML parser does.
- **Track import history**: new `historical_import_run` table (id, account_id, started_at, completed_at, from_date, to_date, source ∈ {flex_xml, csv_upload}, chunks_attempted, chunks_succeeded, rows_imported, rows_deduplicated, status, warnings_json).

**Acceptance criteria**:

1. Founder can import 2024-10-15 → 2025-07-22 for `U15891532` via the UI wizard (the actual range of the local CSV they shared).
2. Re-running the same import is idempotent (zero net new rows the second time).
3. The replay harness (G21, future) can `SELECT * FROM trades WHERE account_id = X AND execution_time BETWEEN ...` and get every trade.
4. Partial failures (one chunk errored mid-import) leave a clean state — succeeded chunks committed, failed chunk surfaced in the wizard, retry button re-runs only the failed chunk.

**No-silent-fallback enforcement**: if any chunk returns 0 rows AND the validator's `expected_sections` are missing, surface as PARTIAL on the import run (not the account sync). Reuse `_build_partial_sync_message` helper from G22.

### G24 — Account-Type-Aware Strategy Logic (P0)

**What**: The system currently treats every account the same. The founder's IRA and Joint Taxable need different exit logic (no wash-sale on IRA, no LTCG/STCG distinction on IRA, no tax-loss-harvesting in IRA). The `AccountType` enum already supports `IRA / ROTH_IRA / TAXABLE / HSA / TRUST / BUSINESS` (verified in `backend/models/broker_account.py`); the gap is everything downstream that ignores it.

**Architecture**:

- New `backend/services/strategy/account_strategy.py` module exposing `get_strategy_profile(account: BrokerAccount) -> AccountStrategyProfile`.
- `AccountStrategyProfile` is a frozen dataclass with: `tax_lot_method` (FIFO / SpecID), `wash_sale_aware` (bool), `harvest_losses` (bool), `prefer_long_term_holds` (bool), `default_holding_horizon_days` (int).
- Defaults per account type (IRA → no wash sale, no LTCG distinction, harvest=False, horizon=any; TAXABLE → wash sale aware, harvest=True, prefer LTCG); founder can override per account in settings (precursor to G27).
- Wire into G14 (Position Health Auditor), G16 (Tax-Aware Exit Calculator), and the Risk Gate's "before suggesting exit" check.

**Acceptance criteria**:

1. `get_strategy_profile(ira_account).wash_sale_aware == False`.
2. `get_strategy_profile(taxable_account).wash_sale_aware == True`.
3. G16's "should we wait N days for LTCG?" question returns False unconditionally for IRA.
4. Cross-tenant isolation test: User A's IRA strategy profile cannot leak into User B's request.

### G25 — Broker Account Auto-Discovery & Metadata Detection (P0)

**What**: The founder has two IBKR accounts under one Flex Query but our sync only detected `U15891532` and tagged it as TAXABLE (it's actually a Traditional IRA). The Flex Query XML's `AccountInformation` section includes `accountType` and `customerType` fields we're ignoring.

**Architecture**:

- Extend `IBKRSyncService.sync_account_comprehensive` to scan the XML's `<FlexStatement accountId="...">` blocks. For each unique `accountId` found that isn't already a `BrokerAccount` row for this user, create one — and read `<AccountInformation accountType="..." customerType="..."/>` to set the correct `AccountType` enum value.
- IBKR's `accountType` values are documented (Individual, Joint, IRA-Roth, IRA-Traditional, IRA-SEP, Trust, Corporate, ...) — map to our enum in a small lookup table.
- For accounts already existing but with the wrong `account_type`, log a warning at sync time and surface in `/admin/health` (do NOT silently overwrite — the founder may have manually set it for a reason).

**Acceptance criteria**:

1. Re-running the founder's IBKR sync auto-creates `U19490886` as TAXABLE (Joint).
2. `U15891532` gets a `WARNING: account_type DB=TAXABLE, broker=IRA-Traditional, no auto-update — set manually if intended` warning surfaced in the sync's `warnings` JSON column (G22 plumbing already in place).
3. Cross-tenant: a malicious user adding their own Flex Query that contains another user's account ID does not auto-create a `BrokerAccount` row for the wrong user — the auto-create is gated on the credential being explicitly added by `current_user`.

### Why bundle G23 + G24 + G25 together

- G23 imports historical data; G25 ensures the historical data lands in the correct account; G24 ensures the historical data is interpreted with the correct tax/strategy logic. Shipping them piecemeal would mean intermediate states where the founder's data is partially wrong — exactly the silent-degradation class of bug we're trying to eliminate.
- Combined PR is medium-large (est. ~1500 LOC + tests). If that's too big, split into two: (G23) and (G24+G25).

---

## IBKR Gateway in production — the specific hardcoding

**Founder asked**: "my ibkr gateway how do i connect to that in prod? its opening localhost - is that hardcoded somewhere - wtf?"

**Answer**: Yes, it's hardcoded in `backend/config.py:100`:

```python
IBKR_HOST: str = "127.0.0.1"
IBKR_PORT: int = 7497
```

And `render.yaml` does NOT override these — so the production API container literally tries to TCP-connect to its own loopback on port 7497, where nothing is listening. This is why every Gateway-dependent feature in prod opens "localhost" — it's the API service trying (and failing) to talk to a TWS/IB-Gateway that exists only on the founder's laptop.

### Three architectural options (escalating cost / capability)

1. **Status quo — Gateway is dev-only.** Keep `IBKR_HOST=127.0.0.1` in dev. In prod, every Gateway-dependent feature returns "Gateway unavailable in this environment". Real-time positions / order placement work only when the founder is at their laptop with TWS or IB Gateway running, talking to a localhost-tunnelled or VPN-bridged backend. **Cost**: zero. **Capability**: founder cannot place orders from mobile or from a different computer.

2. **Self-hosted IB Gateway container on Render** — add a new Render `worker` service running `ghcr.io/extrange/ibkr-docker` (or `IBC` + IB Gateway in a single container with auto-2FA via TOTP). Set `IBKR_HOST` env var on the API service to the Gateway service's internal Render hostname (Render private networking). **Cost**: ~$25/month for the Gateway container, plus the operational burden of keeping IB's nightly server reset (Sunday 23:45 ET) from killing the container, plus 2FA secrets to rotate. **Capability**: real-time positions and order placement work from anywhere the founder logs into AxiomFolio.

3. **IBKR Client Portal Web API (no Gateway)** — IBKR's REST API alternative to TWS sockets. Token-based auth, no Gateway process needed. **Cost**: app rewrite of `backend/services/clients/ibkr_client.py` (~600 LOC, all the `IB().connect()` paths replaced with `httpx` calls). **Capability**: cleanest long-term — no Gateway babysitting at all. But it's a nontrivial migration.

The founder's current IBKR Watchdog gate (`backend/tasks/ops/ibkr_watchdog.py`) and the Risk Gate's `paper-shadow` mode are already designed to gracefully refuse trading when the Gateway isn't reachable — i.e., option 1 is already implemented as the default and is safe. **The actual bug is that the UI doesn't communicate "Gateway unavailable in prod" to the user; it just silently fails the call.** That's a P1 UI fix worth doing in the Phase 0 bundle: render a clear "Gateway is dev-only in this environment — order placement disabled until founder connects via VPN" badge wherever Gateway-dependent UI lives.

---

## FlexQuery API — what we can and cannot automate

**Founder asked**: "can you create flexqueries? that would be fire"

**Answer**: No, sadly — the IBKR Flex Web Service API is read-only with respect to the queries themselves. From IBKR's official docs (last updated 2025-10-03):

> "Flex Queries are first constructed manually as templates in Client Portal, after which the Flex Web Service API is used to generate an instance of a report populated with up-to-date data and deliver it back to the requesting client."

The only two API endpoints are `SendRequest` (run a query by ID) and `GetStatement` (fetch result). There is no `CreateQuery`, `UpdateQuery`, `AddSection`, etc. The founder must configure queries in IBKR Client Portal → Performance & Reports → Flex Queries → Activity Flex Query.

**What we CAN automate** (and should, in a follow-up PR after G22 catches the missing sections):

- **G22 already detects which sections are missing** and now surfaces it in `account_syncs.warnings` and the UI yellow PARTIAL badge.
- **Wizard upgrade**: when the system detects a missing required section in the founder's Flex Query, render a "Fix your Flex Query" wizard with screenshot-by-screenshot instructions for adding that exact section. The instructions live in `IBKRFlexQueryClient.get_setup_instructions()` (already exists in `backend/services/clients/ibkr_flexquery_client.py`); we just need to surface them contextually in the UI when G22 detects a gap.

### What the founder needs to do RIGHT NOW for the failing IBKR sync

**Corrected 2026-04-20 23:50 PT:** An earlier draft of this doc claimed the founder's Flex Query (ID `1331520`) was missing required sections. **That claim was wrong** — the founder's screenshot of the live query config shows every section G22's validator requires, plus all three optional ones, plus bonus sections (Change in NAV, Change in Dividend Accruals, Incoming/Outgoing Trade Transfers, Transaction Fees). The real cause of the PARTIAL-looking sync was NOT a Flex Query gap; it was that **G22 itself had not deployed to prod** (see the CRITICAL section at the top of this doc). The sync was running on pre-G22 code that couldn't set PARTIAL in the first place — it was the old silent-empty-SUCCESS bug.

**Verified inventory of founder's Flex Query 1331520 (as of 2026-04-20 screenshot):**

| Section | Required by G22? | Present? |
|---------|------------------|----------|
| Account Information | yes | yes |
| Open Positions (Summary + Lot) | yes | yes |
| Trades (incl. Closed Lots + Wash Sales) | yes | yes |
| Cash Transactions | yes | yes |
| Transfers | optional | yes |
| Interest Accruals | optional | yes |
| Option Exercises, Assignments and Expirations | optional | yes |
| Change in NAV | bonus | yes |
| Change in Dividend Accruals | bonus | yes |
| Incoming/Outgoing Trade Transfers | bonus | yes |
| Transaction Fees | bonus | yes |
| Delivery: accounts `U19490886, U15891532`, XML, last 365 days | — | correct |

**Actual action required:**

1. Unblock the prod deploy pipeline first (CRITICAL section at top).
2. Once prod is on a post-`ccedcf69` SHA with alembic `0053`, trigger a re-sync from `/settings/connections`.
3. With G22 live, the sync will write one of: `SUCCESS` (if every section present AND every writer wrote rows), `PARTIAL` (with exact missing/errored/empty-section names in `account_syncs.warnings`), or `ERROR`. No silent SUCCESS is possible.
4. If PARTIAL, the `last_sync_completeness` payload on `/accounts/{id}/sync-status` will list exactly which section was missing or errored — no LLM inference required. Paste that JSON into the next chat if you need help interpreting it.

### Should the founder delete and reconnect?

**No, not necessary, and actively harmful right now:**

- The sync badge is not failing because of a Flex Query / credentials issue — it's failing because G22 code isn't deployed yet. Reconnecting would not help.
- Reconnecting *would* destroy (a) the `BrokerAccount` row's currently-set `account_type` (which is incorrectly `TAXABLE` for the IRA — G24/G25 will fix this properly via broker-reported metadata detection, not via re-onboarding); (b) the `AccountSync` history (the diagnostic rows help us audit the G22 rollout).

**Best action: wait for prod deploy to unblock, then trigger one re-sync. If that sync is PARTIAL with a structured warnings payload, we'll fix forward.**

---

## How to verify the prod state in 60 seconds (post-merge — AND post-deploy-unblock)

**Step 0 (new, do this FIRST every single time):** verify prod is actually on a post-merge SHA before running the rest of this recipe. If the `axiomfolio-api` and `axiomfolio-worker` services are not both on a SHA at-or-after the commit you just merged, STOP — the rest of this recipe will report false failures because the code isn't live.

```bash
# Render API: latest deploy per prod service (requires RENDER_API_KEY)
for svc in srv-d64mkqi4d50c73eite20 srv-d64mkqi4d50c73eite10 srv-d7hpo2v7f7vs738o9p80; do
  curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
    "https://api.render.com/v1/services/$svc/deploys?limit=1" \
    | jq -r ".[0] | \"$svc  \\(.status)  \\(.commit.id[0:8])  created=\\(.createdAt)  finished=\\(.finishedAt)\""
done
# Each service must show status=live on the target SHA. If status=build_failed
# with finishedAt within 2s of createdAt, see the CRITICAL section at top.

# Confirm prod alembic has applied 0053 (only after deploy is live)
source infra/env.prod
psql "$RENDER_DB_EXTERNAL_URL" -c "SELECT version_num FROM alembic_version;"
# Must be >= 0053 for G22 to be enforcing.

# Check the new account_syncs columns exist
psql "$RENDER_DB_EXTERNAL_URL" -c "\d account_syncs" | grep -E "warnings|expected_sections|received_sections|missing_sections|section_row_counts"
# All 5 must be present.

# After founder triggers a re-sync via the UI, inspect the latest sync's completeness
psql "$RENDER_DB_EXTERNAL_URL" -c "SELECT id, status, missing_sections, section_row_counts, started_at FROM account_syncs ORDER BY started_at DESC LIMIT 3;"
```

**If step 0 shows `build_failed` for the latest deploy and prod is behind `main`:** the deploy pipeline is broken (see the CRITICAL section). Fix that first; all other checks will lie until it's fixed.

---

## Constraints you must honour (from the always-applied workspace rules)

- **No silent fallbacks** — `.cursor/rules/no-silent-fallback.mdc`. G22 was specifically designed to enforce this; don't undo it. Counter-intuitive corollary: NEVER bump `last_successful_sync` on a degraded sync (the Copilot review on PR #383 caught this exact bug already).
- **Plan mode first** for anything touching >2 files, danger zones, models, routes, Celery tasks, billing, auth, multi-tenancy, risk gate, or indicator math. G23+G24+G25 will trip this — write a 60-second plan first.
- **Multi-tenancy enforcement** — every new route accepts `current_user`, every new service accepts `user_id`, every new task derives `user_id` from job context. Cross-tenant test required for every new route.
- **No emojis anywhere** — repo-wide rule per `MASTER_PLAN_2026.md:66`. Use `OK` / `(warning)` / text labels. The 11 Copilot comments on PR #382 were all about this; don't reintroduce.
- **No hallucinated UI labels** — `.cursor/rules/no-hallucinated-ui-labels.mdc`. Read the actual JSX before writing user-facing references. The button labelled "Sync Now" might actually be "Refresh Account" — verify.
- **DANGER ZONE files require explicit approval** — `.cursor/rules/protected-regions.mdc`. The G23/G24/G25 work does NOT need to touch any danger zone file. If you find yourself reaching for `risk_gate.py` or `indicator_engine.py`, stop and re-read your plan.
- **Founder financial data is committed to the public repo as of this writing.** The founder explicitly accepted this trade-off (CI minutes vs privacy) and plans to make the repo private later. Do not delete those files; do not push more sensitive files. Treat the existing exposure as a known accepted risk.

---

## Carry-forward prompt (paste this into the new chat)

```
Continue work on AxiomFolio. Read docs/handoffs/2026-04-21-g22-shipped-next-g23.md
end-to-end before doing anything else — it captures the full session context,
including the CRITICAL deploy-pipeline-broken section at the top of that doc.

Currently on main:
- G22 (sync completeness validation) merged as PR #383; Copilot comments
  addressed; post-merge doc cleanup landed as PR #384.
- Decision log current through D121 (added D120 deploy-health + D121 evidence-
  based diagnosis at session end).
- Gap log current through G28 (added G28 deploy-health telemetry + validator-
  specific PARTIAL messaging at session end).

BUT: Prod was not accepting Render deploys for 8+ hours at session end —
every deploy since PR #373 showed status=build_failed with finishedAt ~1s
after createdAt, meaning Render rejected the build at queue time (billing
or build-minutes, NOT a code issue). G22 is NOT live in prod at session
end; prod alembic is at 0046, not 0053. Step 0 of any prod work is to
confirm the founder has cleared the Render block and both axiomfolio-api
and axiomfolio-worker show status=live on the latest main SHA. Until then,
every IBKR sync in prod runs on pre-G22 code and will silently mark SUCCESS
with empty data. See the recipe in the handoff doc under "How to verify
the prod state in 60 seconds."

Next code work (only after prod deploys unblock): open PR
feat/v1-phase-0-sync-correctness-g23-g24-g25 implementing G23 (historical
XML/CSV backfill), G24 (account-type-aware strategy logic), G25 (broker
account auto-discovery + metadata detection). Bundle them because they are
co-dependent and they unblock G21 (founder portfolio replay corpus) which
gates G14 / G15 evaluation.

Parallel infra work (independent of G23/G24/G25): G28 deploy-health
telemetry + validator-specific PARTIAL messaging. This is P0 because
without it, the deploy-silence failure mode repeats next time. Small
scope, no DANGER ZONE touches, can be opened as a separate PR in parallel.

Acceptance criteria for G23/G24/G25 are in docs/handoffs/2026-04-21-g22-
shipped-next-g23.md sections "G23", "G24", "G25". Acceptance criteria for
G28 are in docs/plans/GAPS_2026Q2.md G28 section.

Use plan mode first. Write the plan, get founder approval, then execute.
Tests required: replay-corpus integration test for G23, cross-tenant
isolation tests for G24 and G25, no-silent-fallback regression test for
G23 partial-import case (reuse _build_partial_sync_message helper from G22),
deploy-health mock test for G28 that replays the 2026-04-20 two-consecutive-
build_failed scenario.

Diagnostic discipline (D121): before claiming any user-facing config is
"missing X", read the actual config (screenshot / XML / API response) or
scope the claim as a hypothesis. The previous Opus incorrectly told the
founder their Flex Query was missing sections — it was not. The real cause
was the deploy pipeline, not the Flex Query. Do not repeat.

Constraints: no DANGER ZONE file edits, no emojis, multi-tenancy enforced,
no silent fallbacks. Start with a clean slate.
```

---

## Open follow-ups not bundled in next PR

- **G27 (Per-Account Risk Profile)** — ships Phase 1 after G24/G25 land.
- **Gateway-in-prod UI badge** — small UX fix to surface "Gateway unavailable in this environment" when an order-placement attempt would otherwise silently fail. Can be a 1-file PR alongside the Phase 0 bundle.
- **Render Postgres backup automation** — `scripts/backup_db.sh` exists but isn't scheduled. Worth a Beat job for nightly backups before G14/G15 start writing replay-corpus rows.
- **Repo privacy** — founder plans to flip to private "later"; no action needed from the agent.
