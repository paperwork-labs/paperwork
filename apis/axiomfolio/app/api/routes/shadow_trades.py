"""Shadow (paper) autotrading read + submit routes.

All routes are scoped to ``current_user.id`` — there is no admin or
cross-tenant surface here. The ``POST /submit`` endpoint bypasses
``OrderManager`` entirely and writes directly to the ``shadow_orders``
table via :class:`ShadowOrderRecorder`, so clients can exercise the paper
path without going through preview/submit.

See D137 for the rationale behind default-ON shadow mode.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.shadow_order import ShadowOrder, ShadowOrderStatus
from app.models.user import User
from app.services.execution.shadow_order_recorder import ShadowOrderRecorder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shadow-trades", tags=["Shadow Trades"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ShadowSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(..., min_length=1, max_length=20)
    side: str = Field(..., description="buy or sell")
    quantity: Decimal = Field(..., gt=Decimal("0"))
    order_type: str = Field(default="market")
    limit_price: Optional[Decimal] = Field(default=None)
    tif: Optional[str] = Field(default=None)
    account_id: Optional[str] = Field(default=None, max_length=100)

    @field_validator("side")
    @classmethod
    def _normalize_side(cls, v: str) -> str:
        lower = (v or "").lower().strip()
        if lower not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        return lower

    @field_validator("order_type")
    @classmethod
    def _normalize_order_type(cls, v: str) -> str:
        lower = (v or "market").lower().strip()
        # TODO: re-enable stop / stop_limit when stop_price is modeled in this
        # API and the risk gate accepts the full order shape end-to-end.
        if lower not in {"market", "limit"}:
            raise ValueError("order_type must be one of: market, limit")
        return lower


def _row_to_dict(row: ShadowOrder) -> Dict[str, Any]:
    def _d(v: Any) -> Optional[str]:
        return str(v) if v is not None else None

    return {
        "id": row.id,
        "user_id": row.user_id,
        "account_id": row.account_id,
        "symbol": row.symbol,
        "side": row.side,
        "order_type": row.order_type,
        "qty": _d(row.qty),
        "limit_price": _d(row.limit_price),
        "tif": row.tif,
        "status": row.status,
        "risk_gate_verdict": row.risk_gate_verdict,
        "intended_fill_price": _d(row.intended_fill_price),
        "intended_fill_at": (
            row.intended_fill_at.isoformat()
            if row.intended_fill_at is not None
            else None
        ),
        "simulated_pnl": _d(row.simulated_pnl),
        "simulated_pnl_as_of": (
            row.simulated_pnl_as_of.isoformat()
            if row.simulated_pnl_as_of is not None
            else None
        ),
        "last_mark_price": _d(row.last_mark_price),
        "source_order_id": row.source_order_id,
        "error_message": row.error_message,
        "created_at": (
            row.created_at.isoformat() if row.created_at is not None else None
        ),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_shadow_trades(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    symbol: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List the authenticated user's shadow orders, newest first."""
    q = db.query(ShadowOrder).filter(ShadowOrder.user_id == current_user.id)
    if status_filter:
        q = q.filter(ShadowOrder.status == status_filter)
    if symbol:
        q = q.filter(ShadowOrder.symbol == symbol.upper())
    total = q.count()
    items = (
        q.order_by(ShadowOrder.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [_row_to_dict(r) for r in items],
        "total": total,
        "limit": limit,
        "offset": offset,
        "user_id": current_user.id,
    }


@router.post("/submit", status_code=status.HTTP_201_CREATED)
async def submit_shadow_trade(
    payload: ShadowSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Record a shadow (paper) order directly — bypasses ``OrderManager``.

    This path exists so clients (and tests) can exercise the recorder in
    isolation; the flag-gated divert inside ``OrderManager.submit`` remains
    the primary entry for live-path callers while shadow mode is on.
    """
    recorder = ShadowOrderRecorder(session=db)
    try:
        row = recorder.record_direct(
            user_id=current_user.id,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            order_type=payload.order_type,
            limit_price=payload.limit_price,
            tif=payload.tif,
            account_id=payload.account_id,
        )
    except (ValueError, InvalidOperation) as e:
        logger.warning(
            "shadow_trades.submit: invalid payload user_id=%s: %s",
            current_user.id,
            e,
        )
        raise HTTPException(status_code=400, detail=str(e))

    return _row_to_dict(row)


@router.get("/pnl-summary")
async def pnl_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate simulated P&L across the user's shadow book.

    The response explicitly distinguishes the four possible states a
    downstream UI must render (see .cursor/rules/no-silent-fallback.mdc):
    - ``total_orders`` may be zero (empty state)
    - ``marked`` / ``unmarked`` break out rows the MtM task has / has not
      processed yet (so the UI does not silently conflate "loading" with
      "truly zero").
    """
    open_for_mtm = (
        ShadowOrderStatus.EXECUTED_AT_SIMULATION_TIME.value,
        ShadowOrderStatus.MARKED_TO_MARKET.value,
    )

    agg = (
        db.query(
            func.count(ShadowOrder.id).label("total_orders"),
            func.coalesce(func.sum(ShadowOrder.simulated_pnl), 0).label(
                "total_pnl"
            ),
            func.sum(
                case((ShadowOrder.simulated_pnl.isnot(None), 1), else_=0)
            ).label("marked"),
            func.sum(
                case(
                    (
                        and_(
                            ShadowOrder.simulated_pnl.is_(None),
                            ShadowOrder.status.in_(open_for_mtm),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("unmarked"),
        )
        .filter(ShadowOrder.user_id == current_user.id)
        .one()
    )

    status_rows = (
        db.query(ShadowOrder.status, func.count(ShadowOrder.id))
        .filter(ShadowOrder.user_id == current_user.id)
        .group_by(ShadowOrder.status)
        .all()
    )
    by_status: Dict[str, int] = {str(s): int(c) for s, c in status_rows}

    total_pnl = agg.total_pnl
    if total_pnl is None:
        total_pnl = Decimal("0")
    elif not isinstance(total_pnl, Decimal):
        total_pnl = Decimal(str(total_pnl))

    return {
        "user_id": current_user.id,
        "total_orders": int(agg.total_orders or 0),
        "by_status": by_status,
        "marked": int(agg.marked or 0),
        "unmarked": int(agg.unmarked or 0),
        "total_simulated_pnl": str(total_pnl),
    }
