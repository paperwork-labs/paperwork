"""
Snapshot Routes
===============

Endpoints for market snapshots (current state and history).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, nullslast, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.market_data import MarketSnapshot, MarketSnapshotHistory
from backend.models.market_tracked_plan import MarketTrackedPlan
from backend.services.market.market_data_service import MarketDataService
from backend.services.market.universe import tracked_symbols
from backend.api.dependencies import get_market_data_viewer
from backend.api.rate_limit import limiter
from backend.api.schemas.market import SnapshotSingleResponse, SnapshotsListResponse
from ._shared import snapshot_preferred_columns

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


def _latest_technical_snapshot_subq(tracked: list[str]):
    """One row per symbol: latest technical_snapshot by analysis_timestamp (SQL window)."""
    ranked = func.row_number().over(
        partition_by=MarketSnapshot.symbol,
        order_by=MarketSnapshot.analysis_timestamp.desc(),
    ).label("rn")
    return (
        select(MarketSnapshot.id, ranked)
        .where(
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.symbol.in_(tracked),
        )
        .subquery()
    )


@router.get("/heatmap")
async def get_snapshot_heatmap(
    symbols: str = Query(..., description="Comma-separated symbols"),
    days: int = Query(90, ge=1, le=365),
    _viewer: User = Depends(get_market_data_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Batch heatmap endpoint — returns stage history grid for multiple symbols in one query."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return {"grid": {}, "dates": []}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)
    rows = (
        db.query(
            MarketSnapshotHistory.symbol,
            MarketSnapshotHistory.as_of_date,
            MarketSnapshotHistory.stage_label,
        )
        .filter(
            MarketSnapshotHistory.symbol.in_(symbol_list),
            MarketSnapshotHistory.analysis_type == "technical_snapshot",
            MarketSnapshotHistory.as_of_date >= cutoff,
        )
        .order_by(MarketSnapshotHistory.as_of_date.asc())
        .all()
    )
    grid: Dict[str, Dict[str, str | None]] = {}
    dates_set: set[str] = set()
    for sym, dt, stage in rows:
        d = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
        dates_set.add(d)
        grid.setdefault(sym, {})[d] = stage
    return {"grid": grid, "dates": sorted(dates_set)}


@router.get("/table")
async def get_snapshot_table(
    sort_by: str = Query("symbol", description="Sort column"),
    sort_dir: str = Query("asc", description="asc or desc"),
    filter_stage: Optional[str] = Query(
        None, description="Filter by stage prefix e.g. '2A'"
    ),
    search: Optional[str] = Query(None, description="Symbol search substring"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _viewer: User = Depends(get_market_data_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Server-side paginated, sorted, filtered snapshot table."""
    svc = MarketDataService()
    tracked = tracked_symbols(db, redis_client=svc.redis_client)
    if not tracked:
        return {"rows": [], "total": 0}

    subq = _latest_technical_snapshot_subq(tracked)
    q = (
        db.query(MarketSnapshot)
        .join(subq, MarketSnapshot.id == subq.c.id)
        .filter(subq.c.rn == 1)
    )

    if search:
        q = q.filter(MarketSnapshot.symbol.ilike(f"%{search.strip().upper()}%"))

    if filter_stage:
        stage_upper = filter_stage.upper()
        q = q.filter(func.upper(MarketSnapshot.stage_label).like(f"{stage_upper}%"))

    allowed_sort = {
        "symbol",
        "current_stage",
        "price",
        "perf_20d",
        "rs_mansfield",
        "analysis_timestamp",
    }
    effective_sort = sort_by if sort_by in allowed_sort else "symbol"
    reverse = sort_dir.lower() == "desc"

    sort_col_map = {
        "symbol": MarketSnapshot.symbol,
        "current_stage": MarketSnapshot.stage_label,
        "price": MarketSnapshot.current_price,
        "perf_20d": MarketSnapshot.perf_20d,
        "rs_mansfield": MarketSnapshot.rs_mansfield_pct,
        "analysis_timestamp": MarketSnapshot.analysis_timestamp,
    }
    sort_col = sort_col_map[effective_sort]
    primary = (
        nullslast(sort_col.desc())
        if reverse
        else nullslast(sort_col.asc())
    )
    q_ordered = q.order_by(primary, MarketSnapshot.symbol.asc())

    total = q.count()
    page = q_ordered.offset(offset).limit(limit).all()

    preferred = snapshot_preferred_columns("list")
    rows_out: list[Dict[str, Any]] = []
    for r in page:
        d: Dict[str, Any] = {}
        for col in preferred:
            val = getattr(r, col, None)
            if val is not None:
                d[col] = val
        rows_out.append(d)

    return {"rows": rows_out, "total": total}


@router.get("/history/batch")
async def get_snapshot_history_batch(
    symbols: str = Query(..., description="Comma-separated symbols"),
    days: int = Query(90, ge=1, le=365),
    _viewer: User = Depends(get_market_data_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Batch fetch snapshot history for multiple symbols (used by HeatmapView)."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if len(symbol_list) > 50:
        raise HTTPException(status_code=400, detail="Max 50 symbols per batch")
    if not symbol_list:
        return {"histories": {}, "counts": {}}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)
    rows = (
        db.query(MarketSnapshotHistory)
        .filter(
            MarketSnapshotHistory.symbol.in_(symbol_list),
            MarketSnapshotHistory.analysis_type == "technical_snapshot",
            MarketSnapshotHistory.as_of_date >= cutoff,
        )
        .order_by(
            MarketSnapshotHistory.symbol.asc(),
            MarketSnapshotHistory.as_of_date.desc(),
        )
        .all()
    )

    preferred = snapshot_preferred_columns("history")
    histories: Dict[str, list[Dict[str, Any]]] = {s: [] for s in symbol_list}
    for r in rows:
        sym = getattr(r, "symbol", None)
        if sym is None or sym not in histories:
            continue
        payload: Dict[str, Any] = {}
        for col in preferred:
            val = getattr(r, col, None)
            if val is not None:
                payload[col] = val
        histories[sym].append(payload)

    counts = {s: len(histories[s]) for s in symbol_list}
    return {"histories": histories, "counts": counts}


@router.get("/{symbol}", response_model=SnapshotSingleResponse)
async def get_snapshot(
    symbol: str,
    _viewer: User = Depends(get_market_data_viewer),
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
        return {"symbol": symbol.upper(), "snapshot": None}

    preferred = snapshot_preferred_columns("single")
    col_names = [c.name for c in row.__table__.columns]
    ordered_keys = [k for k in preferred if k in col_names]
    ordered_keys.extend([k for k in col_names if k not in set(ordered_keys)])
    payload = {k: getattr(row, k) for k in ordered_keys}
    return {"symbol": symbol.upper(), "snapshot": payload}


@router.get(
    "",
    response_model=SnapshotsListResponse,
    response_model_exclude_unset=True,
)
@limiter.limit("60/minute")
async def get_snapshots(
    request: Request,
    limit: int = Query(2000, ge=1, le=5000),
    _viewer: User = Depends(get_market_data_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return latest technical snapshots for the tracked universe from MarketSnapshot."""
    svc = MarketDataService()
    tracked = tracked_symbols(db, redis_client=svc.redis_client)
    if not tracked:
        return {"count": 0, "rows": []}

    subq = _latest_technical_snapshot_subq(tracked)
    rows = (
        db.query(MarketSnapshot)
        .join(subq, MarketSnapshot.id == subq.c.id)
        .filter(subq.c.rn == 1)
        .order_by(MarketSnapshot.symbol.asc())
        .limit(limit)
        .all()
    )

    preferred = snapshot_preferred_columns("list")
    col_names = list(getattr(MarketSnapshot, "__table__").columns.keys())
    ordered = [k for k in preferred if k in col_names]
    ordered.extend([k for k in col_names if k not in set(ordered) and k not in {"id"}])

    plan_map: dict[str, MarketTrackedPlan] = {}
    symbols = [str(getattr(r, "symbol", "")).upper() for r in rows if getattr(r, "symbol", None)]
    if symbols:
        plans = db.query(MarketTrackedPlan).filter(MarketTrackedPlan.symbol.in_(symbols)).all()
        plan_map = {str(p.symbol).upper(): p for p in plans}

    out: list[dict] = []
    for r in rows:
        payload = {k: getattr(r, k) for k in ordered}
        sym = str(payload.get("symbol") or "").upper()
        plan = plan_map.get(sym)
        payload["entry_price"] = getattr(plan, "entry_price", None) if plan else None
        payload["exit_price"] = getattr(plan, "exit_price", None) if plan else None
        out.append(payload)

    return {"count": len(out), "tracked_count": len(tracked), "rows": out}


@router.get("/{symbol}/history")
async def get_snapshot_history(
    symbol: str,
    days: int = Query(90, ge=1, le=365),
    _viewer: User = Depends(get_market_data_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get historical snapshots for a symbol."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)

    rows = (
        db.query(MarketSnapshotHistory)
        .filter(
            MarketSnapshotHistory.symbol == symbol.upper(),
            MarketSnapshotHistory.analysis_type == "technical_snapshot",
            MarketSnapshotHistory.as_of_date >= cutoff,
        )
        .order_by(MarketSnapshotHistory.as_of_date.desc())
        .all()
    )

    preferred = snapshot_preferred_columns("history")
    history = []
    for r in rows:
        payload = {}
        for col in preferred:
            val = getattr(r, col, None)
            if val is not None:
                payload[col] = val
        history.append(payload)

    return {"symbol": symbol.upper(), "history": history, "count": len(rows)}
