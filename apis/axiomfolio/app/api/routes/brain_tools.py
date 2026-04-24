"""
Brain-compatible HTTP tool endpoints (machine-to-machine).

Auth: header X-Brain-Api-Key matching settings.BRAIN_API_KEY.
Tenant scoping: header X-Axiom-User-Id selects the target user.
``settings.BRAIN_TOOLS_USER_ID`` is a deprecated last-resort fallback
when the caller omits the header (logged at WARNING so we can drive
the deprecation campaign).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import verify_brain_api_key
from app.config import settings
from app.database import get_db
from app.models import BrokerAccount, Option, Position
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.models.market_data import MarketSnapshot
from app.services.execution.approval_service import ApprovalService
from app.services.execution.broker_base import OrderRequest
from app.services.execution.order_manager import OrderManager
from app.services.market.regime_engine import get_current_regime as fetch_current_regime
from app.services.silver.portfolio.analytics import PortfolioAnalyticsService
from app.services.risk.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_brain_api_key)])


def brain_user_id_dep(
    x_axiom_user_id: Optional[str] = Header(None, alias="X-Axiom-User-Id"),
) -> int:
    """Resolve the M2M caller's target user.

    Order:
      1. Explicit ``X-Axiom-User-Id`` header (preferred, scoped per tenant).
      2. Fallback to ``settings.BRAIN_TOOLS_USER_ID`` (deprecated; logs a
         WARNING for every use so we can drive the deprecation campaign).
    """
    if x_axiom_user_id:
        try:
            return int(x_axiom_user_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid X-Axiom-User-Id header: {exc}",
            )
    logger.warning(
        "brain_tools: M2M call without X-Axiom-User-Id; "
        "falling back to BRAIN_TOOLS_USER_ID=%s (deprecated)",
        settings.BRAIN_TOOLS_USER_ID,
    )
    return int(settings.BRAIN_TOOLS_USER_ID)


def _brain_user_id() -> int:
    """Legacy helper preserved for paths that haven't migrated to the
    dependency yet. Always logs a WARNING so we can find every caller.
    """
    logger.warning(
        "brain_tools._brain_user_id() invoked without dependency injection; "
        "use Depends(brain_user_id_dep) instead. user_id=%s",
        settings.BRAIN_TOOLS_USER_ID,
    )
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
    uid: int = Depends(brain_user_id_dep),
) -> Dict[str, Any]:
    """Portfolio summary: P&L, exposure, risk and sector attribution."""
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
        "as_of": datetime.now(timezone.utc).isoformat(),
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
    uid: int = Depends(brain_user_id_dep),
) -> Dict[str, Any]:
    """Create a PREVIEW order (broker what-if + persisted row)."""
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
    uid: int = Depends(brain_user_id_dep),
) -> Dict[str, Any]:
    """Submit a preview order via OrderManager, or queue for approval when configured."""
    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        raise HTTPException(
            status_code=400,
            detail=f"User id {uid} not found",
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


@router.post("/approve-trade")
async def tools_approve_trade(
    body: ApproveTradeBody,
    db: Session = Depends(get_db),
    uid: int = Depends(brain_user_id_dep),
) -> Dict[str, Any]:
    """Approve a pending order (owner only); returns to PREVIEW for execute-trade."""
    approver = db.query(User).filter(User.id == uid).first()
    if approver is None:
        raise HTTPException(
            status_code=400,
            detail=f"User id {uid} not found",
        )
    order = (
        db.query(Order)
        .filter(Order.id == body.order_id, Order.user_id == uid)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    result = await ApprovalService.approve(db, body.order_id, approver)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class RejectTradeBody(BaseModel):
    order_id: int = Field(..., ge=1)
    reason: Optional[str] = Field(None, max_length=500)


@router.post("/reject-trade")
async def tools_reject_trade(
    body: RejectTradeBody,
    db: Session = Depends(get_db),
    uid: int = Depends(brain_user_id_dep),
) -> Dict[str, Any]:
    """Reject a pending or preview order."""
    rejector = db.query(User).filter(User.id == uid).first()
    if rejector is None:
        raise HTTPException(
            status_code=400,
            detail=f"User id {uid} not found",
        )
    order = (
        db.query(Order)
        .filter(Order.id == body.order_id, Order.user_id == uid)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    result = await ApprovalService.reject(
        db, body.order_id, rejector, reason=body.reason
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ========================= SCHEDULE MANAGEMENT =========================


class RunTaskBody(BaseModel):
    task_id: str = Field(..., min_length=1, description="Catalog task ID, e.g. admin_coverage_backfill")


@router.get("/schedules")
async def tools_list_schedules(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all scheduled tasks from the job catalog with last run status."""
    from app.tasks.job_catalog import CATALOG
    from app.models.market_data import JobRun

    labels = [j.job_run_label for j in CATALOG if j.job_run_label]
    latest_runs: Dict[str, JobRun] = {}
    if labels:
        try:
            subq = (
                db.query(
                    JobRun.task_name,
                    func.max(JobRun.started_at).label("max_started"),
                )
                .filter(JobRun.task_name.in_(labels))
                .group_by(JobRun.task_name)
                .subquery()
            )
            runs = (
                db.query(JobRun)
                .join(
                    subq,
                    (JobRun.task_name == subq.c.task_name)
                    & (JobRun.started_at == subq.c.max_started),
                )
                .all()
            )
            latest_runs = {r.task_name: r for r in runs}
        except Exception:
            logger.exception(
                "Failed to batch-fetch latest JobRun rows for schedules (labels=%s)",
                labels,
            )

    schedules = []
    for job in CATALOG:
        entry: Dict[str, Any] = {
            "id": job.id,
            "display_name": job.display_name,
            "group": job.group,
            "task": job.task,
            "cron": job.default_cron,
            "timezone": job.default_tz,
        }
        if job.job_run_label:
            try:
                last = latest_runs.get(job.job_run_label)
                if last:
                    entry["last_run"] = {
                        "status": last.status,
                        "started_at": last.started_at.isoformat() if last.started_at else None,
                        "finished_at": last.finished_at.isoformat() if last.finished_at else None,
                    }
            except Exception:
                logger.exception(
                    "Failed to fetch last JobRun for job id=%s label=%s",
                    job.id,
                    getattr(job, "job_run_label", None),
                )
        schedules.append(entry)

    return {"schedules": schedules, "count": len(schedules), "scheduler": "celery_beat"}


@router.post("/run-task")
async def tools_run_task(
    body: RunTaskBody,
) -> Dict[str, Any]:
    """Trigger a catalog task to run immediately via Celery."""
    from app.tasks.job_catalog import CATALOG
    from app.tasks.celery_app import celery_app

    catalog_map = {j.id: j for j in CATALOG}
    job = catalog_map.get(body.task_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown task_id: {body.task_id}",
        )

    try:
        result = celery_app.send_task(
            job.task,
            kwargs=job.kwargs or {},
            args=job.args or [],
            queue=job.queue or "celery",
        )
        return {
            "status": "dispatched",
            "task_id": result.id,
            "task": job.task,
            "display_name": job.display_name,
        }
    except Exception as e:
        logger.warning("run-task failed for %s: %s", body.task_id, e)
        raise HTTPException(status_code=500, detail="Failed to dispatch task") from e


# ========================= APPROVAL MANAGEMENT =========================


@router.get("/pending-approvals")
async def tools_pending_approvals(
    db: Session = Depends(get_db),
    uid: int = Depends(brain_user_id_dep),
) -> Dict[str, Any]:
    """List orders currently awaiting approval with timeout info."""
    pending = ApprovalService.list_pending(db, uid)
    return {"count": len(pending), "orders": pending}
