"""
Market Admin Routes
===================

Administrative endpoints for market data operations:
- Health checks
- Backfill operations (daily, 5m, coverage)
- Job management
- Auto-fix
- Indicators recompute
- History recording
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.api.dependencies import get_admin_user
from app.api.rate_limit import limiter
from app.api.routes.utils import serialize_job_runs
from app.config import settings
from app.database import get_db
from app.models.market_data import (
    JobRun,
    MarketSnapshot,
    MarketSnapshotHistory,
    PriceData,
)
from app.models.user import User
from app.services.brain.webhook_client import brain_webhook
from app.services.market.admin_health_service import AdminHealthService
from app.services.market.market_data_service import (
    coverage_analytics,
    infra,
    price_bars,
    stage_quality,
)
from app.services.market.universe import tracked_symbols_async
from app.tasks.market.backfill import (
    daily_bars,
    daily_since,
    full_historical,
    safe_recompute,
    stale_daily,
)
from app.tasks.market.coverage import daily_bootstrap, health_check
from app.tasks.market.fundamentals import fill_missing
from app.tasks.market.history import record_daily, snapshot_last_n_days
from app.tasks.market.indicators import recompute_universe
from app.tasks.market.intraday import bars_5m_last_n_days, bars_5m_symbols
from app.tasks.market.maintenance import prune_old_bars, recover_jobs_impl

from ._shared import TASK_ACTIONS, enqueue_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _default_history_start() -> str:
    """Derive the default since_date from HISTORY_TARGET_YEARS."""
    from datetime import date, timedelta

    return (date.today() - timedelta(days=settings.HISTORY_TARGET_YEARS * 365)).isoformat()


# ── Pydantic models for auto-fix ──


class AutoFixPlanItem(BaseModel):
    task: str
    reason: str
    task_id: str | None = None
    status: str = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    error: str | None = None


class AutoFixResponse(BaseModel):
    status: str
    job_id: str | None = None
    plan: list[AutoFixPlanItem] = []
    estimated_minutes: int = 0
    message: str = ""


class AutoFixStatusResponse(BaseModel):
    job_id: str
    status: str
    plan: list[AutoFixPlanItem] = []
    completed_count: int = 0
    total_count: int = 0
    current_task: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


# ── Health endpoints ──


@router.get("/health")
async def admin_composite_health(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Composite health check across coverage, stage quality, jobs, and audit."""
    svc = AdminHealthService()
    return svc.get_composite_health(db)


@router.get("/pre-market-readiness")
async def get_pre_market_readiness(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Check system readiness for next trading session."""
    svc = AdminHealthService()
    return svc.check_pre_market_readiness(db)


@router.get("/coverage/sanity")
async def admin_sanity_coverage(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Quick DB sanity checks for coverage (no Redis cache dependence)."""
    r = await infra._get_redis()
    tracked = await tracked_symbols_async(db, redis_async=r)
    tracked_set = set(tracked)
    tracked_total = len(tracked_set)

    latest_daily_dt = db.query(func.max(PriceData.date)).filter(PriceData.interval == "1d").scalar()
    latest_daily_date = None
    if latest_daily_dt:
        d0 = latest_daily_dt.date() if hasattr(latest_daily_dt, "date") else latest_daily_dt
        latest_daily_date = d0.isoformat() if hasattr(d0, "isoformat") else str(d0)
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
    latest_hist_date = None
    if latest_hist_dt:
        h0 = latest_hist_dt.date() if hasattr(latest_hist_dt, "date") else latest_hist_dt
        latest_hist_date = h0.isoformat() if hasattr(h0, "isoformat") else str(h0)
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
    bench = coverage_analytics.benchmark_health(db)
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


# ── Backfill endpoints ──


@router.post("/backfill/snapshots/history")
@limiter.limit("10/minute")
async def admin_backfill_snapshot_history_last_n_days(
    request: Request,
    days: int = Query(200, ge=1, le=3000),
    since_date: str | None = Query(None, description="Optional YYYY-MM-DD"),
    symbols: str | None = Query(
        None, description="Comma-separated symbols for targeted fill (e.g. 'QQQ,IWM,RSP')"
    ),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Backfill MarketSnapshotHistory for the last N trading days.

    If symbols is provided, only those symbols are processed (much faster).
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()] if symbols else None
    return enqueue_task(snapshot_last_n_days, days, since_date=since_date, symbols=symbol_list)


@router.post("/backfill/daily/since-date")
@limiter.limit("10/minute")
async def admin_backfill_daily_since_date(
    request: Request,
    since_date: str | None = Query(
        None, description="YYYY-MM-DD; omit for HISTORY_TARGET_YEARS"
    ),
    batch_size: int = Query(25, ge=1, le=200),
    index: str | None = Query(None, description="DOW30, NASDAQ100, SP500, or RUSSELL2000"),
    confirm_bandwidth: bool = Query(
        False, description="Must be true to confirm FMP bandwidth spend"
    ),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Deep daily OHLCV backfill since a given date.

    WARNING: Downloads full history from FMP (bypasses DB cache). Consumes
    significant API bandwidth. Set confirm_bandwidth=true to proceed.

    When *index* is provided, only that index's active constituents are backfilled.
    """
    if not settings.ALLOW_DEEP_BACKFILL:
        raise HTTPException(
            status_code=403,
            detail="Deep backfill is disabled (ALLOW_DEEP_BACKFILL=False). "
            "This setting protects against accidental FMP bandwidth exhaustion.",
        )
    if not confirm_bandwidth:
        raise HTTPException(
            status_code=400,
            detail="This endpoint downloads full OHLCV from FMP and consumes significant bandwidth. "
            "Pass confirm_bandwidth=true to proceed.",
        )
    effective_since = since_date or _default_history_start()
    return enqueue_task(daily_since, effective_since, batch_size, index=index)


@router.post("/backfill/since-date")
@limiter.limit("10/minute")
async def admin_backfill_since_date(
    request: Request,
    since_date: str | None = Query(
        None, description="YYYY-MM-DD; omit for HISTORY_TARGET_YEARS"
    ),
    daily_batch_size: int = Query(25, ge=1, le=200),
    history_batch_size: int = Query(50, ge=1, le=200),
    confirm_bandwidth: bool = Query(
        False, description="Must be true to confirm FMP bandwidth spend"
    ),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Backfill daily bars + indicators + snapshot history since a given date.

    WARNING: Downloads full history from FMP (bypasses DB cache). Consumes
    significant API bandwidth. Set confirm_bandwidth=true to proceed.
    """
    if not settings.ALLOW_DEEP_BACKFILL:
        raise HTTPException(
            status_code=403,
            detail="Deep backfill is disabled (ALLOW_DEEP_BACKFILL=False). "
            "This setting protects against accidental FMP bandwidth exhaustion.",
        )
    if not confirm_bandwidth:
        raise HTTPException(
            status_code=400,
            detail="This endpoint downloads full OHLCV from FMP and consumes significant bandwidth. "
            "Pass confirm_bandwidth=true to proceed.",
        )
    effective_since = since_date or _default_history_start()
    return enqueue_task(
        full_historical,
        effective_since,
        daily_batch_size=daily_batch_size,
        history_batch_size=history_batch_size,
    )


@router.post("/backfill/daily")
@limiter.limit("10/minute")
async def admin_backfill_daily_last_bars(
    request: Request,
    days: int = Query(200, ge=30, le=3000),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Backfill last N daily bars for the tracked universe."""
    return enqueue_task(daily_bars, days=days)


@router.get("/backfill/5m/toggle")
async def get_backfill_5m_toggle(
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    return {"backfill_5m_enabled": await infra.is_backfill_5m_enabled_async()}


@router.post("/backfill/5m/toggle")
@limiter.limit("10/minute")
async def set_backfill_5m_toggle(
    request: Request,
    enabled: bool = Body(..., embed=True),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    try:
        r = await infra._get_redis()
        await r.set("coverage:backfill_5m_enabled", "true" if enabled else "false")
        return {"backfill_5m_enabled": enabled}
    except Exception as e:
        logger.error(f"toggle error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update 5m backfill toggle")


@router.post("/backfill/coverage/stale")
@limiter.limit("10/minute")
async def backfill_stale_daily(
    request: Request,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Backfill daily bars for symbols currently marked stale (>48h) in coverage."""
    try:
        r = await infra._get_redis()
        tracked = await tracked_symbols_async(db, redis_async=r)
        tracked = sorted({str(s).upper() for s in (tracked or []) if s})
        if not tracked:
            tracked = sorted(
                {str(s).upper() for (s,) in db.query(PriceData.symbol).distinct().all() if s}
            )

        _, stale_full = coverage_analytics._compute_interval_coverage_for_symbols(
            db,
            symbols=tracked,
            interval="1d",
            now_utc=datetime.now(UTC),
            return_full_stale=True,
        )
        stale_candidates = len(stale_full or [])
        enq = enqueue_task(stale_daily)
        return {**enq, "stale_candidates": stale_candidates}
    except Exception as e:
        logger.exception("backfill_stale_daily failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/backfill/coverage/refresh")
@limiter.limit("10/minute")
async def admin_refresh_coverage(
    request: Request,
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Trigger the coverage health monitor to refresh Redis cache."""
    return enqueue_task(health_check)


@router.post("/backfill/coverage")
@limiter.limit("10/minute")
async def admin_backfill_daily_tracked(
    request: Request,
    history_days: int | None = Query(None, ge=1, le=300),
    history_batch_size: int = Query(25, ge=1, le=200),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Run the guided daily coverage backfill chain for the tracked universe."""
    return enqueue_task(
        daily_bootstrap,
        history_days=history_days,
        history_batch_size=history_batch_size,
    )


@router.get("/backfill/coverage/preview")
async def admin_backfill_daily_tracked_preview(
    history_days: int | None = Query(None, ge=1, le=300),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    from app.tasks.utils.task_utils import _resolve_history_days

    resolved_days = _resolve_history_days(history_days)
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=resolved_days)
    return {
        "requested_history_days": history_days,
        "resolved_history_days": int(resolved_days),
        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
    }


@router.post("/backfill/5m")
@limiter.limit("10/minute")
async def post_backfill_5m(
    request: Request,
    n_days: int = Query(5, ge=1, le=60),
    batch_size: int = Query(50, ge=10, le=200),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    return enqueue_task(bars_5m_last_n_days, n_days=n_days, batch_size=batch_size)


# ── Indicators and snapshots ──


@router.post("/recompute/since-date")
@limiter.limit("10/minute")
async def admin_recompute_since_date(
    request: Request,
    since_date: str | None = Query(
        None, description="YYYY-MM-DD; omit for HISTORY_TARGET_YEARS"
    ),
    batch_size: int = Query(50, ge=10, le=200),
    history_batch_size: int = Query(25, ge=1, le=200),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Recompute indicators + rebuild snapshot history from existing DB data.

    Safe operation — never fetches from external market data providers.
    """
    effective_since = since_date or _default_history_start()
    return enqueue_task(
        safe_recompute,
        since_date=effective_since,
        batch_size=batch_size,
        history_batch_size=history_batch_size,
    )


@router.post("/indicators/recompute-universe")
@limiter.limit("10/minute")
async def post_recompute_universe(
    request: Request,
    batch_size: int = Query(50, ge=10, le=200),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    return enqueue_task(recompute_universe, batch_size)


@router.post("/snapshots/history/record")
@limiter.limit("10/minute")
async def admin_record_history(
    request: Request,
    symbols: list[str] | None = Query(None),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    return enqueue_task(record_daily, symbols=symbols)


@router.post("/snapshots/discord-digest")
@limiter.limit("10/minute")
async def admin_send_snapshot_digest_to_discord(
    request: Request,
    channel_id: str | None = Query(None),
    limit: int = Query(12, ge=1, le=25),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Send a compact MarketSnapshot digest to Brain (path name kept for API compatibility)."""
    if not brain_webhook.webhook_url:
        raise HTTPException(status_code=400, detail="BRAIN_WEBHOOK_URL not configured")
    # channel_id retained for API compatibility; Brain routes the payload server-side.
    _ = channel_id

    tracked = await tracked_symbols_async(db, redis_async=await infra._get_redis())
    if not tracked:
        raise HTTPException(status_code=400, detail="No tracked symbols available")

    sym_set = set(tracked)
    rows = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.analysis_type == "technical_snapshot", MarketSnapshot.symbol.in_(sym_set)
        )
        .order_by(MarketSnapshot.symbol.asc(), MarketSnapshot.analysis_timestamp.desc())
        .distinct(MarketSnapshot.symbol)
        .all()
    )

    total = len(tracked)
    have = len(rows)

    stage_counts: dict[str, int] = {}
    for r in rows:
        lbl = getattr(r, "stage_label", None) or "UNKNOWN"
        stage_counts[str(lbl)] = stage_counts.get(str(lbl), 0) + 1
    stage_counts_sorted = sorted(stage_counts.items(), key=lambda kv: (-kv[1], kv[0]))

    def rs_val(r) -> float:
        try:
            v = getattr(r, "rs_mansfield_pct", None)
            return float(v) if v is not None else float("-inf")
        except Exception:
            return float("-inf")

    top_rs = sorted(rows, key=rs_val, reverse=True)[: int(limit)]
    top_lines: list[str] = []
    for r in top_rs:
        sym = getattr(r, "symbol", "")
        rs = getattr(r, "rs_mansfield_pct", None)
        stage = getattr(r, "stage_label", None) or "?"
        try:
            rs_fmt = f"{float(rs):.1f}%" if rs is not None else "-"
        except Exception:
            rs_fmt = "-"
        top_lines.append(f"- {sym}: RS {rs_fmt} - Stage {stage}")

    now = datetime.now(UTC).replace(microsecond=0).isoformat() + "Z"
    lines = [f"AxiomFolio - MarketSnapshot digest ({now})", f"Universe: {have}/{total} symbols"]
    if stage_counts_sorted:
        lines.append("Stage distribution:")
        lines.extend([f"- {k}: {v}" for k, v in stage_counts_sorted])
    if top_lines:
        lines.append(f"Top RS (top {len(top_lines)}):")
        lines.extend(top_lines)

    content = "\n".join(lines)
    ok = await brain_webhook.notify(
        "snapshot_digest",
        {
            "content": content,
            "universe_have": have,
            "universe_total": total,
        },
        user_id=_admin.id,
    )
    return {"status": "ok" if ok else "error", "sent": bool(ok), "destination": "brain"}


# ── DB history and maintenance ──


@router.get("/db/history")
async def get_db_history(
    symbol: str = Query(...),
    interval: str = Query("1d", pattern="^(1d|5m)$"),
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=20000),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return OHLCV bars for a symbol from price_data."""
    try:
        parse = lambda s: datetime.fromisoformat(s) if s else None
        df = price_bars.get_db_history(
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
        logger.exception("get_db_history failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/retention/enforce")
@limiter.limit("10/minute")
async def post_retention_enforce(
    request: Request,
    max_days_5m: int = Query(90, ge=7, le=365),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    return enqueue_task(prune_old_bars, max_days_5m=max_days_5m)


@router.post("/stage/repair")
@limiter.limit("10/minute")
async def admin_repair_stage_history(
    request: Request,
    days: int = Query(120, ge=7, le=3650),
    symbol: str | None = Query(None),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return stage_quality.repair_stage_history_window(db, days=days, symbol=symbol)


@router.post("/stage/repair-async")
@limiter.limit("10/minute")
async def admin_repair_stage_history_async(
    request: Request,
    days: int = Query(3650, ge=7, le=3650),
    symbol: str | None = Query(None),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Queue async stage repair — use for large day windows that timeout synchronously."""
    from app.tasks.market.history import repair_stage_history_async

    return enqueue_task(repair_stage_history_async, days=days, symbol=symbol)


@router.post("/fundamentals/fill-missing")
@limiter.limit("10/minute")
async def admin_fill_missing_fundamentals(
    request: Request,
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    return enqueue_task(fill_missing)


@router.post("/reconciliation/spot-check")
@limiter.limit("10/minute")
async def admin_reconciliation_spot_check(
    request: Request,
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Trigger OHLCV spot-check reconciliation."""
    from app.tasks.celery_app import celery_app

    result = celery_app.send_task("app.tasks.market.reconciliation.spot_check")
    return {"task_id": result.id, "message": "Reconciliation queued"}


# ── Job management ──


@router.get("/jobs")
async def admin_get_jobs(
    limit: int | None = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=100000),
    all: bool = Query(False),
    exclude_task: str | None = Query(None),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    base_query = db.query(JobRun)
    if exclude_task:
        excluded = [t.strip() for t in exclude_task.split(",") if t.strip()]
        if excluded:
            base_query = base_query.filter(JobRun.task_name.notin_(excluded))
    total = base_query.count()
    query = base_query.order_by(JobRun.started_at.desc())
    if all:
        rows = query.all()
        return {"jobs": serialize_job_runs(rows), "total": total, "limit": total, "offset": 0}
    effective_limit = limit or 50
    rows = query.offset(offset).limit(effective_limit).all()
    return {
        "jobs": serialize_job_runs(rows),
        "total": total,
        "limit": effective_limit,
        "offset": offset,
    }


@router.post("/jobs/recover-stale")
@limiter.limit("10/minute")
async def admin_recover_stale_jobs(
    request: Request,
    stale_minutes: int = Query(120, ge=30, le=10080),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Mark job runs stuck in RUNNING as cancelled."""
    return recover_jobs_impl(stale_minutes=stale_minutes)


# ── Regime admin ──


@router.post("/regime/compute")
@limiter.limit("10/minute")
async def admin_compute_regime(
    request: Request,
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Manually trigger daily regime computation."""
    from app.tasks.market.regime import compute_daily

    result = compute_daily.delay()
    return {"task_id": result.id, "message": "Regime computation queued"}


# ── Tasks discovery ──


@router.get("/tasks")
async def admin_list_tasks(
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Discover available market-data task actions."""
    return {"tasks": TASK_ACTIONS}


@router.post("/tasks/run")
@limiter.limit("10/minute")
async def admin_run_task(
    request: Request,
    task_name: str = Query(...),
    symbols: list[str] | None = Query(None),
    n_days: int | None = Query(None),
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Manually trigger selected tasks."""
    if task_name == "admin_backfill_5m_symbols":
        if not symbols:
            raise HTTPException(status_code=400, detail="symbols required")
        return enqueue_task(bars_5m_symbols, [s.upper() for s in symbols if s], n_days=n_days or 5)
    if task_name == "admin_backfill_5m":
        return enqueue_task(bars_5m_last_n_days, n_days=n_days or 5)
    raise HTTPException(status_code=400, detail="unsupported task")


# ── Intelligence admin ──


@router.post("/backtest/system-validation")
@limiter.limit("10/minute")
async def admin_system_backtest_validation(
    request: Request,
    _admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Run Stage Analysis backtest across all regime periods (1999-2026)."""
    from app.tasks.strategy.system_validation import validate_stage_analysis

    return enqueue_task(validate_stage_analysis)


@router.post("/intelligence/generate")
@limiter.limit("10/minute")
def trigger_brief_generation(
    request: Request,
    brief_type: str = Query("daily", description="daily, weekly, or monthly"),
    _admin: User = Depends(get_admin_user),
):
    """Manually trigger intelligence brief generation."""
    task_map = {
        "daily": "app.tasks.intelligence_tasks.generate_daily_digest",
        "weekly": "app.tasks.intelligence_tasks.generate_weekly_brief",
        "monthly": "app.tasks.intelligence_tasks.generate_monthly_review",
    }
    task_name = task_map.get(brief_type)
    if not task_name:
        raise HTTPException(status_code=400, detail=f"Invalid brief type: {brief_type}")
    from app.tasks.celery_app import celery_app

    celery_app.send_task(task_name)
    return {"status": "queued", "type": brief_type}


# ── Auto-fix ──


def _build_remediation_plan(health: dict[str, Any]) -> list[AutoFixPlanItem]:
    dims = health.get("dimensions", {})
    plan: list[AutoFixPlanItem] = []

    coverage = dims.get("coverage", {})
    if coverage.get("status") != "green":
        stale_daily = coverage.get("stale_daily", 0)
        if stale_daily > 0:
            plan.append(
                AutoFixPlanItem(
                    task="backfill_stale_daily",
                    reason=f"{stale_daily} symbols with stale daily data",
                )
            )

    stage = dims.get("stage_quality", {})
    if stage.get("status") != "green":
        unknown_rate = stage.get("unknown_rate", 0)
        invalid_count = stage.get("invalid_count", 0)
        if unknown_rate > 0.01 or invalid_count > 0:
            reasons = []
            if unknown_rate > 0.01:
                reasons.append(f"{unknown_rate * 100:.1f}% unknown stages")
            if invalid_count > 0:
                reasons.append(f"{invalid_count} invalid")
            plan.append(AutoFixPlanItem(task="recompute_indicators", reason=", ".join(reasons)))

    audit = dims.get("audit", {})
    if audit.get("status") != "green":
        daily_fill = audit.get("daily_fill_pct", 100)
        snapshot_fill = audit.get("snapshot_fill_pct", 100)
        if daily_fill < 95 or snapshot_fill < 90:
            plan.append(
                AutoFixPlanItem(
                    task="record_snapshot_history", reason=f"Daily fill {daily_fill:.1f}%"
                )
            )

    regime = dims.get("regime", {})
    if regime.get("status") != "green":
        age_hours = regime.get("age_hours", 0)
        plan.append(
            AutoFixPlanItem(task="compute_regime", reason=f"Regime data {age_hours:.1f}h old")
        )

    jobs = dims.get("jobs", {})
    if jobs.get("status") != "green":
        error_count = jobs.get("error_count", 0)
        if error_count > 0:
            plan.append(
                AutoFixPlanItem(task="recover_stale_jobs", reason=f"{error_count} failed jobs")
            )

    return plan


def _get_autofix_redis_key(job_id: str) -> str:
    return f"autofix:{job_id}"


_AUTOFIX_REDIS_TTL_S = int(timedelta(hours=2).total_seconds())


@router.post("/auto-fix", response_model=AutoFixResponse)
@limiter.limit("10/minute")
async def start_auto_fix(
    request: Request,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> AutoFixResponse:
    """Agent-powered auto-fix for all market data issues."""
    import uuid

    service = AdminHealthService()
    health = service.get_composite_health(db)
    dims = health.get("dimensions", {})
    red_dims = [k for k, v in dims.items() if v.get("status") == "red"]

    if not red_dims:
        return AutoFixResponse(status="ok", message="No issues to fix - all systems operational")

    plan = _build_remediation_plan(health)
    if not plan:
        return AutoFixResponse(
            status="ok", message="Red dimensions detected but no remediation actions available"
        )

    job_id = str(uuid.uuid4())[:8]
    r = await infra._get_redis()

    job_data = {
        "job_id": job_id,
        "status": "running",
        "plan": [item.model_dump() for item in plan],
        "started_at": datetime.now(UTC).isoformat(),
        "completed_count": 0,
        "total_count": len(plan),
        "current_task": plan[0].task if plan else None,
    }
    await r.setex(_get_autofix_redis_key(job_id), _AUTOFIX_REDIS_TTL_S, json.dumps(job_data))

    await _execute_autofix_plan(job_id, plan, r)

    return AutoFixResponse(
        status="fixing",
        job_id=job_id,
        plan=plan,
        estimated_minutes=len(plan) * 2,
        message=f"Agent fixing {len(plan)} issues",
    )


async def _execute_autofix_plan(job_id: str, plan: list[AutoFixPlanItem], r) -> None:
    from app.tasks.celery_app import celery_app

    task_map = {
        "backfill_stale_daily": "app.tasks.market.backfill.stale_daily",
        "recompute_indicators": "app.tasks.market.indicators.recompute_universe",
        "record_snapshot_history": "app.tasks.market.history.record_daily",
        "compute_regime": "app.tasks.market.regime.compute_daily",
        "recover_stale_jobs": "app.tasks.market.maintenance.recover_jobs",
    }

    task_kwargs = {
        "recover_stale_jobs": {"stale_minutes": 120},
        "recompute_indicators": {"batch_size": 50},
    }

    for item in plan:
        celery_task = task_map.get(item.task)
        if celery_task:
            kwargs = task_kwargs.get(item.task, {})
            result = celery_app.send_task(celery_task, kwargs=kwargs)
            item.task_id = result.id
            item.status = "running"
            item.started_at = datetime.now(UTC).isoformat()

    key = _get_autofix_redis_key(job_id)
    raw = await r.get(key)
    if raw:
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode()
        data = json.loads(raw)
        data["plan"] = [item.model_dump() for item in plan]
        await r.setex(key, _AUTOFIX_REDIS_TTL_S, json.dumps(data))


@router.get("/auto-fix/{job_id}/status", response_model=AutoFixStatusResponse)
async def get_auto_fix_status(
    job_id: str,
    _admin: User = Depends(get_admin_user),
) -> AutoFixStatusResponse:
    """Get the status of an auto-fix job."""
    from celery.result import AsyncResult

    from app.tasks.celery_app import celery_app

    r = await infra._get_redis()
    key = _get_autofix_redis_key(job_id)
    raw = await r.get(key)

    if not raw:
        raise HTTPException(status_code=404, detail=f"Auto-fix job {job_id} not found")

    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    data = json.loads(raw)
    plan = [AutoFixPlanItem(**item) for item in data.get("plan", [])]

    completed_count = 0
    current_task = None
    all_done = True
    has_error = False
    error_msg = None

    for item in plan:
        if item.task_id:
            result = AsyncResult(item.task_id, app=celery_app)
            if result.ready():
                if result.successful():
                    item.status = "done"
                    if not item.finished_at:
                        item.finished_at = datetime.now(UTC).isoformat()
                    completed_count += 1
                else:
                    item.status = "failed"
                    has_error = True
                    error_msg = str(result.result) if result.result else "Task failed"
                    item.error = error_msg
            elif result.state == "STARTED":
                item.status = "running"
                current_task = item.task
                all_done = False
            elif result.state == "PENDING":
                item.status = "pending"
                all_done = False
            else:
                all_done = False
        else:
            if item.status != "done":
                all_done = False

    if has_error:
        overall_status = "failed"
    elif all_done and completed_count == len(plan):
        overall_status = "completed"
    else:
        overall_status = "running"

    data["plan"] = [item.model_dump() for item in plan]
    data["status"] = overall_status
    data["completed_count"] = completed_count
    data["current_task"] = current_task
    if overall_status in ("completed", "failed"):
        data["finished_at"] = datetime.now(UTC).isoformat()

    await r.setex(key, _AUTOFIX_REDIS_TTL_S, json.dumps(data))

    return AutoFixStatusResponse(
        job_id=job_id,
        status=overall_status,
        plan=plan,
        completed_count=completed_count,
        total_count=len(plan),
        current_task=current_task,
        error=error_msg,
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
    )
