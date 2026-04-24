"""
Admin Data Quality Routes
=========================

Read endpoints for the multi-source quorum + drift detection layer.
All endpoints are admin-only (``get_admin_user`` dependency on the
router) -- this is operations infra, not user-facing.

Endpoints:

* ``GET /api/v1/admin/data-quality/quorum-failures?days=7`` --
  recent ``DISAGREEMENT`` / ``INSUFFICIENT_PROVIDERS`` rows for the
  health dashboard.
* ``GET /api/v1/admin/data-quality/quorum-summary?days=7`` --
  aggregated counts by status; powers the headline KPIs.
* ``GET /api/v1/admin/data-quality/drift-alerts?status=open`` --
  per-provider drift events, filterable by open/resolved.
* ``POST /api/v1/admin/data-quality/drift-alerts/{id}/resolve`` --
  operator marks an alert resolved with a note.

Pydantic responses serialise ``Decimal`` as strings (no float precision
loss across the wire). Filters are clamped server-side so a careless
``?days=99999`` doesn't open a full-table scan.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_admin_user
from app.database import get_db
from app.models.provider_quorum import (
    ProviderDriftAlert,
    ProviderQuorumLog,
    QuorumStatus,
)
from app.models.user import User

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/data-quality",
    tags=["Admin Data Quality"],
    dependencies=[Depends(get_admin_user)],
)


# ---------------------------------------------------------------------------
# Wire shapes
# ---------------------------------------------------------------------------


class QuorumLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: int
    symbol: str
    field_name: str
    check_at: datetime
    providers_queried: dict[str, str | None]
    quorum_value: str | None = None
    quorum_threshold: str
    status: str
    max_disagreement_pct: str | None = None
    action_taken: str


class QuorumLogListOut(BaseModel):
    items: list[QuorumLogOut]
    total: int
    days: int


class QuorumStatusCount(BaseModel):
    status: str
    count: int


class QuorumSummaryOut(BaseModel):
    days: int
    total: int
    by_status: list[QuorumStatusCount]


class DriftAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: int
    symbol: str
    field_name: str
    provider: str
    expected_range: dict[str, Any]
    actual_value: str
    deviation_pct: str
    alert_at: datetime
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    is_open: bool


class DriftAlertListOut(BaseModel):
    items: list[DriftAlertOut]
    total: int
    status_filter: str


class ResolveDriftAlertIn(BaseModel):
    note: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Operator note describing the resolution.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp_days(days: int, lo: int = 1, hi: int = 90) -> int:
    """Clamp the ``?days=`` window to a sane range.

    Upper bound prevents a careless caller from triggering a full-
    table scan; lower bound keeps the query well-defined.
    """
    if days < lo:
        return lo
    if days > hi:
        return hi
    return days


def _row_to_quorum_out(row: ProviderQuorumLog) -> QuorumLogOut:
    return QuorumLogOut(
        id=row.id,
        symbol=row.symbol,
        field_name=row.field_name,
        check_at=row.check_at,
        providers_queried=row.providers_queried or {},
        quorum_value=(str(row.quorum_value) if row.quorum_value is not None else None),
        quorum_threshold=str(row.quorum_threshold),
        status=row.status.value if row.status else "",
        max_disagreement_pct=(
            str(row.max_disagreement_pct) if row.max_disagreement_pct is not None else None
        ),
        action_taken=row.action_taken.value if row.action_taken else "",
    )


def _row_to_drift_out(row: ProviderDriftAlert) -> DriftAlertOut:
    return DriftAlertOut(
        id=row.id,
        symbol=row.symbol,
        field_name=row.field_name,
        provider=row.provider,
        expected_range=row.expected_range or {},
        actual_value=str(row.actual_value),
        deviation_pct=str(row.deviation_pct),
        alert_at=row.alert_at,
        resolved_at=row.resolved_at,
        resolution_note=row.resolution_note,
        is_open=row.is_open(),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/quorum-failures", response_model=QuorumLogListOut)
def list_quorum_failures(
    days: int = Query(7, ge=1, le=90, description="Lookback window in days"),
    limit: int = Query(200, ge=1, le=1000),
    symbol: str | None = Query(None, max_length=32),
    field_name: str | None = Query(None, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> QuorumLogListOut:
    """Recent quorum failures (DISAGREEMENT / INSUFFICIENT_PROVIDERS)."""
    days = _clamp_days(days)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    failure_statuses = [
        QuorumStatus.DISAGREEMENT,
        QuorumStatus.INSUFFICIENT_PROVIDERS,
    ]

    query = (
        db.query(ProviderQuorumLog)
        .filter(ProviderQuorumLog.check_at >= cutoff)
        .filter(ProviderQuorumLog.status.in_(failure_statuses))
    )
    if symbol:
        query = query.filter(ProviderQuorumLog.symbol == symbol.upper())
    if field_name:
        query = query.filter(ProviderQuorumLog.field_name == field_name.upper())

    total = query.count()
    rows = query.order_by(ProviderQuorumLog.check_at.desc()).limit(limit).all()
    return QuorumLogListOut(
        items=[_row_to_quorum_out(r) for r in rows],
        total=total,
        days=days,
    )


@router.get("/quorum-summary", response_model=QuorumSummaryOut)
def quorum_summary(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> QuorumSummaryOut:
    """Counts by status over the lookback window. Powers KPI tiles."""
    days = _clamp_days(days)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    rows = (
        db.query(
            ProviderQuorumLog.status,
            func.count(ProviderQuorumLog.id).label("n"),
        )
        .filter(ProviderQuorumLog.check_at >= cutoff)
        .group_by(ProviderQuorumLog.status)
        .all()
    )
    by_status = [
        QuorumStatusCount(
            status=row.status.value if row.status else "UNKNOWN",
            count=int(row.n),
        )
        for row in rows
    ]
    total = sum(item.count for item in by_status)
    return QuorumSummaryOut(days=days, total=total, by_status=by_status)


@router.get("/drift-alerts", response_model=DriftAlertListOut)
def list_drift_alerts(
    status_filter: str = Query(
        "open",
        alias="status",
        pattern="^(open|resolved|all)$",
        description="open | resolved | all",
    ),
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(200, ge=1, le=1000),
    symbol: str | None = Query(None, max_length=32),
    provider: str | None = Query(None, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> DriftAlertListOut:
    """Drift alerts filterable by open/resolved/all."""
    days = _clamp_days(days, hi=180)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    query = db.query(ProviderDriftAlert).filter(ProviderDriftAlert.alert_at >= cutoff)
    if status_filter == "open":
        query = query.filter(ProviderDriftAlert.resolved_at.is_(None))
    elif status_filter == "resolved":
        query = query.filter(ProviderDriftAlert.resolved_at.isnot(None))
    if symbol:
        query = query.filter(ProviderDriftAlert.symbol == symbol.upper())
    if provider:
        query = query.filter(ProviderDriftAlert.provider == provider)

    total = query.count()
    rows = query.order_by(ProviderDriftAlert.alert_at.desc()).limit(limit).all()
    return DriftAlertListOut(
        items=[_row_to_drift_out(r) for r in rows],
        total=total,
        status_filter=status_filter,
    )


@router.post(
    "/drift-alerts/{alert_id}/resolve",
    response_model=DriftAlertOut,
    status_code=status.HTTP_200_OK,
)
def resolve_drift_alert(
    alert_id: int,
    payload: ResolveDriftAlertIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> DriftAlertOut:
    """Mark a drift alert resolved with an operator note.

    Idempotent w.r.t. note overwrite: re-resolving an already-resolved
    alert updates the note and ``resolved_at`` rather than 409-ing,
    so an operator can correct a typo.
    """
    row = db.query(ProviderDriftAlert).filter(ProviderDriftAlert.id == alert_id).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drift alert {alert_id} not found",
        )

    row.resolved_at = datetime.now(UTC)
    row.resolution_note = payload.note.strip()
    db.commit()
    db.refresh(row)

    logger.info(
        "drift alert resolved id=%s symbol=%s provider=%s by_user=%s",
        row.id,
        row.symbol,
        row.provider,
        getattr(current_user, "id", None),
    )
    return _row_to_drift_out(row)
