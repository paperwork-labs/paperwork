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
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.market_data import (
    MarketSnapshot,
    MarketSnapshotHistory,
    PriceData,
    JobRun,
)
from backend.services.market.market_data_service import MarketDataService
from backend.services.market.universe import tracked_symbols_async
from backend.services.market.admin_health_service import AdminHealthService
from backend.services.brain.webhook_client import brain_webhook
from backend.api.dependencies import get_admin_user
from backend.api.routes.utils import serialize_job_runs
from backend.config import settings
from backend.tasks.market.backfill import (
    daily_bars,
    daily_since,
    full_historical,
    safe_recompute,
    stale_daily,
)
from backend.tasks.market.coverage import daily_bootstrap, health_check
from backend.tasks.market.fundamentals import fill_missing
from backend.tasks.market.history import record_daily, snapshot_last_n_days
from backend.tasks.market.indicators import recompute_universe
from backend.tasks.market.intraday import bars_5m_last_n_days, bars_5m_symbols
from backend.tasks.market.maintenance import prune_old_bars, recover_jobs_impl
from ._shared import enqueue_task, TASK_ACTIONS

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
    task_id: Optional[str] = None
    status: str = "pending"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


class AutoFixResponse(BaseModel):
    status: str
    job_id: Optional[str] = None
    plan: List[AutoFixPlanItem] = []
    estimated_minutes: int = 0
    message: str = ""


class AutoFixStatusResponse(BaseModel):
    job_id: str
    status: str
    plan: List[AutoFixPlanItem] = []
    completed_count: int = 0
    total_count: int = 0
    current_task: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


# ── Health endpoints ──

@router.get("/health")
async def admin_composite_health(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Composite health check across coverage, stage quality, jobs, and audit."""
    svc = AdminHealthService()
    return svc.get_composite_health(db)


@router.get("/pre-market-readiness")
async def get_pre_market_readiness(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Check system readiness for next trading session."""
    svc = AdminHealthService()
    return svc.check_pre_market_readiness(db)


@router.get("/coverage/sanity")
async def admin_sanity_coverage(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Quick DB sanity checks for coverage (no Redis cache dependence)."""
    svc = MarketDataService()
    r = await svc._get_redis()
    tracked = await tracked_symbols_async(db, redis_async=r)
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


# ── Backfill endpoints ──

@router.post("/backfill/snapshots/history")
async def admin_backfill_snapshot_history_last_n_days(
    days: int = Query(200, ge=1, le=3000),
    since_date: str | None = Query(None, description="Optional YYYY-MM-DD"),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Backfill MarketSnapshotHistory for the last N trading days."""
    return enqueue_task(snapshot_last_n_days, days, since_date=since_date)


@router.post("/backfill/daily/since-date")
async def admin_backfill_daily_since_date(
    since_date: Optional[str] = Query(None, description="YYYY-MM-DD; omit for HISTORY_TARGET_YEARS"),
    batch_size: int = Query(25, ge=1, le=200),
    index: Optional[str] = Query(None, description="DOW30, NASDAQ100, SP500, or RUSSELL2000"),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Deep daily OHLCV backfill since a given date.

    When *index* is provided, only that index's active constituents are backfilled.
    """
    effective_since = since_date or _default_history_start()
    return enqueue_task(daily_since, effective_since, batch_size, index=index)


@router.post("/backfill/since-date")
async def admin_backfill_since_date(
    since_date: Optional[str] = Query(None, description="YYYY-MM-DD; omit for HISTORY_TARGET_YEARS"),
    daily_batch_size: int = Query(25, ge=1, le=200),
    history_batch_size: int = Query(50, ge=1, le=200),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Backfill daily bars + indicators + snapshot history since a given date."""
    effective_since = since_date or _default_history_start()
    return enqueue_task(
        full_historical,
        effective_since,
        daily_batch_size=daily_batch_size,
        history_batch_size=history_batch_size,
    )


@router.post("/backfill/daily")
async def admin_backfill_daily_last_bars(
    days: int = Query(200, ge=30, le=3000),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Backfill last N daily bars for the tracked universe."""
    return enqueue_task(daily_bars, days=days)


@router.get("/backfill/5m/toggle")
async def get_backfill_5m_toggle(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    svc = MarketDataService()
    return {"backfill_5m_enabled": await svc.is_backfill_5m_enabled_async()}


@router.post("/backfill/5m/toggle")
async def set_backfill_5m_toggle(
    enabled: bool = Body(..., embed=True),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    svc = MarketDataService()
    try:
        r = await svc._get_redis()
        await r.set("coverage:backfill_5m_enabled", "true" if enabled else "false")
        return {"backfill_5m_enabled": enabled}
    except Exception as e:
        logger.error(f"toggle error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update 5m backfill toggle")


@router.post("/backfill/coverage/stale")
async def backfill_stale_daily(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Backfill daily bars for symbols currently marked stale (>48h) in coverage."""
    svc = MarketDataService()
    try:
        r = await svc._get_redis()
        tracked = await tracked_symbols_async(db, redis_async=r)
        tracked = sorted({str(s).upper() for s in (tracked or []) if s})
        if not tracked:
            tracked = sorted({str(s).upper() for (s,) in db.query(PriceData.symbol).distinct().all() if s})

        _, stale_full = svc.coverage.compute_interval_coverage_for_symbols(
            db, symbols=tracked, interval="1d", now_utc=datetime.utcnow(), return_full_stale=True,
        )
        stale_candidates = len(stale_full or [])
        enq = enqueue_task(stale_daily)
        return {**enq, "stale_candidates": stale_candidates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backfill/coverage/refresh")
async def admin_refresh_coverage(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Trigger the coverage health monitor to refresh Redis cache."""
    return enqueue_task(health_check)


@router.post("/backfill/coverage")
async def admin_backfill_daily_tracked(
    history_days: int | None = Query(None, ge=1, le=300),
    history_batch_size: int = Query(25, ge=1, le=200),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
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
) -> Dict[str, Any]:
    from backend.tasks.utils.task_utils import _resolve_history_days

    resolved_days = _resolve_history_days(history_days)
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=resolved_days)
    return {
        "requested_history_days": history_days,
        "resolved_history_days": int(resolved_days),
        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
    }


@router.post("/backfill/5m")
async def post_backfill_5m(
    n_days: int = Query(5, ge=1, le=60),
    batch_size: int = Query(50, ge=10, le=200),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    return enqueue_task(bars_5m_last_n_days, n_days=n_days, batch_size=batch_size)


# ── Indicators and snapshots ──

@router.post("/recompute/since-date")
async def admin_recompute_since_date(
    since_date: Optional[str] = Query(None, description="YYYY-MM-DD; omit for HISTORY_TARGET_YEARS"),
    batch_size: int = Query(50, ge=10, le=200),
    history_batch_size: int = Query(25, ge=1, le=200),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
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
async def post_recompute_universe(
    batch_size: int = Query(50, ge=10, le=200),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    return enqueue_task(recompute_universe, batch_size)


@router.post("/snapshots/history/record")
async def admin_record_history(
    symbols: List[str] | None = Query(None),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    try:
        res = record_daily(symbols)
        return res
    except Exception as e:
        logger.error(f"admin record history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshots/discord-digest")
async def admin_send_snapshot_digest_to_discord(
    channel_id: str | None = Query(None),
    limit: int = Query(12, ge=1, le=25),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Send a compact MarketSnapshot digest to Brain (path name kept for API compatibility)."""
    if not brain_webhook.webhook_url:
        raise HTTPException(status_code=400, detail="BRAIN_WEBHOOK_URL not configured")
    # channel_id retained for API compatibility; Brain routes the payload server-side.
    _ = channel_id

    svc = MarketDataService()
    tracked = await tracked_symbols_async(db, redis_async=await svc._get_redis())
    if not tracked:
        raise HTTPException(status_code=400, detail="No tracked symbols available")

    sym_set = set(tracked)
    rows = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.analysis_type == "technical_snapshot", MarketSnapshot.symbol.in_(sym_set))
        .order_by(MarketSnapshot.symbol.asc(), MarketSnapshot.analysis_timestamp.desc())
        .distinct(MarketSnapshot.symbol)
        .all()
    )

    total = len(tracked)
    have = len(rows)

    stage_counts: Dict[str, int] = {}
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

    top_rs = sorted(rows, key=rs_val, reverse=True)[:int(limit)]
    top_lines: List[str] = []
    for r in top_rs:
        sym = getattr(r, "symbol", "")
        rs = getattr(r, "rs_mansfield_pct", None)
        stage = getattr(r, "stage_label", None) or "?"
        try:
            rs_fmt = f"{float(rs):.1f}%" if rs is not None else "-"
        except Exception:
            rs_fmt = "-"
        top_lines.append(f"- {sym}: RS {rs_fmt} - Stage {stage}")

    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
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
) -> Dict[str, Any]:
    """Return OHLCV bars for a symbol from price_data."""
    svc = MarketDataService()
    try:
        parse = lambda s: datetime.fromisoformat(s) if s else None
        df = svc.get_db_history(db, symbol=symbol.upper(), interval=interval, start=parse(start), end=parse(end), limit=limit)
        bars = []
        for ts, row in df.iterrows():
            bars.append({
                "time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "open": float(row.get("Open", 0) or 0),
                "high": float(row.get("High", 0) or 0),
                "low": float(row.get("Low", 0) or 0),
                "close": float(row.get("Close", 0) or 0),
                "volume": float(row.get("Volume", 0) or 0),
            })
        return {"symbol": symbol.upper(), "interval": interval, "bars": bars}
    except Exception as e:
        logger.error(f"db history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retention/enforce")
async def post_retention_enforce(
    max_days_5m: int = Query(90, ge=7, le=365),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    return enqueue_task(prune_old_bars, max_days_5m=max_days_5m)


@router.post("/stage/repair")
async def admin_repair_stage_history(
    days: int = Query(120, ge=7, le=3650),
    symbol: Optional[str] = Query(None),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    svc = MarketDataService()
    return svc.repair_stage_history_window(db, days=days, symbol=symbol)


@router.post("/fundamentals/fill-missing")
async def admin_fill_missing_fundamentals(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    return enqueue_task(fill_missing)


@router.post("/reconciliation/spot-check")
async def admin_reconciliation_spot_check(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Trigger OHLCV spot-check reconciliation."""
    from backend.tasks.celery_app import celery_app

    result = celery_app.send_task("backend.tasks.market.reconciliation.spot_check")
    return {"task_id": result.id, "message": "Reconciliation queued"}


# ── Job management ──

@router.get("/jobs")
async def admin_get_jobs(
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=100000),
    all: bool = Query(False),
    exclude_task: Optional[str] = Query(None),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
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
    return {"jobs": serialize_job_runs(rows), "total": total, "limit": effective_limit, "offset": offset}


@router.post("/jobs/recover-stale")
async def admin_recover_stale_jobs(
    stale_minutes: int = Query(120, ge=30, le=10080),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Mark job runs stuck in RUNNING as cancelled."""
    return recover_jobs_impl(stale_minutes=stale_minutes)


# ── Regime admin ──

@router.post("/regime/compute")
async def admin_compute_regime(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Manually trigger daily regime computation."""
    from backend.tasks.market.regime import compute_daily

    result = compute_daily.delay()
    return {"task_id": result.id, "message": "Regime computation queued"}


# ── Tasks discovery ──

@router.get("/tasks")
async def admin_list_tasks(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Discover available market-data task actions."""
    return {"tasks": TASK_ACTIONS}


@router.post("/tasks/run")
async def admin_run_task(
    task_name: str = Query(...),
    symbols: List[str] | None = Query(None),
    n_days: int | None = Query(None),
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
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
async def admin_system_backtest_validation(
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Run Stage Analysis backtest across all regime periods (1999-2026)."""
    from backend.tasks.strategy.system_validation import validate_stage_analysis

    return enqueue_task(validate_stage_analysis)


@router.post("/intelligence/generate")
def trigger_brief_generation(
    brief_type: str = Query("daily", description="daily, weekly, or monthly"),
    _admin: User = Depends(get_admin_user),
):
    """Manually trigger intelligence brief generation."""
    task_map = {
        "daily": "backend.tasks.intelligence_tasks.generate_daily_digest",
        "weekly": "backend.tasks.intelligence_tasks.generate_weekly_brief",
        "monthly": "backend.tasks.intelligence_tasks.generate_monthly_review",
    }
    task_name = task_map.get(brief_type)
    if not task_name:
        raise HTTPException(status_code=400, detail=f"Invalid brief type: {brief_type}")
    from backend.tasks.celery_app import celery_app
    celery_app.send_task(task_name)
    return {"status": "queued", "type": brief_type}


# ── Auto-fix ──

def _build_remediation_plan(health: Dict[str, Any]) -> List[AutoFixPlanItem]:
    dims = health.get("dimensions", {})
    plan: List[AutoFixPlanItem] = []

    coverage = dims.get("coverage", {})
    if coverage.get("status") != "green":
        stale_daily = coverage.get("stale_daily", 0)
        if stale_daily > 0:
            plan.append(AutoFixPlanItem(task="backfill_stale_daily", reason=f"{stale_daily} symbols with stale daily data"))

    stage = dims.get("stage_quality", {})
    if stage.get("status") != "green":
        unknown_rate = stage.get("unknown_rate", 0)
        invalid_count = stage.get("invalid_count", 0)
        if unknown_rate > 0.01 or invalid_count > 0:
            reasons = []
            if unknown_rate > 0.01:
                reasons.append(f"{unknown_rate*100:.1f}% unknown stages")
            if invalid_count > 0:
                reasons.append(f"{invalid_count} invalid")
            plan.append(AutoFixPlanItem(task="recompute_indicators", reason=", ".join(reasons)))

    audit = dims.get("audit", {})
    if audit.get("status") != "green":
        daily_fill = audit.get("daily_fill_pct", 100)
        snapshot_fill = audit.get("snapshot_fill_pct", 100)
        if daily_fill < 95 or snapshot_fill < 90:
            plan.append(AutoFixPlanItem(task="record_snapshot_history", reason=f"Daily fill {daily_fill:.1f}%"))

    regime = dims.get("regime", {})
    if regime.get("status") != "green":
        age_hours = regime.get("age_hours", 0)
        plan.append(AutoFixPlanItem(task="compute_regime", reason=f"Regime data {age_hours:.1f}h old"))

    jobs = dims.get("jobs", {})
    if jobs.get("status") != "green":
        error_count = jobs.get("error_count", 0)
        if error_count > 0:
            plan.append(AutoFixPlanItem(task="recover_stale_jobs", reason=f"{error_count} failed jobs"))

    return plan


def _get_autofix_redis_key(job_id: str) -> str:
    return f"autofix:{job_id}"


_AUTOFIX_REDIS_TTL_S = int(timedelta(hours=2).total_seconds())


@router.post("/auto-fix", response_model=AutoFixResponse)
async def start_auto_fix(
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
        return AutoFixResponse(status="ok", message="Red dimensions detected but no remediation actions available")

    job_id = str(uuid.uuid4())[:8]
    mds = MarketDataService()
    r = await mds._get_redis()

    job_data = {
        "job_id": job_id,
        "status": "running",
        "plan": [item.model_dump() for item in plan],
        "started_at": datetime.utcnow().isoformat(),
        "completed_count": 0,
        "total_count": len(plan),
        "current_task": plan[0].task if plan else None,
    }
    await r.setex(_get_autofix_redis_key(job_id), _AUTOFIX_REDIS_TTL_S, json.dumps(job_data))

    await _execute_autofix_plan(job_id, plan, r)

    return AutoFixResponse(status="fixing", job_id=job_id, plan=plan, estimated_minutes=len(plan) * 2, message=f"Agent fixing {len(plan)} issues")


async def _execute_autofix_plan(job_id: str, plan: List[AutoFixPlanItem], r) -> None:
    from backend.tasks.celery_app import celery_app

    task_map = {
        "backfill_stale_daily": "backend.tasks.market.backfill.stale_daily",
        "recompute_indicators": "backend.tasks.market.indicators.recompute_universe",
        "record_snapshot_history": "backend.tasks.market.history.record_daily",
        "compute_regime": "backend.tasks.market.regime.compute_daily",
        "recover_stale_jobs": "backend.tasks.market.maintenance.recover_jobs",
    }

    for item in plan:
        celery_task = task_map.get(item.task)
        if celery_task:
            result = celery_app.send_task(celery_task)
            item.task_id = result.id
            item.status = "running"
            item.started_at = datetime.utcnow().isoformat()

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
    from backend.tasks.celery_app import celery_app

    mds = MarketDataService()
    r = await mds._get_redis()
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
                        item.finished_at = datetime.utcnow().isoformat()
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
        data["finished_at"] = datetime.utcnow().isoformat()

    await r.setex(key, _AUTOFIX_REDIS_TTL_S, json.dumps(data))

    return AutoFixStatusResponse(
        job_id=job_id, status=overall_status, plan=plan, completed_count=completed_count,
        total_count=len(plan), current_task=current_task, error=error_msg,
        started_at=data.get("started_at"), finished_at=data.get("finished_at"),
    )
