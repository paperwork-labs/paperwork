"""Portfolio order execution routes.

All order operations go through OrderManager which enforces:
- RiskGate checks BEFORE broker preview
- Single execution path through BrokerRouter
- Stage Analysis position sizing when risk_budget is provided

Mutation routes (preview, submit, cancel) require OWNER or ANALYST role.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, require_role
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.services.execution.order_manager import OrderManager
from backend.services.execution.broker_base import OrderRequest
from backend.services.execution.risk_gate import RiskViolation
from backend.services.risk.account_risk_profile import (
    AccountNotFoundError,
    get_effective_limits,
)
from backend.services.risk.firm_caps import FirmCapsUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio/orders", tags=["orders"])

# Singleton manager instance
_order_manager = OrderManager()


class OrderPreviewRequest(BaseModel):
    symbol: str
    side: str = Field(description="buy or sell")
    order_type: str = Field(default="market", description="market, limit, stop, stop_limit")
    quantity: float
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    broker_type: str = Field(default="ibkr", description="Broker to use: ibkr, schwab, tastytrade")
    account_id: Optional[int] = Field(
        default=None,
        description=(
            "Optional internal broker_accounts.id for advisory per-account "
            "risk-profile display. Enforcement remains in RiskGate."
        ),
    )


class OrderSubmitRequest(BaseModel):
    order_id: int


@router.post("/preview")
async def preview_order(
    req: OrderPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.OWNER, UserRole.ANALYST)),
):
    """Preview an order with risk checks and broker what-if. Requires OWNER or ANALYST role."""
    try:
        order_req = OrderRequest.from_user_input(
            symbol=req.symbol,
            side=req.side,
            order_type=req.order_type,
            quantity=req.quantity,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
        )
        result = await _order_manager.preview(
            db=db,
            req=order_req,
            user_id=user.id,
            broker_type=req.broker_type,
        )
    except RiskViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    # Advisory: show per-account effective risk limits alongside the preview.
    # Enforcement stays in RiskGate (Danger Zone); this is display only.
    if req.account_id is not None:
        try:
            effective = get_effective_limits(
                db=db, user_id=user.id, account_id=req.account_id
            )
            result["risk_profile_advisory"] = effective.as_dict()
        except AccountNotFoundError:
            result["risk_profile_advisory"] = None
        except FirmCapsUnavailable as exc:
            logger.warning(
                "order-preview: firm caps unavailable for user_id=%s account_id=%s: %s",
                user.id,
                req.account_id,
                exc,
            )
            result["risk_profile_advisory"] = None
    return {"data": result}


@router.post("/submit")
async def submit_order(
    req: OrderSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.OWNER, UserRole.ANALYST)),
):
    """Submit a previewed order for execution. Requires OWNER or ANALYST role."""
    result = await _order_manager.submit(db=db, order_id=req.order_id, user_id=user.id)
    err = result.get("error")
    if err:
        raise HTTPException(
            status_code=403 if err == "Forbidden" else 400, detail=err
        )
    return {"data": result}


@router.get("")
def list_orders(
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100_000),
    source: str = Query(
        "all",
        description="Which rows to return: in-app orders (app), broker-synced trades (broker), or both (all).",
    ),
    account_id: Optional[int] = Query(
        None,
        description="Optional broker_accounts.id: restrict rows to that linked account.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List in-app orders and/or broker-ledger trades for the current user."""
    src = (source or "all").strip().lower()
    if src not in ("all", "app", "broker"):
        src = "all"
    orders = _order_manager.list_orders(
        db=db,
        user_id=user.id,
        status=status,
        symbol=symbol,
        limit=limit,
        offset=offset,
        list_source=src,
        account_id=account_id,
    )
    return {"data": orders}


@router.get("/{order_id}/status")
async def poll_order_status(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Poll broker for latest order status."""
    result = await _order_manager.poll_status(
        db=db, order_id=order_id, user_id=user.id,
    )
    err = result.get("error")
    if err:
        raise HTTPException(
            status_code=403 if err == "Forbidden" else 400, detail=err
        )
    return {"data": result}


@router.get("/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single order by ID."""
    order = _order_manager.get_order(db=db, order_id=order_id, user_id=user.id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"data": order}


@router.delete("/{order_id}")
async def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.OWNER, UserRole.ANALYST)),
):
    """Cancel a submitted order. Requires OWNER or ANALYST role."""
    result = await _order_manager.cancel(
        db=db, order_id=order_id, user_id=user.id,
    )
    err = result.get("error")
    if err:
        raise HTTPException(
            status_code=403 if err == "Forbidden" else 400, detail=err
        )
    return {"data": result}
