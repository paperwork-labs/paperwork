"""
Snapshot Routes
===============

Endpoints for market snapshots (current state and history).
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.market_data import MarketSnapshot, MarketSnapshotHistory
from backend.models.market_tracked_plan import MarketTrackedPlan
from backend.services.market.market_data_service import MarketDataService
from backend.services.market.universe import tracked_symbols
from backend.api.dependencies import get_optional_user
from ._shared import snapshot_preferred_columns

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("/{symbol}")
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
        return {"symbol": symbol.upper(), "snapshot": None}

    preferred = snapshot_preferred_columns("single")
    col_names = [c.name for c in row.__table__.columns]
    ordered_keys = [k for k in preferred if k in col_names]
    ordered_keys.extend([k for k in col_names if k not in set(ordered_keys)])
    payload = {k: getattr(row, k) for k in ordered_keys}
    return {"symbol": symbol.upper(), "snapshot": payload}


@router.get("")
async def get_snapshots(
    limit: int = Query(2000, ge=1, le=5000),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return latest technical snapshots for the tracked universe from MarketSnapshot."""
    svc = MarketDataService()
    tracked = tracked_symbols(db, redis_client=svc.redis_client)
    if not tracked:
        return {"count": 0, "rows": []}

    base_query = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.symbol.in_(tracked),
        )
        .order_by(MarketSnapshot.symbol.asc(), MarketSnapshot.analysis_timestamp.desc())
    )

    bind = getattr(db, "bind", None)
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect_name == "postgresql" and hasattr(base_query, "distinct"):
        rows = base_query.distinct(MarketSnapshot.symbol).limit(limit).all()
    else:
        raw_rows = base_query.all()
        latest_rows: list[MarketSnapshot] = []
        seen_symbols: set[str] = set()
        for row in raw_rows:
            sym = str(getattr(row, "symbol", "")).upper()
            if not sym or sym in seen_symbols:
                continue
            seen_symbols.add(sym)
            latest_rows.append(row)
            if len(latest_rows) >= limit:
                break
        rows = latest_rows

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
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get historical snapshots for a symbol."""
    cutoff = datetime.utcnow() - timedelta(days=days)

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
