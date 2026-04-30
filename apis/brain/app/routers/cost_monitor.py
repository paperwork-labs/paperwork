"""Cost ledger HTTP API (monthly summary, burn rate, budget alerts).

medallion: ops
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.config import settings
from app.schemas.cost_monitor import (
    BudgetAlertItem,
    BudgetAlertsResponse,
    DailyBurnRateResponse,
    MonthlyCostSummaryResponse,
)
from app.services import cost_monitor as cost_monitor_svc

router = APIRouter(prefix="/costs", tags=["costs"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


@router.get("/summary", response_model=MonthlyCostSummaryResponse)
async def costs_summary(
    month: str = Query(..., description="Calendar month as YYYY-MM", pattern=r"^\d{4}-\d{2}$"),
    _auth: None = Depends(_require_admin),
) -> MonthlyCostSummaryResponse:
    try:
        r = cost_monitor_svc.get_monthly_summary(month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MonthlyCostSummaryResponse(
        month=r.month,
        vendors=list(r.vendors),
        total_usd=r.total_usd,
        monthly_budgets=r.monthly_budgets,
    )


@router.get("/burn-rate", response_model=DailyBurnRateResponse)
async def costs_burn_rate(
    _auth: None = Depends(_require_admin),
) -> DailyBurnRateResponse:
    r = cost_monitor_svc.get_daily_burn_rate()
    return DailyBurnRateResponse(
        window_days=r.window_days,
        total_usd=r.total_usd,
        daily_average_usd=r.daily_average_usd,
        as_of=r.as_of,
    )


@router.get("/alerts", response_model=BudgetAlertsResponse)
async def costs_alerts(
    month: str | None = Query(None, description="YYYY-MM (default: current UTC month)"),
    _auth: None = Depends(_require_admin),
) -> BudgetAlertsResponse:
    try:
        key = cost_monitor_svc.normalized_month(month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raw = cost_monitor_svc.check_budget_alerts(month=key)
    return BudgetAlertsResponse(
        month=key,
        alerts=[
            BudgetAlertItem(
                vendor=a.vendor,
                budget_key=a.budget_key,
                spent_usd=a.spent_usd,
                budget_usd=a.budget_usd,
                utilization=a.utilization,
                status=a.status,
            )
            for a in raw
        ],
    )
