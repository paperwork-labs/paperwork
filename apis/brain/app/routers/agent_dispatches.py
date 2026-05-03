"""Agent dispatches CRUD + cost summary API.

Tracks every Task subagent dispatch with T-Shirt size, model, and cost.
Feeds the Studio /admin/cost dashboard.

Routes:
  POST   /v1/agents/dispatches           — create a dispatch record
  GET    /v1/agents/dispatches           — list dispatches (filtered)
  PATCH  /v1/agents/dispatches/{id}      — update outcome / cost
  GET    /v1/agents/dispatches/cost-summary — cost rollups for charts

medallion: ops
"""

from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select, text

from app.config import settings
from app.database import get_db
from app.models.agent_dispatch import (
    MODEL_TO_SIZE,
    SIZE_COST_CENTS,
    AgentDispatch,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DispatchCreateRequest(BaseModel):
    model_used: str = Field(..., description="Model slug (must be in cheap allow-list)")
    t_shirt_size: str | None = Field(
        None,
        description="Derived from model_used if omitted",
    )
    workstream_id: str | None = None
    subagent_type: str | None = None
    task_summary: str | None = Field(None, max_length=500)
    branch: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    dispatched_by: str = Field(default="opus-orchestrator")
    outcome: str = "pending"

    @model_validator(mode="after")
    def _validate_and_derive(self) -> DispatchCreateRequest:
        model = self.model_used.strip()

        if "opus" in model.lower():
            raise ValueError(
                f"Model '{model}' contains 'opus' and is FORBIDDEN as a subagent dispatch. "
                "Opus is orchestrator-only. Use a cheap model (XS-L). "
                "See cheap-agent-fleet.mdc Rule #2."
            )

        if model not in MODEL_TO_SIZE:
            raise ValueError(
                f"Model '{model}' is not in the T-Shirt Size allow-list. "
                f"Allowed: {', '.join(sorted(MODEL_TO_SIZE))}. "
                "See docs/PR_TSHIRT_SIZING.md."
            )

        self.t_shirt_size = MODEL_TO_SIZE[model]
        return self


class DispatchResponse(BaseModel):
    id: str
    organization_id: str
    workstream_id: str | None
    t_shirt_size: str
    model_used: str
    subagent_type: str | None
    task_summary: str | None
    branch: str | None
    pr_number: int | None
    pr_url: str | None
    dispatched_at: datetime
    completed_at: datetime | None
    estimated_cost_cents: int | None
    actual_cost_cents: int | None
    outcome: str
    dispatched_by: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_row(cls, row: AgentDispatch) -> DispatchResponse:
        return cls(
            id=str(row.id),
            organization_id=row.organization_id,
            workstream_id=row.workstream_id,
            t_shirt_size=row.t_shirt_size,
            model_used=row.model_used,
            subagent_type=row.subagent_type,
            task_summary=row.task_summary,
            branch=row.branch,
            pr_number=row.pr_number,
            pr_url=row.pr_url,
            dispatched_at=row.dispatched_at,
            completed_at=row.completed_at,
            estimated_cost_cents=row.estimated_cost_cents,
            actual_cost_cents=row.actual_cost_cents,
            outcome=row.outcome,
            dispatched_by=row.dispatched_by,
        )


class DispatchUpdateRequest(BaseModel):
    outcome: str | None = None
    completed_at: datetime | None = None
    actual_cost_cents: int | None = None
    pr_number: int | None = None
    pr_url: str | None = None


class CostSummaryBySizeBucket(BaseModel):
    t_shirt_size: str
    count: int
    estimated_total_cents: int
    actual_total_cents: int | None


class CostSummaryByWorkstreamRow(BaseModel):
    workstream_id: str | None
    count: int
    estimated_total_cents: int
    t_shirt_size_breakdown: dict[str, int]


class DailySpend(BaseModel):
    date: str
    estimated_cents: int
    actual_cents: int | None


class CalibrationDelta(BaseModel):
    t_shirt_size: str
    estimated_total_cents: int
    actual_total_cents: int | None
    ratio: float | None


class CostSummaryResponse(BaseModel):
    by_size: list[CostSummaryBySizeBucket]
    by_workstream: list[CostSummaryByWorkstreamRow]
    by_day: list[DailySpend]
    calibration_delta: list[CalibrationDelta]


# ---------------------------------------------------------------------------
# Route: create dispatch (POST)
# ---------------------------------------------------------------------------


@router.post("/dispatches", response_model=DispatchResponse, status_code=201)
async def create_dispatch(
    body: DispatchCreateRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> DispatchResponse:
    """Record a new agent dispatch. Derives t_shirt_size from model_used."""
    size = body.t_shirt_size or MODEL_TO_SIZE.get(body.model_used, "M")
    estimated = SIZE_COST_CENTS.get(size, 100)

    row = AgentDispatch(
        organization_id="paperwork-labs",
        workstream_id=body.workstream_id,
        t_shirt_size=size,
        model_used=body.model_used,
        subagent_type=body.subagent_type,
        task_summary=body.task_summary,
        branch=body.branch,
        pr_number=body.pr_number,
        pr_url=body.pr_url,
        dispatched_at=datetime.now(UTC),
        estimated_cost_cents=estimated,
        outcome=body.outcome,
        dispatched_by=body.dispatched_by,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return DispatchResponse.from_orm_row(row)


# ---------------------------------------------------------------------------
# Route: list dispatches (GET)
# ---------------------------------------------------------------------------


@router.get("/dispatches", response_model=list[DispatchResponse])
async def list_dispatches(
    workstream_id: str | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    t_shirt_size: str | None = Query(None),
    outcome: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> list[DispatchResponse]:
    """List agent dispatches with optional filters. Default: 50 most recent."""
    stmt = select(AgentDispatch).order_by(AgentDispatch.dispatched_at.desc()).limit(limit)

    if workstream_id is not None:
        stmt = stmt.where(AgentDispatch.workstream_id == workstream_id)
    if since is not None:
        stmt = stmt.where(AgentDispatch.dispatched_at >= since)
    if until is not None:
        stmt = stmt.where(AgentDispatch.dispatched_at <= until)
    if t_shirt_size is not None:
        stmt = stmt.where(AgentDispatch.t_shirt_size == t_shirt_size)
    if outcome is not None:
        stmt = stmt.where(AgentDispatch.outcome == outcome)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [DispatchResponse.from_orm_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Route: update dispatch by id (PATCH)
# ---------------------------------------------------------------------------


@router.patch("/dispatches/{dispatch_id}", response_model=DispatchResponse)
async def update_dispatch(
    dispatch_id: str,
    body: DispatchUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> DispatchResponse:
    """Update outcome, completed_at, actual_cost_cents, pr_number, or pr_url."""
    try:
        uid = uuid.UUID(dispatch_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid dispatch ID format") from None

    result = await db.execute(select(AgentDispatch).where(AgentDispatch.id == uid))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Dispatch not found")

    if body.outcome is not None:
        _valid_outcomes = {"pending", "success", "failed", "blocked", "cancelled"}
        if body.outcome not in _valid_outcomes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid outcome. Must be one of: {sorted(_valid_outcomes)}",
            )
        row.outcome = body.outcome
    if body.completed_at is not None:
        row.completed_at = body.completed_at
    if body.actual_cost_cents is not None:
        row.actual_cost_cents = body.actual_cost_cents
    if body.pr_number is not None:
        row.pr_number = body.pr_number
    if body.pr_url is not None:
        row.pr_url = body.pr_url

    await db.flush()
    await db.refresh(row)
    return DispatchResponse.from_orm_row(row)


# ---------------------------------------------------------------------------
# Route: cost summary (GET)
# ---------------------------------------------------------------------------


@router.get("/dispatches/cost-summary", response_model=CostSummaryResponse)
async def cost_summary(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> CostSummaryResponse:
    """Cost rollups by size, workstream, day. Suitable for direct chart rendering."""
    # --- by size ---
    size_stmt = select(
        AgentDispatch.t_shirt_size,
        func.count().label("count"),
        func.coalesce(func.sum(AgentDispatch.estimated_cost_cents), 0).label("estimated_total"),
        func.sum(AgentDispatch.actual_cost_cents).label("actual_total"),
    ).group_by(AgentDispatch.t_shirt_size)

    size_result = await db.execute(size_stmt)
    by_size = [
        CostSummaryBySizeBucket(
            t_shirt_size=size_row.t_shirt_size,
            count=size_row.count,
            estimated_total_cents=size_row.estimated_total or 0,
            actual_total_cents=size_row.actual_total,
        )
        for size_row in size_result
    ]

    # --- by workstream (top 20) ---
    ws_stmt = (
        select(
            AgentDispatch.workstream_id,
            func.count().label("count"),
            func.coalesce(func.sum(AgentDispatch.estimated_cost_cents), 0).label("estimated_total"),
            AgentDispatch.t_shirt_size,
        )
        .group_by(AgentDispatch.workstream_id, AgentDispatch.t_shirt_size)
        .order_by(func.sum(AgentDispatch.estimated_cost_cents).desc())
        .limit(100)
    )
    ws_result = await db.execute(ws_stmt)

    ws_map: dict[str | None, dict[str, Any]] = {}
    for ws_row in ws_result:
        key = ws_row.workstream_id
        if key not in ws_map:
            ws_map[key] = {"count": 0, "estimated_total": 0, "breakdown": {}}
        ws_map[key]["count"] += ws_row.count
        ws_map[key]["estimated_total"] += ws_row.estimated_total or 0
        ws_map[key]["breakdown"][ws_row.t_shirt_size] = (
            ws_map[key]["breakdown"].get(ws_row.t_shirt_size, 0) + ws_row.count
        )

    by_workstream = [
        CostSummaryByWorkstreamRow(
            workstream_id=ws_id,
            count=data["count"],
            estimated_total_cents=data["estimated_total"],
            t_shirt_size_breakdown=data["breakdown"],
        )
        for ws_id, data in sorted(
            ws_map.items(),
            key=lambda x: x[1]["estimated_total"],
            reverse=True,
        )
    ][:20]

    # --- by day (last 30 days) ---
    day_stmt = select(
        func.date_trunc("day", AgentDispatch.dispatched_at).label("day"),
        func.coalesce(func.sum(AgentDispatch.estimated_cost_cents), 0).label("estimated"),
        func.sum(AgentDispatch.actual_cost_cents).label("actual"),
    ).where(
        AgentDispatch.dispatched_at >= text("NOW() - INTERVAL '30 days'")
    ).group_by(
        func.date_trunc("day", AgentDispatch.dispatched_at)
    ).order_by(
        func.date_trunc("day", AgentDispatch.dispatched_at)
    )

    day_result = await db.execute(day_stmt)
    by_day = [
        DailySpend(
            date=(
                day_row.day.strftime("%Y-%m-%d")
                if hasattr(day_row.day, "strftime")
                else str(day_row.day)[:10]
            ),
            estimated_cents=day_row.estimated or 0,
            actual_cents=day_row.actual,
        )
        for day_row in day_result
    ]

    # --- calibration delta ---
    cal_stmt = select(
        AgentDispatch.t_shirt_size,
        func.coalesce(func.sum(AgentDispatch.estimated_cost_cents), 0).label("estimated_total"),
        func.sum(AgentDispatch.actual_cost_cents).label("actual_total"),
    ).group_by(AgentDispatch.t_shirt_size)

    cal_result = await db.execute(cal_stmt)
    calibration_delta = []
    for cal_row in cal_result:
        ratio: float | None = None
        if cal_row.actual_total and cal_row.actual_total > 0 and cal_row.estimated_total > 0:
            ratio = round(cal_row.estimated_total / cal_row.actual_total, 3)
        calibration_delta.append(
            CalibrationDelta(
                t_shirt_size=cal_row.t_shirt_size,
                estimated_total_cents=cal_row.estimated_total or 0,
                actual_total_cents=cal_row.actual_total,
                ratio=ratio,
            )
        )

    return CostSummaryResponse(
        by_size=by_size,
        by_workstream=by_workstream,
        by_day=by_day,
        calibration_delta=calibration_delta,
    )
