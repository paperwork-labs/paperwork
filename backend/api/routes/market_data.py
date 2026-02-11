"""
AxiomFolio V1 - Market Data Routes

Clean, service-driven endpoints for prices, snapshots, tracked universe, backfills,
indicator recompute, and history. DB-first strategy: compute from local `price_data`.
Providers are used only for OHLCV backfills (paid provider prioritized).
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from typing import List, Dict, Any, Callable, Optional
import logging
from datetime import datetime, timedelta

# dependencies
from backend.database import get_db
from backend.models.user import User
from backend.services.market.market_data_service import MarketDataService
from backend.services.market.market_dashboard_service import MarketDashboardService
from backend.services.market.universe import tracked_symbols
from backend.services.market.constants import (
    SNAPSHOT_PREFERRED_COLUMNS,
    SNAPSHOTS_PREFERRED_COLUMNS,
    SNAPSHOT_HISTORY_PREFERRED_COLUMNS,
)
from backend.models.market_data import MarketSnapshot, MarketSnapshotHistory
from backend.tasks.market_data_tasks import (
    record_daily_history,
    update_tracked_symbol_cache,
    backfill_symbols,
    recompute_indicators_universe,
    refresh_index_constituents,
    refresh_single_symbol,
    backfill_snapshot_history_last_n_days,
    backfill_daily_since_date,
    backfill_last_bars,
    backfill_since_date,
)
from backend.api.dependencies import (
    get_optional_user,
    get_admin_user,
    get_market_data_viewer,
    market_visibility_scope,
    market_exposed_to_all,
)
from backend.models.index_constituent import IndexConstituent
from backend.models.market_data import PriceData
from backend.models.market_data import JobRun
from backend.api.routes.utils import serialize_job_runs
from backend.tasks.market_data_tasks import backfill_5m_last_n_days, enforce_price_data_retention, backfill_5m_for_symbols
from backend.tasks.market_data_tasks import monitor_coverage_health
from backend.tasks.market_data_tasks import bootstrap_daily_coverage_tracked
from backend.tasks.market_data_tasks import backfill_stale_daily_tracked
from backend.config import settings
from backend.services.notifications.discord_bot import discord_bot_client
from backend.models import Position

logger = logging.getLogger(__name__)

router = APIRouter()


def _visibility_scope() -> str:
    return market_visibility_scope()


def _snapshot_preferred_columns(kind: str) -> list[str]:
    if kind == "single":
        return list(SNAPSHOT_PREFERRED_COLUMNS)
    if kind == "list":
        return list(SNAPSHOTS_PREFERRED_COLUMNS)
    if kind == "history":
        return list(SNAPSHOT_HISTORY_PREFERRED_COLUMNS)
    raise ValueError(f"Unknown snapshot column kind: {kind}")


TASK_ACTIONS: List[Dict[str, Any]] = [
    {
        "task_name": "admin_backfill_5m",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/5m",
        "description": "Backfill 5m bars for last N days (default 5).",
        "params_schema": [
            {"name": "n_days", "type": "int", "default": 5, "min": 1, "max": 60},
            {"name": "batch_size", "type": "int", "default": 50, "min": 10, "max": 500},
        ],
        "status_task": "admin_backfill_5m",
    },
    {
        "task_name": "admin_backfill_daily",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/daily",
        "description": "Backfill last ~200 daily bars for tracked universe.",
        "params_schema": [
            {"name": "days", "type": "int", "default": 200, "min": 30, "max": 3000},
        ],
        "status_task": "admin_backfill_daily",
    },
    {
        "task_name": "admin_coverage_backfill_stale",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/coverage/stale",
        "description": "Backfill stale/missing daily bars across tracked symbols.",
        "status_task": "admin_coverage_backfill_stale",
    },
    {
        "task_name": "admin_coverage_refresh",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/coverage/refresh",
        "description": "Recompute coverage health snapshot and cache.",
        "status_task": "admin_coverage_refresh",
    },
    {
        "task_name": "admin_coverage_backfill",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/coverage",
        "description": "Guided backfill: refresh → tracked → daily → recompute → history → refresh.",
        "status_task": "admin_coverage_backfill",
    },
    {
        "task_name": "admin_indicators_recompute_universe",
        "method": "POST",
        "endpoint": "/market-data/admin/indicators/recompute-universe",
        "description": "Recompute indicators for tracked universe.",
        "params_schema": [
            {"name": "batch_size", "type": "int", "default": 50, "min": 10, "max": 200},
        ],
        "status_task": "admin_indicators_recompute_universe",
    },
    {
        "task_name": "admin_snapshots_history_backfill",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/snapshots/history",
        "description": "Backfill snapshot history for last 200 trading days.",
        "params_schema": [
            {"name": "days", "type": "int", "default": 200, "min": 5, "max": 3000},
        ],
        "status_task": "admin_snapshots_history_backfill",
    },
    {
        "task_name": "admin_snapshots_history_record",
        "method": "POST",
        "endpoint": "/market-data/admin/snapshots/history/record",
        "description": "Record immutable daily analysis history.",
        "status_task": "admin_snapshots_history_record",
    },
    {
        "task_name": "market_indices_constituents_refresh",
        "method": "POST",
        "endpoint": "/market-data/indices/constituents/refresh",
        "description": "Refresh SP500 / NASDAQ100 / DOW30 constituents.",
        "status_task": "market_indices_constituents_refresh",
    },
    {
        "task_name": "market_universe_tracked_refresh",
        "method": "POST",
        "endpoint": "/market-data/universe/tracked/refresh",
        "description": "Refresh tracked symbol universe (index ∪ portfolio).",
        "status_task": "market_universe_tracked_refresh",
    },
]


def _task_status_keys() -> List[str]:
    keys = {action.get("status_task") or action["task_name"] for action in TASK_ACTIONS}
    keys.update({"admin_backfill_since_date", "admin_snapshots_history_backfill"})
    return sorted(keys)


def _coverage_actions(backfill_5m_enabled: bool = True) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = [
        {
            "label": "Refresh Index Constituents",
            "task_name": "market_indices_constituents_refresh",
            "description": "Fetch SP500 / NASDAQ100 / DOW30 members (FMP-first, Wikipedia fallback). Endpoint: POST /api/v1/market-data/indices/constituents/refresh",
        },
        {
            "label": "Update Tracked Symbols",
            "task_name": "market_universe_tracked_refresh",
            "description": "Union index constituents with held symbols and publish tracked:all/new in Redis. Endpoint: POST /api/v1/market-data/universe/tracked/refresh",
        },
        {
            "label": "Backfill Daily Coverage (Tracked)",
            "task_name": "admin_coverage_backfill",
            "description": "Guided operator flow: refresh → tracked → daily backfill → recompute → history → refresh coverage (no 5m). Endpoint: POST /api/v1/market-data/admin/backfill/coverage",
        },
        {
            "label": "Backfill Daily (Stale Only)",
            "task_name": "admin_coverage_backfill_stale",
            "description": "Backfill daily bars only for symbols currently stale (>48h/none) in coverage snapshot. Endpoint: POST /api/v1/market-data/admin/backfill/coverage/stale",
        },
        {
            "label": "Refresh Coverage Cache",
            "task_name": "admin_coverage_refresh",
            "description": "Recompute coverage snapshot and refresh Redis cache + history. Endpoint: POST /api/v1/market-data/admin/backfill/coverage/refresh",
        },
        {
            "label": "Backfill 5m Last N Days",
            "task_name": "admin_backfill_5m",
            "description": "Populate 5m bars for the tracked set (default N days) to improve intraday freshness. Endpoint: POST /api/v1/market-data/admin/backfill/5m",
        },
    ]
    if not backfill_5m_enabled:
        for action in actions:
            if action.get("task_name") == "admin_backfill_5m":
                action["disabled"] = True
                action["description"] = f"{action.get('description')} (disabled by admin toggle)"
    return actions


def _coverage_education() -> Dict[str, Any]:
    return {
        "coverage": "Coverage measures how many tracked symbols have fresh bars stored in price_data. Daily coverage should stay above 95% and 5m coverage should be refreshed at least once per trading day.",
        "tracked": "Tracked is the union of live index constituents plus any symbols seen in your brokerage accounts. Use Update Tracked after refreshing constituents to republish the universe to Redis.",
        "how_to_fix": [
            "Refresh Index Constituents to sync SP500 / NASDAQ100 / DOW30 membership.",
            "Update Tracked Symbol Cache to rebuild the Redis universe from the DB.",
            "Backfill Daily Coverage (Tracked) to backfill daily bars and recompute indicators (no 5m).",
            "Backfill 5m to capture latest intraday data for freshness dashboards.",
        ],
    }


def _tracked_actions() -> List[Dict[str, str]]:
    return [
        {
            "label": "Update Tracked Symbols",
            "task_name": "market_universe_tracked_refresh",
            "description": "Rebuild tracked:all / tracked:new from DB index_constituents ∪ portfolio symbols. Endpoint: POST /api/v1/market-data/universe/tracked/refresh",
        },
    ]


def _tracked_education() -> Dict[str, Any]:
    return {
        "overview": "Tracked symbols represent everything the platform monitors (index members + any holdings pulled from brokers). Coverage metrics show how fresh the price_data rows are for these symbols.",
        "details": [
            "Update Tracked Symbol Cache unions DB constituents with holdings and publishes Redis keys tracked:all and tracked:new.",
            "You can sort/filter the table by sector, industry, ATR, or stage to decide the next action.",
        ],
    }


def _enqueue_task(task_fn: Callable, *args, **kwargs) -> Dict[str, Any]:
    """Standardize task enqueue responses."""
    result = task_fn.delay(*args, **kwargs)
    return {"task_id": result.id}

@router.get("/admin/coverage/sanity")
async def admin_sanity_coverage(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Quick DB sanity checks for coverage (no Redis cache dependence).

    Returns:
    - latest daily OHLCV date + distinct symbol count on that date
    - latest snapshot-history as_of_date + distinct symbol count on that date
    - snapshot-history fill % vs tracked universe for that day (+ missing sample)
    - benchmark (SPY) daily bar count + latest date (for Stage/RS diagnostics)
    """
    svc = MarketDataService()
    tracked = tracked_symbols(db, redis_client=svc.redis_client)
    tracked_set = set(tracked)
    tracked_total = len(tracked_set)

    latest_daily_dt = (
        db.query(func.max(PriceData.date))
        .filter(PriceData.interval == "1d")
        .scalar()
    )
    latest_daily_date = latest_daily_dt.date().isoformat() if latest_daily_dt else None
    daily_count = 0
    if latest_daily_dt and tracked_set:
        daily_count = (
            db.query(func.count(distinct(PriceData.symbol)))
            .filter(
                PriceData.interval == "1d",
                PriceData.symbol.in_(tracked_set),
                func.date(PriceData.date) == func.date(latest_daily_dt),
            )
            .scalar()
            or 0
        )

    latest_hist_dt = (
        db.query(func.max(MarketSnapshotHistory.as_of_date))
        .filter(MarketSnapshotHistory.analysis_type == "technical_snapshot")
        .scalar()
    )
    latest_hist_date = latest_hist_dt.date().isoformat() if latest_hist_dt else None
    hist_count = 0
    missing_sample: list[str] = []
    if latest_hist_dt and tracked_set:
        hist_syms = (
            db.query(MarketSnapshotHistory.symbol)
            .filter(
                MarketSnapshotHistory.analysis_type == "technical_snapshot",
                MarketSnapshotHistory.symbol.in_(tracked_set),
                func.date(MarketSnapshotHistory.as_of_date) == func.date(latest_hist_dt),
            )
            .distinct()
            .all()
        )
        hist_set = {s[0].upper() for s in hist_syms if s and s[0]}
        hist_count = len(hist_set)
        if tracked_total:
            missing_sample = sorted(list(tracked_set - hist_set))[:20]

    pct = round((hist_count / tracked_total) * 100.0, 1) if tracked_total else 0.0
    bench = svc.coverage.benchmark_health(db)
    return {
        "tracked_total": tracked_total,
        "latest_daily_date": latest_daily_date,
        "latest_daily_symbol_count": int(daily_count),
        "latest_snapshot_history_date": latest_hist_date,
        "latest_snapshot_history_symbol_count": int(hist_count),
        "latest_snapshot_history_fill_pct": pct,
        "missing_snapshot_history_sample": missing_sample,
        "benchmark": {
            "symbol": bench.get("symbol"),
            "latest_daily_date": bench.get("latest_daily_date"),
            "daily_bars": int(bench.get("daily_bars") or 0),
            "required_bars": int(bench.get("required_bars") or 0),
            "ok": bool(bench.get("ok")),
        },
    }


# =============================================================================
# MARKET DATA ENDPOINTS
# Order: Prices → Snapshots → Constituents/Tracked → Backfills → Indicators → Admin
# =============================================================================


@router.get("/prices/{symbol}")
async def get_current_price(
    symbol: str, user: User | None = Depends(get_optional_user)
) -> Dict[str, Any]:
    """Get current price for a symbol."""
    try:
        market_service = MarketDataService()
        price = await market_service.get_current_price(symbol)

        return {
            "symbol": symbol,
            "current_price": price,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Price error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prices/{symbol}/history")
async def get_history(
    symbol: str,
    period: str = Query("1y", description="e.g., 1mo, 3mo, 6mo, 1y, 2y, 5y"),
    interval: str = Query("1d", description="1d, 4h, 1h, 5m"),
    user: User | None = Depends(get_optional_user),
) -> Dict[str, Any]:
    """
    Daily/intraday OHLCV series for the symbol using MarketDataService policy.
    Returns list of { time, open, high, low, close, volume } with time as ISO.
    """
    try:
        svc = MarketDataService()
        # Pass max_bars=None so longer periods (e.g., 3y) are not trimmed to default 270
        df = await svc.get_historical_data(symbol=symbol.upper(), period=period, interval=interval, max_bars=None)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="No historical data")
        # Expect newest->first index; convert to ascending by date
        try:
            df_out = df.iloc[::-1].copy()
        except Exception:
            df_out = df
        # Normalize columns
        cols = {c.lower(): c for c in df_out.columns}
        def pick(col_name: str) -> str:
            for key in cols:
                if key.startswith(col_name):
                    return cols[key]
            return col_name
        o = pick("open")
        h = pick("high")
        l = pick("low")
        c = pick("close")
        v = pick("volume")
        out = []
        for ts, row in df_out.iterrows():
            out.append({
                "time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "open": float(row.get(o, None) or row.get("open_price", 0) or 0),
                "high": float(row.get(h, None) or row.get("high_price", 0) or 0),
                "low": float(row.get(l, None) or row.get("low_price", 0) or 0),
                "close": float(row.get(c, None) or row.get("close_price", 0) or 0),
                "volume": float(row.get(v, 0) or 0),
            })
        return {"symbol": symbol.upper(), "period": period, "interval": interval, "bars": out}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ History error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# TECHNICAL SNAPSHOTS (MarketSnapshot)
# =============================================================================


@router.get("/snapshots/{symbol}")
async def get_snapshot(
    symbol: str,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return latest technical snapshot for a symbol from MarketSnapshot."""
    row = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.symbol == symbol.upper(),
            MarketSnapshot.analysis_type == "technical_snapshot",
        )
        .order_by(MarketSnapshot.analysis_timestamp.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="No snapshot found")
    # Keep response stable and human-friendly by ordering key columns first.
    preferred = _snapshot_preferred_columns("single")
    col_names = [c.name for c in row.__table__.columns]
    ordered_keys = [k for k in preferred if k in col_names]
    ordered_keys.extend([k for k in col_names if k not in set(ordered_keys)])
    payload = {k: getattr(row, k) for k in ordered_keys}
    return {"symbol": symbol.upper(), "snapshot": payload}


@router.get("/snapshots")
async def get_snapshots(
    limit: int = Query(2000, ge=1, le=5000),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return latest technical snapshots for the tracked universe from MarketSnapshot.

    Intended for read-only scanners/tables (e.g., Market Coverage page). Sorting is client-side.
    """
    svc = MarketDataService()
    tracked = tracked_symbols(db, redis_client=svc.redis_client)
    if not tracked:
        return {"count": 0, "rows": []}

    rows = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.symbol.in_(tracked),
        )
        .order_by(MarketSnapshot.symbol.asc())
        .limit(limit)
        .all()
    )

    preferred = _snapshot_preferred_columns("list")
    col_names = list(getattr(MarketSnapshot, "__table__").columns.keys())
    ordered = [k for k in preferred if k in col_names]
    ordered.extend([k for k in col_names if k not in set(ordered) and k not in {"id"}])

    out: list[dict] = []
    for r in rows:
        out.append({k: getattr(r, k) for k in ordered})

    return {"count": len(out), "rows": out}


@router.get("/snapshots/{symbol}/history")
async def get_snapshot_history(
    symbol: str,
    days: int = Query(200, ge=1, le=3000),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return historical technical snapshots (MarketSnapshotHistory ledger) for a symbol."""
    rows = (
        db.query(MarketSnapshotHistory)
        .filter(
            MarketSnapshotHistory.symbol == symbol.upper(),
            MarketSnapshotHistory.analysis_type == "technical_snapshot",
        )
        .order_by(MarketSnapshotHistory.as_of_date.desc())
        .limit(days)
        .all()
    )
    out = []
    for r in reversed(rows):  # oldest->newest
        # Build a stable snapshot dict from wide columns (no JSON payload).
        col_names = [c.name for c in r.__table__.columns]
        preferred = _snapshot_preferred_columns("history")
        ordered = [k for k in preferred if k in col_names]
        ordered.extend([k for k in col_names if k not in set(ordered) and k not in {"id"}])
        payload = {k: getattr(r, k) for k in ordered}
        out.append(
            {
                "as_of_date": r.as_of_date.isoformat() if hasattr(r.as_of_date, "isoformat") else str(r.as_of_date),
                "snapshot": payload,
            }
        )
    return {"symbol": symbol.upper(), "days": int(days), "rows": out}


@router.post("/admin/backfill/snapshots/history")
async def admin_backfill_snapshot_history_last_n_days(
    days: int = Query(200, ge=1, le=3000),
    since_date: str | None = Query(None, description="Optional YYYY-MM-DD; overrides days by selecting all available trading days since date"),
    user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Backfill MarketSnapshotHistory for the last N trading days (DB-only)."""
    return _enqueue_task(backfill_snapshot_history_last_n_days, days, since_date=since_date)


@router.post("/admin/backfill/daily/since-date")
async def admin_backfill_daily_since_date(
    since_date: str = Query("2021-01-01", description="YYYY-MM-DD"),
    batch_size: int = Query(25, ge=1, le=200),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Deep daily OHLCV backfill since a given date for the tracked universe (provider fetch)."""
    return _enqueue_task(backfill_daily_since_date, since_date, batch_size)


@router.post("/admin/backfill/since-date")
async def admin_backfill_since_date(
    since_date: str = Query("2021-01-01", description="YYYY-MM-DD"),
    daily_batch_size: int = Query(25, ge=1, le=200),
    history_batch_size: int = Query(50, ge=1, le=200),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Backfill daily bars + indicators + snapshot history since a given date."""
    return _enqueue_task(
        backfill_since_date,
        since_date,
        daily_batch_size=daily_batch_size,
        history_batch_size=history_batch_size,
    )


@router.post("/admin/backfill/daily")
async def admin_backfill_daily_last_bars(
    days: int = Query(200, ge=30, le=3000, description="Approx trading days (default 200)"),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Backfill last N daily bars for the tracked universe (provider fetch, delta insert)."""
    return _enqueue_task(backfill_last_bars, days=days)


# Removed duplicate refresh; use POST /symbols/{symbol}/refresh instead


@router.get("/admin/tasks/status")
async def admin_task_status(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Return last-run status for key market-data tasks from Redis.

    This endpoint intentionally returns a clean, task-name keyed payload (not raw Redis keys),
    so UIs can render friendly labels without leaking storage details.
    """
    try:
        from backend.services.market.market_data_service import market_data_service

        r = market_data_service.redis_client
        tasks = _task_status_keys()
        out: Dict[str, Any] = {}
        import json as _json

        for task_name in tasks:
            try:
                key = f"taskstatus:{task_name}:last"
                raw = r.get(key)
                out[task_name] = _json.loads(raw) if raw else None
            except Exception:
                out[task_name] = None
        return out
    except Exception as e:
        logger.error(f"task status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MarketSnapshot → Discord Digest (manual trigger; scheduled later)
# =============================================================================


@router.post("/admin/snapshots/discord-digest")
async def admin_send_snapshot_digest_to_discord(
    channel_id: str | None = Query(
        None, description="Discord channel ID; defaults to DISCORD_BOT_DEFAULT_CHANNEL_ID"
    ),
    limit: int = Query(12, ge=1, le=25, description="Top-N RS rows to include"),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Send a compact snapshot digest to Discord (Bot token).

    Manual trigger today; reuse the same builder for scheduled sends later.
    """
    if not discord_bot_client.is_configured():
        raise HTTPException(status_code=400, detail="DISCORD_BOT_TOKEN not configured")
    resolved_channel = channel_id or getattr(settings, "DISCORD_BOT_DEFAULT_CHANNEL_ID", None)
    if not resolved_channel:
        raise HTTPException(
            status_code=400,
            detail="No channel_id provided and DISCORD_BOT_DEFAULT_CHANNEL_ID not set",
        )

    svc = MarketDataService()
    tracked = tracked_symbols(db, redis_client=svc.redis_client)
    if not tracked:
        raise HTTPException(status_code=400, detail="No tracked symbols available")

    sym_set = set(tracked)
    rows = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.symbol.in_(sym_set),
        )
        .order_by(MarketSnapshot.symbol.asc(), MarketSnapshot.analysis_timestamp.desc())
        .distinct(MarketSnapshot.symbol)
        .all()
    )

    total = len(tracked)
    have = len(rows)

    # Stage distribution
    stage_counts: Dict[str, int] = {}
    for r in rows:
        lbl = getattr(r, "stage_label", None) or "UNKNOWN"
        stage_counts[str(lbl)] = stage_counts.get(str(lbl), 0) + 1
    stage_counts_sorted = sorted(stage_counts.items(), key=lambda kv: (-kv[1], kv[0]))

    # Top RS (Mansfield %)
    def rs_val(r) -> float:
        try:
            v = getattr(r, "rs_mansfield_pct", None)
            return float(v) if v is not None else float("-inf")
        except Exception:
            return float("-inf")

    top_rs = sorted(rows, key=rs_val, reverse=True)[: int(limit)]
    top_lines: List[str] = []
    for r in top_rs:
        sym = getattr(r, "symbol", "")
        rs = getattr(r, "rs_mansfield_pct", None)
        stage = getattr(r, "stage_label", None) or "?"
        try:
            rs_fmt = f"{float(rs):.1f}%" if rs is not None else "—"
        except Exception:
            rs_fmt = "—"
        top_lines.append(f"- {sym}: RS {rs_fmt} • Stage {stage}")

    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    lines = [
        f"AxiomFolio — MarketSnapshot digest ({now})",
        f"Universe: {have}/{total} symbols have snapshots",
    ]
    if stage_counts_sorted:
        lines.append("Stage distribution:")
        lines.extend([f"- {k}: {v}" for k, v in stage_counts_sorted])
    if top_lines:
        lines.append(f"Top RS (Mansfield vs SPY, top {len(top_lines)}):")
        lines.extend(top_lines)

    content = "\n".join(lines)
    ok = await discord_bot_client.send_message(channel_id=resolved_channel, content=content)
    return {
        "status": "ok" if ok else "error",
        "channel_id": resolved_channel,
        "sent": bool(ok),
        "symbols": total,
        "snapshots": have,
    }


# =============================================================================
# Constituents & Tracked Universe (DB + Redis)
# =============================================================================


@router.get("/indices/constituents")
async def get_index_constituents(
    index: str = Query("SP500", description="SP500, NASDAQ100, DOW30"),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    index = index.upper()
    if index not in {"SP500", "NASDAQ100", "DOW30"}:
        raise HTTPException(status_code=400, detail="invalid index")
    q = db.query(IndexConstituent).filter(IndexConstituent.index_name == index)
    if active_only:
        q = q.filter(IndexConstituent.is_active.is_(True))
    rows = q.order_by(IndexConstituent.symbol.asc()).all()
    return {"index": index, "count": len(rows), "symbols": [r.symbol for r in rows]}


@router.post("/indices/constituents/refresh")
async def post_refresh_constituents(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    return _enqueue_task(refresh_index_constituents)


@router.get("/universe/tracked")
async def get_tracked(
    include_details: bool = Query(True),
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    from backend.services.market.market_data_service import market_data_service

    r = market_data_service.redis_client

    all_raw = r.get("tracked:all")
    new_raw = r.get("tracked:new")
    all_symbols = sorted(json.loads(all_raw) if all_raw else [])
    new_symbols = json.loads(new_raw) if new_raw else []

    details = market_data_service.get_tracked_details(db, all_symbols) if include_details else {}

    meta = {
        "visibility": _visibility_scope(),
        "exposed_to_all": market_exposed_to_all(),
        "education": _tracked_education(),
        "actions": _tracked_actions(),
    }

    return {
        "all": all_symbols,
        "new": new_symbols,
        "details": details if include_details else {},
        "meta": meta,
    }


@router.post("/universe/tracked/refresh")
async def post_update_tracked(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    return _enqueue_task(update_tracked_symbol_cache)


# =============================================================================
# Backfills (OHLCV) and Indicators
# =============================================================================


## Hard consolidation: legacy daily backfill endpoints removed.
## Use:
## - POST /admin/backfill/coverage
## - POST /admin/backfill/coverage/stale
## - POST /admin/backfill/coverage/refresh


@router.post("/admin/indicators/recompute-universe")
async def post_recompute_universe(
    batch_size: int = Query(50, ge=10, le=200),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    return _enqueue_task(recompute_indicators_universe, batch_size)


# =============================================================================
# Single-symbol Refresh (DB-first flow)
# =============================================================================


@router.post("/symbols/{symbol}/refresh")
async def post_refresh_symbol(
    symbol: str,
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Delta backfill and recompute indicators for a single symbol (no external TA).

    Flow: backfill_last_bars(symbols/days) → recompute from DB → persist MarketSnapshot.
    """
    return _enqueue_task(refresh_single_symbol, symbol.upper())


@router.post("/admin/snapshots/history/record")
async def admin_record_history(
    symbols: List[str] | None = Query(None),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    try:
        res = record_daily_history(symbols)
        return res
    except Exception as e:
        logger.error(f"admin record history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# DB History (from price_data) and Coverage
# =============================================================================


@router.get("/admin/db/history")
async def get_db_history(
    symbol: str = Query(...),
    interval: str = Query("1d", pattern="^(1d|5m)$"),
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=20000),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return OHLCV bars for a symbol from price_data (ascending)."""
    from backend.services.market.market_data_service import MarketDataService

    svc = MarketDataService()
    try:
        parse = lambda s: datetime.fromisoformat(s) if s else None
        df = svc.get_db_history(
            db,
            symbol=symbol.upper(),
            interval=interval,
            start=parse(start),
            end=parse(end),
            limit=limit,
        )
        bars = []
        for ts, row in df.iterrows():
            bars.append(
                {
                    "time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                    "open": float(row.get("Open", 0) or 0),
                    "high": float(row.get("High", 0) or 0),
                    "low": float(row.get("Low", 0) or 0),
                    "close": float(row.get("Close", 0) or 0),
                    "volume": float(row.get("Volume", 0) or 0),
                }
            )
        return {"symbol": symbol.upper(), "interval": interval, "bars": bars}
    except Exception as e:
        logger.error(f"db history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/coverage")
async def get_coverage(
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
    fill_trading_days_window: int | None = Query(
        None, ge=10, le=300, description="UI histogram window (trading days)"
    ),
    fill_lookback_days: int | None = Query(
        None, ge=30, le=4000, description="Calendar-day lookback for fill_by_date series"
    ),
) -> Dict[str, Any]:
    """Return coverage summary across intervals with last bar timestamps and freshness buckets."""
    try:
        svc = MarketDataService()
        snapshot = svc.coverage.build_coverage_response(
            db,
            fill_trading_days_window=fill_trading_days_window,
            fill_lookback_days=fill_lookback_days,
        )
        meta = snapshot.setdefault("meta", {})
        meta["visibility"] = _visibility_scope()
        meta["exposed_to_all"] = market_exposed_to_all()
        meta["education"] = _coverage_education()
        meta["actions"] = _coverage_actions(meta.get("backfill_5m_enabled"))
        return snapshot
    except Exception as e:
        logger.error(f"coverage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def get_market_dashboard(
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """Reader-friendly market dashboard summary for momentum workflows."""
    try:
        dashboard = MarketDashboardService()
        return dashboard.build_dashboard(db)
    except Exception as e:
        logger.error(f"market dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/backfill/5m/toggle")
async def get_backfill_5m_toggle(
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    svc = MarketDataService()
    return {"backfill_5m_enabled": svc.coverage.is_backfill_5m_enabled()}


@router.post("/admin/backfill/5m/toggle")
async def set_backfill_5m_toggle(
    enabled: bool = Body(..., embed=True),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    svc = MarketDataService()
    try:
        svc.redis_client.set("coverage:backfill_5m_enabled", "true" if enabled else "false")
        return {"backfill_5m_enabled": enabled}
    except Exception as e:
        logger.error(f"toggle error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update 5m backfill toggle")


@router.post("/admin/backfill/coverage/stale")
async def backfill_stale_daily(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Backfill daily bars for symbols currently marked stale (>48h) in coverage snapshot.
    """
    svc = MarketDataService()
    try:
        # Provide an estimate for UI (full stale+missing set, not sample-capped).
        tracked: List[str] = []
        try:
            raw = svc.redis_client.get("tracked:all")
            tracked = json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw) if raw else []  # type: ignore[arg-type]
        except Exception:
            tracked = []
        tracked = sorted({str(s).upper() for s in (tracked or []) if s})
        if not tracked:
            tracked = sorted({str(s).upper() for (s,) in db.query(PriceData.symbol).distinct().all() if s})

        _, stale_full = svc.coverage.compute_interval_coverage_for_symbols(
            db,
            symbols=tracked,
            interval="1d",
            now_utc=datetime.utcnow(),
            return_full_stale=True,
        )
        stale_candidates = len(stale_full or [])
        enq = _enqueue_task(backfill_stale_daily_tracked)
        return {**enq, "stale_candidates": stale_candidates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/backfill/coverage/refresh")
async def admin_refresh_coverage(
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Trigger the coverage health monitor to refresh Redis cache + history."""
    return _enqueue_task(monitor_coverage_health)


@router.post("/admin/backfill/coverage")
async def admin_backfill_daily_tracked(
    history_days: int | None = Query(
        None, ge=1, le=300, description="Trading days to backfill into snapshot history (auto if omitted)"
    ),
    history_batch_size: int = Query(25, ge=1, le=200),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Run the guided daily coverage backfill chain for the tracked universe (no 5m)."""
    return _enqueue_task(
        bootstrap_daily_coverage_tracked,
        history_days=history_days,
        history_batch_size=history_batch_size,
    )


@router.get("/admin/backfill/coverage/preview")
async def admin_backfill_daily_tracked_preview(
    history_days: int | None = Query(
        None, ge=1, le=300, description="Trading days to backfill into snapshot history (auto if omitted)"
    ),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    from backend.tasks import market_data_tasks

    resolved_days = market_data_tasks._resolve_history_days(history_days)
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=resolved_days)
    return {
        "requested_history_days": history_days,
        "resolved_history_days": int(resolved_days),
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
    }


@router.get("/coverage/{symbol}")
async def get_symbol_coverage(
    symbol: str,
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """Return last bar timestamps for daily and 5m for a symbol."""
    try:
        sym = symbol.upper()
        last_daily = (
            db.query(PriceData.date)
            .filter(PriceData.symbol == sym, PriceData.interval == "1d")
            .order_by(PriceData.date.desc())
            .limit(1)
            .scalar()
        )
        last_m5 = (
            db.query(PriceData.date)
            .filter(PriceData.symbol == sym, PriceData.interval == "5m")
            .order_by(PriceData.date.desc())
            .limit(1)
            .scalar()
        )
        return {
            "symbol": sym,
            "last_daily": last_daily.isoformat() if last_daily else None,
            "last_5m": last_m5.isoformat() if last_m5 else None,
        }
    except Exception as e:
        logger.error(f"symbol coverage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Admin: 5m backfill, retention, jobs and tasks (RBAC)
# =============================================================================


@router.post("/admin/backfill/5m")
async def post_backfill_5m(
    n_days: int = Query(5, ge=1, le=60),
    batch_size: int = Query(50, ge=10, le=200),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    return _enqueue_task(backfill_5m_last_n_days, n_days=n_days, batch_size=batch_size)


@router.post("/admin/retention/enforce")
async def post_retention_enforce(
    max_days_5m: int = Query(90, ge=7, le=365),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    return _enqueue_task(enforce_price_data_retention, max_days_5m=max_days_5m)


@router.get("/admin/market-audit")
async def get_market_data_audit(
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    svc = MarketDataService()
    try:
        raw = svc.redis_client.get("market_audit:last")
        payload = json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw) if raw else None
    except Exception:
        payload = None
    return {"audit": payload}


@router.get("/admin/jobs")
async def admin_get_jobs(
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=100000),
    all: bool = Query(False),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    total = db.query(JobRun).count()
    query = db.query(JobRun).order_by(JobRun.started_at.desc())
    if all:
        rows = query.all()
        return {"jobs": serialize_job_runs(rows), "total": total, "limit": total, "offset": 0}
    effective_limit = limit or 50
    rows = query.offset(offset).limit(effective_limit).all()
    return {"jobs": serialize_job_runs(rows), "total": total, "limit": effective_limit, "offset": offset}


@router.get("/admin/tasks")
async def admin_list_tasks(
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Discover available market-data task actions (UI-safe subset)."""
    for action in TASK_ACTIONS:
        name = action.get("task_name")
        method = action.get("method")
        endpoint = action.get("endpoint")
        if not isinstance(name, str) or not name:
            raise HTTPException(status_code=500, detail="task action missing task_name")
        if not isinstance(method, str) or not method:
            raise HTTPException(status_code=500, detail=f"task action {name} missing method")
        if not isinstance(endpoint, str) or not endpoint:
            raise HTTPException(status_code=500, detail=f"task action {name} missing endpoint")
    return {"tasks": TASK_ACTIONS}


@router.post("/admin/tasks/run")
async def admin_run_task(
    task_name: str = Query(...),
    symbols: List[str] | None = Query(None),
    n_days: int | None = Query(None),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Manually trigger selected tasks."""
    if task_name == "admin_backfill_5m_symbols":
        if not symbols:
            raise HTTPException(status_code=400, detail="symbols required")
        return _enqueue_task(
            backfill_5m_for_symbols,
            [s.upper() for s in symbols if s],
            n_days=n_days or 5,
        )
    if task_name == "admin_backfill_5m":
        return _enqueue_task(backfill_5m_last_n_days, n_days=n_days or 5)
    raise HTTPException(status_code=400, detail="unsupported task or not exposed here")

