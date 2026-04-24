"""Position sleeve tagging endpoints.

``PATCH /api/v1/positions/{position_id}/sleeve``
    Flip a single position between the ``active`` and ``conviction``
    sleeves. Caller must own the position (404 otherwise — we do not
    leak existence of other users' positions).

``GET /api/v1/positions/by-sleeve``
    Return the caller's positions grouped by sleeve. Used by the
    dashboard's "Active Book" / "Conviction Book" toggles.

All responses are per-user; no cross-tenant leakage. No monetary math
here — pure tagging. Four explicit response states on error (loading is
client-side only): success / not_found / invalid_sleeve /
unexpected_error.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.position import Position, PositionStatus, Sleeve
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


class SleeveUpdateRequest(BaseModel):
    sleeve: str = Field(..., description="One of: active, conviction")


class SleeveUpdateResponse(BaseModel):
    id: int
    symbol: str
    sleeve: str


def _coerce_sleeve(raw: str) -> Sleeve:
    try:
        return Sleeve(raw.strip().lower())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid sleeve '{raw}' — expected one of {[s.value for s in Sleeve]}",
        ) from e


@router.patch("/positions/{position_id}/sleeve", response_model=SleeveUpdateResponse)
def update_position_sleeve(
    position_id: int,
    body: SleeveUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SleeveUpdateResponse:
    """Flip a position between active and conviction sleeve."""
    sleeve = _coerce_sleeve(body.sleeve)

    pos = (
        db.query(Position)
        .filter(
            Position.id == position_id,
            Position.user_id == current_user.id,
        )
        .one_or_none()
    )
    if pos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="position not found",
        )

    previous = pos.sleeve or Sleeve.ACTIVE.value
    pos.sleeve = sleeve.value
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(
            "sleeve update commit failed for position %s user %s: %s",
            position_id,
            current_user.id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to persist sleeve change",
        ) from e
    db.refresh(pos)
    logger.info(
        "position sleeve change: position_id=%s user_id=%s %s -> %s",
        position_id,
        current_user.id,
        previous,
        pos.sleeve,
    )
    return SleeveUpdateResponse(id=pos.id, symbol=pos.symbol, sleeve=pos.sleeve)


def _serialize_position(pos: Position) -> dict[str, Any]:
    return {
        "id": pos.id,
        "symbol": pos.symbol,
        "account_id": pos.account_id,
        "quantity": str(pos.quantity) if pos.quantity is not None else None,
        "market_value": (str(pos.market_value) if pos.market_value is not None else None),
        "unrealized_pnl": (str(pos.unrealized_pnl) if pos.unrealized_pnl is not None else None),
        "unrealized_pnl_pct": (
            str(pos.unrealized_pnl_pct) if pos.unrealized_pnl_pct is not None else None
        ),
        "runner_since": pos.runner_since.isoformat() if pos.runner_since else None,
        "sleeve": pos.sleeve or Sleeve.ACTIVE.value,
    }


@router.get("/positions/by-sleeve")
def list_positions_by_sleeve(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the caller's open positions grouped by sleeve."""
    rows: list[Position] = (
        db.query(Position)
        .filter(
            Position.user_id == current_user.id,
            Position.status == PositionStatus.OPEN,
        )
        .all()
    )

    buckets: dict[str, list[dict[str, Any]]] = {s.value: [] for s in Sleeve}
    for p in rows:
        key = (p.sleeve or Sleeve.ACTIVE.value).lower()
        if key not in buckets:
            # Defensive: unknown sleeve value from a future migration.
            # Surface it as its own bucket rather than silently coercing
            # (no-silent-fallback rule).
            buckets[key] = []
        buckets[key].append(_serialize_position(p))

    totals = {k: len(v) for k, v in buckets.items()}
    return {
        "items_by_sleeve": buckets,
        "totals": totals,
        "total": sum(totals.values()),
    }
