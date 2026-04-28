---
owner: trading
last_reviewed: 2026-04-22
doc_kind: plan
domain: data
status: active
---
# G5 — Implied Volatility / IV-Rank Surface (Free-Providers First)

> Wires the empty IV pipeline to free providers first (Yahoo + IBKR Gateway) and defers the paid-provider decision until after 30 days of coverage measurement. Resolves R-IV01 (silent-zero in Options tab) and the explicit NOOP in `app/tasks/market/iv.py`.

## Positive surprise from the audit

The data model, the IV-rank helper, and the `compute_iv_rank` task all already exist. The ONLY gap is the ingest — the task that's supposed to write `HistoricalIV` rows is an explicit NOOP.

**Already in place:**

- Model: [`app/models/historical_iv.py`](../../app/models/historical_iv.py) — columns `iv_30d`, `iv_60d`, `iv_rank_252`, `iv_high_252`, `iv_low_252`, `hv_20d`, `hv_60d`, `iv_hv_spread`.
- Contract-level model: [`app/models/market/options_chain_snapshot.py`](../../app/models/market/options_chain_snapshot.py) lines 36-38 — `implied_vol`, `iv_pctile_1y`, `iv_rank_1y`.
- Ranking helper: [`app/services/gold/options_chain_surface.py`](../../app/services/gold/options_chain_surface.py) lines 120-139 — `_iv_percentile_rank`.
- Rank computation task: [`app/tasks/market/iv.py`](../../app/tasks/market/iv.py) `compute_rank` lines 39-111 — reads `HistoricalIV.iv_30d`, writes `iv_rank_252`, `iv_high_252`, `iv_low_252`, `iv_hv_spread`.
- IBKR option-chain API: [`app/services/clients/ibkr_client.py`](../../app/services/clients/ibkr_client.py) `get_option_chain` lines 433-501.
- Yahoo options helper: [`app/services/market/yfinance_options_chain.py`](../../app/services/market/yfinance_options_chain.py) (has `_parse_iv` at lines 40-48 that normalizes Yahoo's IV-as-fraction-or-percent into a `Decimal`).

**The actual gap:**

- [`app/tasks/market/iv.py`](../../app/tasks/market/iv.py) lines 22-32 — `snapshot_iv_from_gateway` is an explicit NOOP, so `HistoricalIV` is never populated and `compute_rank` operates on an empty series forever.
- `compute_rank` line 100: `latest.iv_hv_spread = current_iv - (latest.hv_20d or 0)` — silent-zero fallback if `hv_20d` is null. Must be fixed so spread is `None` when `hv_20d` is missing.
- [`frontend/src/pages/portfolio/PortfolioOptions.tsx`](../../frontend/src/pages/portfolio/PortfolioOptions.tsx) line 700: `accessor: (p) => Number(p.implied_volatility ?? 0)` — violates `.cursor/rules/no-silent-fallback.mdc`; must distinguish loading / error / absent / zero.

## Goal

A working IV/IV-rank surface for the tracked universe (watchlist + indexed symbols; approximately 500 symbols) using free providers only. Measure coverage for 30 days; if coverage < 95%, escalate to a separate plan for a paid provider (Polygon Options ~$29/mo or ORATS ~$250/mo). This plan does **not** add a paid provider.

## No new schema

`HistoricalIV` already has every column needed. Do not add migrations.

## Backend changes

### 1. New ingest helpers

[`app/services/market/historical_iv_service.py`](../../app/services/market/historical_iv_service.py) — new module:

```python
@dataclass
class IVSample:
    symbol: str
    date: date
    iv_30d: Optional[float]
    iv_60d: Optional[float]
    source: str  # "ibkr" | "yahoo"

def atm_iv_from_yahoo(symbol: str, as_of: date) -> Optional[IVSample]: ...
def atm_iv_from_ibkr(symbol: str, as_of: date) -> Optional[IVSample]: ...

def compute_hv(symbol: str, as_of: date, window: int, db: Session) -> Optional[float]:
    """Population stdev of log returns over `window` trading days,
    annualized with sqrt(252). Returns None if <window bars available.
    Reads from `price_bar` table."""

def persist_iv_sample(sample: IVSample, hv_20d: Optional[float], hv_60d: Optional[float], db: Session) -> None:
    """Upsert one HistoricalIV row for (symbol, date).
    iv_hv_spread = iv_30d - hv_20d when both present, else None.
    NEVER fall back to 0."""
```

Key design points:

- **HV math** uses **population** stdev (`ddof=0`) of **log returns**, annualized by `sqrt(252)`, matching the Stage Analysis indicator convention (same as D48 for Bollinger Bands).
- All functions return `Optional[float]`; callers must check None. No silent zero anywhere.
- Yahoo ATM lookup: fetch nearest-expiry option chain (≥7 DTE, ≤45 DTE preferred; skip if outside), pick the call+put pair with strike closest to spot, take the mid of their IVs. Reuse `_parse_iv` from [`app/services/market/yfinance_options_chain.py`](../../app/services/market/yfinance_options_chain.py) lines 40-48.
- IBKR ATM: use `ibkr_client.get_option_chain(symbol)` filtered to front-month; primary path when gateway is up.

### 2. Replace the NOOP

Rewrite [`app/tasks/market/iv.py`](../../app/tasks/market/iv.py) `sync_gateway`:

```python
@shared_task(soft_time_limit=600, time_limit=660)
@task_run("snapshot_iv_from_gateway")
def sync_gateway() -> dict:
    """Snapshot ATM IV for tracked symbols. IBKR primary, Yahoo fallback.
    Persist one HistoricalIV row per symbol per trading day.
    """
    session = SessionLocal()
    try:
        symbols = _tracked_symbols(session)  # from MarketSnapshot universe
        today = _last_trading_day()
        written, skipped_no_data, errors = 0, 0, 0

        for symbol in symbols:
            try:
                sample = atm_iv_from_ibkr(symbol, today) or atm_iv_from_yahoo(symbol, today)
                if sample is None:
                    skipped_no_data += 1
                    continue
                hv_20 = compute_hv(symbol, today, 20, session)
                hv_60 = compute_hv(symbol, today, 60, session)
                persist_iv_sample(sample, hv_20, hv_60, session)
                written += 1
            except Exception as e:
                errors += 1
                logger.warning("IV snapshot failed for %s: %s", symbol, e)

        session.commit()
        assert written + skipped_no_data + errors == len(symbols), "counter drift"
        logger.info(
            "IV snapshot: written=%d skipped_no_data=%d errors=%d",
            written, skipped_no_data, errors,
        )
        return {
            "status": "ok",
            "written": written,
            "skipped_no_data": skipped_no_data,
            "errors": errors,
            "total": len(symbols),
        }
    finally:
        session.close()
```

- Task timeout 660s per IRON LAW (`hard_time_limit == lock TTL ≥ soft_time_limit`).
- Per-symbol try/except pattern per `.cursor/rules/no-silent-fallback.mdc`.
- Structured counters + final `assert` prevent the R38-class silent loss.

### 3. Fix `compute_rank` silent-zero

In the same file, line 100: replace

```python
latest.iv_hv_spread = current_iv - (latest.hv_20d or 0)
```

with

```python
if latest.hv_20d is not None:
    latest.iv_hv_spread = current_iv - latest.hv_20d
else:
    latest.iv_hv_spread = None
```

### 4. Job catalog wiring

[`app/tasks/job_catalog.py`](../../app/tasks/job_catalog.py) — add `snapshot_iv_from_gateway` to the catalog:

- Cron: `30 21 * * 1-5` UTC (21:30 UTC = ~30 min after US equity close; weekdays only).
- Queue: `heavy` (per [`.cursor/rules/market-data-platform.mdc`](../../.cursor/rules/market-data-platform.mdc) jobs >5min go to `heavy`).
- `timeout_s: 660`. Matches Celery `hard_time_limit`.

Existing `compute_iv_rank` stays on its current schedule; it now has real data to operate on.

### 5. Scan engine IV-rank filter

[`app/services/market/scan_engine.py`](../../app/services/market/scan_engine.py) — add `iv_rank_252` as a selectable filter dimension. Reference implementation pattern: how `rs_mansfield` is currently plumbed (see R29 — it correctly skips symbols with `None` instead of coercing to 0).

Filter operators: `lt`, `lte`, `gt`, `gte`, `between`. When the user requests `iv_rank_252 < 20`, symbols with `iv_rank_252 IS NULL` are **excluded** from results, not treated as 0. Unit test asserts this.

### 6. Admin health

[`app/services/monitoring/admin_health_service.py`](../../app/services/monitoring/admin_health_service.py) — add an `iv_coverage` dimension:

- `tracked_symbols`
- `with_iv_30d_today`
- `with_hv_20d_today`
- `with_iv_rank_252`  — only populated after ≥20 trading days
- `coverage_pct_iv_30d = with_iv_30d_today / tracked_symbols`
- `source_breakdown: { "ibkr": n, "yahoo": n }`
- `last_successful_snapshot_at`

Dashboard threshold: `coverage_pct_iv_30d < 95%` after a 30-day warm-up window → emit a warning visible on `/admin/health` that reads **"IV coverage below 95% — consider paid provider (see docs/axiomfolio/plans/G5_IV_RANK_SURFACE.md)"**.

## Frontend changes

### 1. Fix silent-zero in Options tab

[`frontend/src/pages/portfolio/PortfolioOptions.tsx`](../../frontend/src/pages/portfolio/PortfolioOptions.tsx) line 700:

```tsx
accessor: (p) => Number(p.implied_volatility ?? 0),
```

Replace with explicit four-state rendering:

```tsx
accessor: (p) => {
  if (p.implied_volatility == null) return null;
  return Number(p.implied_volatility);
},
cell: ({ value, isLoading, isError }) => {
  if (isLoading) return <Skeleton className="h-4 w-12" />;
  if (isError) return <span className="text-muted-foreground">—</span>;
  if (value == null) return (
    <Tooltip content="IV unavailable from provider">
      <span className="text-muted-foreground">—</span>
    </Tooltip>
  );
  return `${(value * 100).toFixed(1)}%`;
},
```

(Exact TSX may differ depending on the existing cell helper; preserve the spirit: distinguish loading / error / absent / numeric.)

### 2. IV-rank columns in watchlist + scan

Wherever a symbol row is rendered (watchlist, scan results, market dashboard rows), add an optional **IV Rank** column sourced from `HistoricalIV.iv_rank_252`:

- During the warm-up window (<252 trading days of data), render **"N/A"** with an `<InfoTooltip>`: **"IV rank requires 1 year of history; ramping."**
- After warm-up, render as integer percentile `0-100`.
- Column hidden by default for users whose symbols have no options coverage (don't clutter equity-only watchlists).

Source of truth for rendering decisions: a new hook `useIvCoverage(symbol)` under `frontend/src/hooks/` that exposes `{ ivRank, hasRank, isRamping, source }`.

### 3. Strike-level IV display sanity check

Grep the options-chain rendering for any place that displays `iv_pctile_1y` or `iv_rank_1y` from `OptionsChainSnapshot`. Confirm it renders as a percentile (0-100) not as a ratio — and if a ratio is found, file a bug.

## New settings / config

`backend/config.py`:

- `IV_SNAPSHOT_UNIVERSE: Literal["tracked","watchlist","all_snapshots"] = "tracked"` — controls which symbols get snapshotted daily.
- `IV_SNAPSHOT_MAX_SYMBOLS: int = 1000` — safety cap; if the universe exceeds this, log a warning and truncate (documented in the code + privacy.md is unaffected).
- `YAHOO_IV_DTE_MIN: int = 7`
- `YAHOO_IV_DTE_MAX: int = 45`

## Tests

- `backend/tests/services/market/test_historical_iv_service.py` — HV math unit tests (known fixture: a 21-day synthetic price series with a known log-return stdev; assert match to 4 decimals). Yahoo + IBKR ATM picker tests with mocked chain responses.
- `backend/tests/tasks/market/test_iv_snapshot.py` — counter-loop correctness; Yahoo fallback when IBKR fails; assertion fires when counter drift simulated.
- `backend/tests/services/market/test_scan_engine_iv.py` — filter with `iv_rank_252 < 20` excludes null-rank symbols.
- `frontend/src/pages/portfolio/__tests__/PortfolioOptions.iv.test.tsx` — renders skeleton during loading, `—` with tooltip when IV absent, numeric with % when present.

## Acceptance

- **T+1 trading day after merge:** `HistoricalIV` populated for all tracked symbols; `iv_30d` present for ≥ 80% of tracked symbols that have listed options (hard 80% floor — below this, PR does not merge); `hv_20d` null (requires 20 days of price history, which will already exist for long-tracked names). `source_breakdown` shows IBKR as primary when gateway is up, Yahoo as fallback.
- **T+20 trading days:** `hv_20d` + `iv_hv_spread` stable for ≥ 95% of covered symbols.
- **T+252 trading days:** `iv_rank_252` populated; UI flips from "N/A" to numeric percentile automatically.
- Options tab IV column shows real values (IBKR primary, Yahoo fallback); `—` with tooltip when both providers fail (warning logged). No `$0.00` for missing IV.
- Scan engine exposes an IV-rank filter; null-symbol behavior is "exclude", not "treat as 0".
- `/admin/health` has an `iv_coverage` dimension with 6+ sub-metrics.
- Structured counters logged on every run; `written + skipped + errors == total` assertion passes.

## 30-day coverage gate (follow-up decision)

After 30 calendar days post-merge, founder (or Opus on request) reads `admin/health.iv_coverage.coverage_pct_iv_30d`:

- **≥ 95%** — free providers are sufficient; close the G5 loop; no paid provider needed.
- **85-95%** — acceptable for watchlist-size universes; paid provider optional; file a low-priority ticket.
- **< 85%** — escalate to a paid-provider evaluation (Polygon Options ~$29/mo vs ORATS ~$250/mo vs Tradier snapshot on an existing paid Tradier account post-Wave F1); record the decision in an ADR or ticket when this threshold trips.

**This plan does not prejudge the paid-provider decision.** The 30-day measurement is how we find out honestly.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Yahoo rate-limiting kicks in above ~500 symbols | `IV_SNAPSHOT_MAX_SYMBOLS` cap; IBKR primary when gateway available; add jitter between requests |
| IBKR gateway down for extended period | Yahoo fallback prevents single-provider outage blackout |
| Silent zero leaks back in | ReadLints + eslint rule + unit test asserting no `?? 0` against IV fields |
| Symbol universe drift (watchlist grows past cap) | `IV_SNAPSHOT_UNIVERSE` config lets us narrow to watchlist quickly |
| HV stdev computed on gappy price series | `compute_hv` requires exactly `window` contiguous trading days; returns None otherwise |

## Sizing

- Backend: 2.5 days (ingest helpers + replace NOOP + scan filter + admin health + tests)
- Frontend: 1 day (options tab fix + IV-rank columns + tooltip + tests)
- Config + catalog + QA: 0.5 day
- Review + verification: 0.5 day
- **Total: ~4-5 dev days, 1 PR, 0 migrations**

## Dispatch pattern

One Cursor Background Agent runs this plan end-to-end on branch `feat/iv-rank-surface`. Opus reviews the final PR focusing on:

- HV stdev math (ddof=0 on log returns, sqrt(252) annualization)
- No silent-zero anywhere (grep `?? 0` and `or 0` in new code)
- Counter-loop assertion present and exercised in tests
- `iv_hv_spread` handles null `hv_20d` correctly (was the bug in the original `compute_rank`)

## Follow-ups (non-blocking)

- Paid-provider evaluation if coverage < 95% after 30 days (separate plan).
- IBKR options-trading path (Wave F F4 options note) once Wave F lands — some executors may gain IV-informed limit-price defaults.
- Strategy-side: expose IV rank as a rule-eval predicate so scanning for "IV rank < 20" filters can fire candidates.
