"""
Brain-compatible HTTP tool endpoints (machine-to-machine).

Auth: header X-Brain-Api-Key matching settings.BRAIN_API_KEY.
Portfolio and orders use settings.BRAIN_TOOLS_USER_ID (default 1).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.dependencies import verify_brain_api_key
from backend.config import settings
from backend.database import get_db
from backend.models import BrokerAccount, Option, Position
from backend.models.order import Order, OrderStatus
from backend.models.user import User
from backend.models.market_data import MarketSnapshot
from backend.services.execution.approval_service import ApprovalService
from backend.services.execution.broker_base import OrderRequest
from backend.services.execution.order_manager import OrderManager
from backend.services.market.regime_engine import get_current_regime as fetch_current_regime
from backend.services.portfolio.portfolio_analytics_service import PortfolioAnalyticsService
from backend.services.risk.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_brain_api_key)])


def _brain_user_id() -> int:
    return int(settings.BRAIN_TOOLS_USER_ID)


def _f(v: Optional[float]) -> Optional[float]:
    return float(v) if v is not None else None


def _latest_technical_snapshot(db: Session, symbol: str) -> Optional[MarketSnapshot]:
    sym = symbol.upper()
    return (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.symbol == sym,
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.is_valid.is_(True),
        )
        .order_by(MarketSnapshot.id.desc())
        .first()
    )


@router.get("/portfolio")
async def tools_portfolio(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Portfolio summary: P&L, exposure, risk and sector attribution."""
    uid = _brain_user_id()
    pos_models = db.query(Position).filter(Position.user_id == uid).all()
    positions: List[Dict[str, Any]] = []
    long_notional = 0.0
    short_notional = 0.0
    for p in pos_models:
        qty = float(p.quantity or 0)
        mv = float(p.market_value or 0)
        if qty > 0:
            long_notional += mv
        elif qty < 0:
            short_notional += abs(mv)
        positions.append({
            "symbol": p.symbol,
            "quantity": qty,
            "market_value": mv,
            "unrealized_pnl": _f(p.unrealized_pnl),
            "total_cost_basis": _f(p.total_cost_basis),
            "sector": (p.sector or "").strip() or None,
        })

    option_models = db.query(Option).filter(
        Option.user_id == uid, Option.open_quantity != 0
    ).all()
    options_mv = sum(
        float(o.current_price or 0)
        * abs(float(o.open_quantity or 0))
        * float(o.multiplier or 100)
        for o in option_models
    )
    options_unrealized = sum(float(o.unrealized_pnl or 0) for o in option_models)

    total_equity_mv = sum(p["market_value"] for p in positions) + options_mv
    total_cost = sum(float(p.total_cost_basis or 0) for p in pos_models)
    unrealized_equity = sum(float(p.unrealized_pnl or 0) for p in pos_models)

    analytics = PortfolioAnalyticsService()
    risk_metrics = analytics.compute_risk_metrics(db, uid)
    sector_attribution = analytics.compute_sector_attribution(db, uid)

    accounts = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.user_id == uid, BrokerAccount.is_enabled.is_(True))
        .all()
    )
    account_rows = []
    for acc in accounts:
        account_rows.append({
            "broker": acc.broker,
            "account_number_suffix": acc.account_number[-4:]
            if acc.account_number
            else None,
            "total_value": _f(acc.total_value),
            "day_pnl": _f(acc.day_pnl),
            "total_pnl": _f(acc.total_pnl),
        })

    return {
        "user_id": uid,
        "as_of": datetime.utcnow().isoformat(),
        "summary": {
            "total_market_value": total_equity_mv,
            "total_cost_basis": total_cost,
            "unrealized_pnl_equity": unrealized_equity,
            "unrealized_pnl_options": options_unrealized,
            "positions_count": len(positions),
            "options_positions_count": len(option_models),
        },
        "exposure": {
            "long_notional": long_notional,
            "short_notional": short_notional,
            "gross_notional": long_notional + short_notional,
            "net_notional": long_notional - short_notional,
            "options_market_value": options_mv,
        },
        "risk_metrics": risk_metrics,
        "sector_attribution": sector_attribution,
        "accounts": account_rows,
        "positions": positions,
    }


@router.get("/regime")
async def tools_regime(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Latest market regime (R1–R5) and inputs."""
    regime = fetch_current_regime(db)
    if regime is None:
        return {"regime": None, "message": "No regime data computed yet"}
    return {
        "regime": {
            "as_of_date": regime.as_of_date.isoformat() if regime.as_of_date else None,
            "regime_state": regime.regime_state,
            "composite_score": regime.composite_score,
            "vix_spot": regime.vix_spot,
            "pct_above_200d": regime.pct_above_200d,
            "pct_above_50d": regime.pct_above_50d,
            "regime_multiplier": regime.regime_multiplier,
            "max_equity_exposure_pct": regime.max_equity_exposure_pct,
            "cash_floor_pct": regime.cash_floor_pct,
        }
    }


@router.get("/stage/{symbol}")
async def tools_stage(
    symbol: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Stage Analysis and key indicators for one symbol (latest technical snapshot)."""
    snap = _latest_technical_snapshot(db, symbol)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"No snapshot for {symbol.upper()}")
    return {
        "symbol": snap.symbol,
        "analysis_timestamp": snap.analysis_timestamp.isoformat()
        if snap.analysis_timestamp
        else None,
        "stage": snap.stage_label,
        "sub_stage": snap.stage_label,
        "stage_4h": snap.stage_4h,
        "stage_confirmed": snap.stage_confirmed,
        "rs_mansfield_pct": _f(snap.rs_mansfield_pct),
        "scan_tier": snap.scan_tier,
        "action_label": snap.action_label,
        "regime_state": snap.regime_state,
        "indicators": {
            "current_price": _f(snap.current_price),
            "sma_50": _f(snap.sma_50),
            "sma_150": _f(snap.sma_150),
            "sma_200": _f(snap.sma_200),
            "rsi": _f(snap.rsi),
            "atrp_14": _f(snap.atrp_14),
            "ext_pct": _f(snap.ext_pct),
            "ema10_dist_n": _f(snap.ema10_dist_n),
            "vol_ratio": _f(snap.vol_ratio),
            "sma150_slope": _f(snap.sma150_slope),
        },
    }


@router.get("/scan")
async def tools_scan(
    db: Session = Depends(get_db),
    scan_tier: Optional[str] = Query(None, description="Filter by scan tier, e.g. Breakout Elite"),
    limit: int = Query(50, ge=1, le=500),
) -> Dict[str, Any]:
    """Scan candidates: latest technical snapshot per symbol with a scan tier."""
    tier_filter = [MarketSnapshot.scan_tier.isnot(None)]
    if scan_tier:
        tier_filter.append(MarketSnapshot.scan_tier == scan_tier)
    latest_ids_sub = (
        db.query(func.max(MarketSnapshot.id).label("id"))
        .filter(
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.is_valid.is_(True),
            *tier_filter,
        )
        .group_by(MarketSnapshot.symbol)
        .subquery()
    )
    query = db.query(MarketSnapshot).join(
        latest_ids_sub, MarketSnapshot.id == latest_ids_sub.c.id
    )
    rows = (
        query.order_by(MarketSnapshot.rs_mansfield_pct.desc().nullslast())
        .limit(limit)
        .all()
    )
    candidates: List[Dict[str, Any]] = []
    for r in rows:
        candidates.append({
            "symbol": r.symbol,
            "name": r.name,
            "stage": r.stage_label,
            "scan_tier": r.scan_tier,
            "action_label": r.action_label,
            "rs_mansfield_pct": _f(r.rs_mansfield_pct),
            "sector": r.sector,
        })
    return {
        "scan_tier_filter": scan_tier,
        "count": len(candidates),
        "candidates": candidates,
    }


@router.get("/risk")
async def tools_risk() -> Dict[str, Any]:
    """Circuit breaker status."""
    return circuit_breaker.get_status()


class PreviewTradeBody(BaseModel):
    symbol: str = Field(..., min_length=1)
    side: str = Field(..., description="buy or sell")
    quantity: float = Field(..., gt=0)
    order_type: str = Field(default="market", description="market, limit, stop, stop_limit")
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None


@router.post("/preview-trade")
async def tools_preview_trade(
    body: PreviewTradeBody,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a PREVIEW order (broker what-if + persisted row)."""
    uid = _brain_user_id()
    try:
        req = OrderRequest.from_user_input(
            symbol=body.symbol.strip(),
            side=body.side,
            order_type=body.order_type,
            quantity=body.quantity,
            limit_price=body.limit_price,
            stop_price=body.stop_price,
        )
    except Exception as e:
        logger.warning("Brain preview-trade bad request: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e

    manager = OrderManager()
    result = await manager.preview(db, req, user_id=uid)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class ExecuteTradeBody(BaseModel):
    order_id: int = Field(..., ge=1)


@router.post("/execute-trade")
async def tools_execute_trade(
    body: ExecuteTradeBody,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit a preview order via OrderManager, or queue for approval when configured."""
    uid = _brain_user_id()
    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        raise HTTPException(
            status_code=400,
            detail=f"User id {uid} (BRAIN_TOOLS_USER_ID) not found",
        )

    order = (
        db.query(Order)
        .filter(Order.id == body.order_id, Order.user_id == uid)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status == OrderStatus.PENDING_APPROVAL.value:
        raise HTTPException(
            status_code=409,
            detail="Order is pending approval; wait for owner approval or reject",
        )

    if order.status == OrderStatus.PREVIEW.value and ApprovalService.requires_approval(
        order, user
    ):
        return await ApprovalService.request_approval(db, order, user)

    manager = OrderManager()
    result = await manager.submit(db, body.order_id, uid)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class ApproveTradeBody(BaseModel):
    order_id: int = Field(..., ge=1)
    approver_user_id: int = Field(..., ge=1)


@router.post("/approve-trade")
async def tools_approve_trade(
    body: ApproveTradeBody,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Approve a pending order (owner only); returns to PREVIEW for execute-trade."""
    approver = db.query(User).filter(User.id == body.approver_user_id).first()
    if approver is None:
        raise HTTPException(status_code=404, detail="Approver user not found")
    result = await ApprovalService.approve(db, body.order_id, approver)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class RejectTradeBody(BaseModel):
    order_id: int = Field(..., ge=1)
    rejector_user_id: int = Field(..., ge=1)
    reason: Optional[str] = Field(None, max_length=500)


@router.post("/reject-trade")
async def tools_reject_trade(
    body: RejectTradeBody,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Reject a pending or preview order."""
    rejector = db.query(User).filter(User.id == body.rejector_user_id).first()
    if rejector is None:
        raise HTTPException(status_code=404, detail="Rejector user not found")
    result = await ApprovalService.reject(
        db, body.order_id, rejector, reason=body.reason
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result
