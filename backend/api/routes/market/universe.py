"""
Universe Routes
===============

Endpoints for index constituents and tracked universe management.
"""

import json
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.index_constituent import IndexConstituent
from backend.models.market_tracked_plan import MarketTrackedPlan
from backend.services.market.market_data_service import market_data_service
from backend.api.dependencies import get_market_data_viewer, get_admin_user
from backend.tasks.market.backfill import constituents, tracked_cache
from backend.tasks.market import backfill as market_backfill_tasks
from ._shared import enqueue_task, visibility_scope, tracked_education, tracked_actions

logger = logging.getLogger(__name__)

router = APIRouter(tags=["universe"])


class TrackedPlanUpdateRequest(BaseModel):
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None


@router.get("/indices/constituents")
async def get_index_constituents(
    index: str = Query("SP500", description="SP500, NASDAQ100, DOW30, RUSSELL2000"),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    index = index.upper()
    if index not in {"SP500", "NASDAQ100", "DOW30", "RUSSELL2000"}:
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
    return enqueue_task(constituents)


@router.get("/universe/tracked")
async def get_tracked(
    include_details: bool = Query(True),
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    r = market_data_service.redis_client

    all_raw = r.get("tracked:all")
    new_raw = r.get("tracked:new")
    all_symbols = sorted(json.loads(all_raw) if all_raw else [])
    new_symbols = json.loads(new_raw) if new_raw else []

    details = market_data_service.get_tracked_details(db, all_symbols) if include_details else {}

    from backend.api.dependencies import market_exposed_to_all
    meta = {
        "visibility": visibility_scope(),
        "exposed_to_all": market_exposed_to_all(),
        "education": tracked_education(),
        "actions": tracked_actions(),
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
    return enqueue_task(tracked_cache)


@router.patch("/tracked-plan/{symbol}")
async def update_tracked_plan(
    symbol: str,
    body: TrackedPlanUpdateRequest,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update entry/exit prices for a tracked symbol plan."""
    sym = symbol.upper()
    plan = db.query(MarketTrackedPlan).filter(MarketTrackedPlan.symbol == sym).first()

    if not plan:
        plan = MarketTrackedPlan(symbol=sym)
        db.add(plan)

    if body.entry_price is not None:
        plan.entry_price = body.entry_price
    if body.exit_price is not None:
        plan.exit_price = body.exit_price

    db.commit()
    db.refresh(plan)

    return {
        "symbol": plan.symbol,
        "entry_price": plan.entry_price,
        "exit_price": plan.exit_price,
    }


@router.post("/symbols/{symbol}/refresh")
async def post_refresh_symbol(
    symbol: str,
    _admin: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Delta backfill and recompute indicators for a single symbol."""
    return enqueue_task(market_backfill_tasks.symbol, symbol.upper())
