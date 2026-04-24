"""Admin HTTP surface for the corporate-action engine.

Endpoints (all require ``get_admin_user``):

* ``GET    /api/v1/admin/corporate-actions``
    Paginated list, filterable by status / symbol / date range. Used
    by the Operator Actions panel to surface any action stuck in
    PARTIAL or FAILED.
* ``GET    /api/v1/admin/corporate-actions/{id}``
    One action plus the per-user ``AppliedCorporateAction`` rows so
    the operator can audit what changed for whom.
* ``POST   /api/v1/admin/corporate-actions/{id}/apply``
    Manually trigger application of a single action (typically used
    after creating a MANUAL action via DB or after fixing a bad row).
* ``POST   /api/v1/admin/corporate-actions/{id}/reverse``
    Restore the pre-application state. Reads the
    ``AppliedCorporateAction`` snapshots and writes the original
    qty / cost basis back onto the live position / lot.

The router is mounted under ``/api/v1/admin`` by ``app.api.main``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_admin_user, get_db
from app.models import User
from app.models.corporate_action import (
    AppliedCorporateAction,
    CorporateAction,
    CorporateActionStatus,
)
from app.services.corporate_actions.applier import CorporateActionApplier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/corporate-actions", tags=["Corporate Actions"])


# ---------------------------------------------------------------------------
# Wire schemas
# ---------------------------------------------------------------------------


class CorporateActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    action_type: str
    ex_date: date
    record_date: date | None = None
    payment_date: date | None = None
    declaration_date: date | None = None
    ratio_numerator: Decimal | None = None
    ratio_denominator: Decimal | None = None
    cash_amount: Decimal | None = None
    cash_currency: str | None = None
    target_symbol: str | None = None
    source: str
    status: str
    ohlcv_adjusted: bool
    error_message: str | None = None
    applied_at: datetime | None = None
    created_at: datetime | None = None


class AppliedCorporateActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    position_id: int | None
    tax_lot_id: int | None
    symbol: str
    original_qty: Decimal
    original_cost_basis: Decimal
    original_avg_cost: Decimal | None
    adjusted_qty: Decimal
    adjusted_cost_basis: Decimal
    adjusted_avg_cost: Decimal | None
    cash_credited: Decimal | None
    applied_at: datetime


class CorporateActionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: CorporateActionOut
    applications: list[AppliedCorporateActionOut]


class ApplyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: int
    status: str
    counters: dict[str, Any]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CorporateActionOut])
def list_corporate_actions(
    status: str | None = Query(
        default=None,
        description="Filter by CorporateActionStatus value (e.g. 'pending', 'applied').",
    ),
    symbol: str | None = Query(
        default=None,
        description="Case-insensitive symbol filter.",
    ),
    since: date | None = Query(
        default=None, description="Earliest ex_date to include (inclusive)."
    ),
    until: date | None = Query(
        default=None, description="Latest ex_date to include (inclusive)."
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> list[CorporateActionOut]:
    stmt = select(CorporateAction)
    if status is not None:
        # Validate up-front so a typo returns 400, not "no rows".
        valid = {s.value for s in CorporateActionStatus}
        if status not in valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status {status!r}; expected one of {sorted(valid)}",
            )
        stmt = stmt.where(CorporateAction.status == status)
    if symbol:
        stmt = stmt.where(CorporateAction.symbol == symbol.upper())
    if since:
        stmt = stmt.where(CorporateAction.ex_date >= since)
    if until:
        stmt = stmt.where(CorporateAction.ex_date <= until)
    stmt = (
        stmt.order_by(CorporateAction.ex_date.desc(), CorporateAction.id.desc())
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(stmt).scalars().all()
    return [CorporateActionOut.model_validate(row) for row in rows]


@router.get("/{action_id}", response_model=CorporateActionDetail)
def get_corporate_action(
    action_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> CorporateActionDetail:
    action = db.get(CorporateAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="corporate action not found")
    apps = (
        db.execute(
            select(AppliedCorporateAction)
            .where(AppliedCorporateAction.corporate_action_id == action_id)
            .order_by(AppliedCorporateAction.id.asc())
        )
        .scalars()
        .all()
    )
    return CorporateActionDetail(
        action=CorporateActionOut.model_validate(action),
        applications=[AppliedCorporateActionOut.model_validate(a) for a in apps],
    )


@router.post("/{action_id}/apply", response_model=ApplyResponse)
def apply_corporate_action(
    action_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> ApplyResponse:
    action = db.get(CorporateAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="corporate action not found")

    if action.status not in (
        CorporateActionStatus.PENDING.value,
        CorporateActionStatus.PARTIAL.value,
        CorporateActionStatus.FAILED.value,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"action {action_id} is in terminal state "
                f"{action.status!r}; reverse it first if you want to re-apply"
            ),
        )

    # Force-reset to PENDING for the apply pass. The applier filters on
    # PENDING + ex_date <= today; we honor that by flipping the status
    # here AND constraining today to action.ex_date so the applier
    # picks it up even if ex_date is in the future for some reason
    # (manual rows can be backdated by the operator).
    action.status = CorporateActionStatus.PENDING.value
    action.error_message = None
    db.flush()

    applier = CorporateActionApplier(db)
    report = applier.apply_pending(today=action.ex_date)
    db.commit()

    db.refresh(action)
    return ApplyResponse(
        action_id=action.id,
        status=action.status,
        counters={
            "actions_total": report.actions_total,
            "actions_applied": report.actions_applied,
            "actions_partial": report.actions_partial,
            "actions_failed": report.actions_failed,
            "actions_skipped": report.actions_skipped,
            "positions_adjusted": report.positions_adjusted,
            "tax_lots_adjusted": report.tax_lots_adjusted,
            "ohlcv_rows_adjusted": report.ohlcv_rows_adjusted,
        },
    )


@router.post("/{action_id}/reverse", response_model=ApplyResponse)
def reverse_corporate_action(
    action_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> ApplyResponse:
    action = db.get(CorporateAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="corporate action not found")
    if action.status not in (
        CorporateActionStatus.APPLIED.value,
        CorporateActionStatus.PARTIAL.value,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"action {action_id} is in state {action.status!r}; "
                "only APPLIED / PARTIAL actions can be reversed"
            ),
        )

    applier = CorporateActionApplier(db)
    outcome = applier.reverse_action(action)
    db.commit()

    db.refresh(action)
    return ApplyResponse(
        action_id=action.id,
        status=action.status,
        counters={
            "users_processed": outcome.users_processed,
            "users_applied": outcome.users_applied,
            "users_failed": outcome.users_failed,
            "ohlcv_rows_adjusted": outcome.ohlcv_rows_adjusted,
        },
    )
