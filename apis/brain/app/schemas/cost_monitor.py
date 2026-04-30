"""API schemas for cost ledger summary, burn rate, and budget alerts.

medallion: ops
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AlertStatus = Literal["approaching", "exceeded"]


class CostLedgerEntry(BaseModel):
    date: str
    vendor: str
    category: str
    amount_usd: float = Field(ge=0)
    details: str = ""


class CostLedgerFile(BaseModel):
    entries: list[CostLedgerEntry] = Field(default_factory=list)
    monthly_budgets: dict[str, int | None] = Field(default_factory=dict)


class VendorMonthRow(BaseModel):
    vendor: str
    amount_usd: float
    categories: dict[str, float] = Field(default_factory=dict)
    budget_cap_usd: int | None = None
    budget_utilization: float | None = None


class MonthlyCostSummaryResponse(BaseModel):
    month: str
    vendors: list[VendorMonthRow]
    total_usd: float
    monthly_budgets: dict[str, int | None]


class DailyBurnRateResponse(BaseModel):
    window_days: int
    total_usd: float
    daily_average_usd: float
    as_of: str


class BudgetAlertItem(BaseModel):
    vendor: str
    budget_key: str
    spent_usd: float
    budget_usd: float
    utilization: float
    status: AlertStatus


class BudgetAlertsResponse(BaseModel):
    month: str
    alerts: list[BudgetAlertItem]
