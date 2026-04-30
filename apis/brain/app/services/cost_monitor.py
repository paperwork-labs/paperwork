"""Cost ledger load, monthly aggregation, burn rate, and budget alerts.

Reads ``apis/brain/data/cost_ledger.json`` for manual / ETL-populated spend.
Vendor rows map to ``monthly_budgets`` keys (e.g. ``google`` for Gemini).

medallion: ops
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.schemas.cost_monitor import (
    AlertStatus,
    CostLedgerFile,
    VendorMonthRow,
)

logger = logging.getLogger(__name__)

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_VENDOR_TO_BUDGET_KEY: dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google": "google",
    "gemini": "google",
    "render": "render",
    "vercel": "vercel",
    "hetzner": "hetzner",
}


def _brain_data_dir() -> Path:
    services_dir = Path(__file__).resolve().parent
    brain_app = services_dir.parent
    brain_root = brain_app.parent
    return brain_root / "data"


def _ledger_path() -> Path:
    return _brain_data_dir() / "cost_ledger.json"


def budget_key_for_vendor(vendor: str) -> str | None:
    return _VENDOR_TO_BUDGET_KEY.get(vendor.strip().lower())


def load_cost_ledger() -> CostLedgerFile:
    """Load and validate ``cost_ledger.json``. Missing file ⇒ empty ledger."""
    path = _ledger_path()
    if not path.is_file():
        logger.warning("cost_monitor: %s missing — using empty ledger", path)
        return CostLedgerFile(entries=[], monthly_budgets={})
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("cost_monitor: failed to read %s", path)
        return CostLedgerFile(entries=[], monthly_budgets={})
    try:
        return CostLedgerFile.model_validate(raw)
    except Exception:
        logger.exception("cost_monitor: invalid ledger schema in %s", path)
        return CostLedgerFile(entries=[], monthly_budgets={})


def _parse_month(month: str) -> tuple[int, int]:
    if not _MONTH_RE.match(month):
        msg = f"month must be YYYY-MM, got {month!r}"
        raise ValueError(msg)
    y, m = month.split("-", 1)
    return int(y), int(m)


def _entry_in_month(entry_date: str, month: str) -> bool:
    if not _DATE_RE.match(entry_date):
        return False
    return entry_date[:7] == month


@dataclass(frozen=True)
class MonthlySummaryResult:
    month: str
    vendors: list[VendorMonthRow]
    total_usd: float
    monthly_budgets: dict[str, int | None]


def get_monthly_summary(month: str) -> MonthlySummaryResult:
    """Aggregate ledger amounts by vendor for ``month`` (``YYYY-MM``)."""
    _parse_month(month)
    ledger = load_cost_ledger()
    budgets = ledger.monthly_budgets
    by_vendor: dict[str, dict[str, float]] = {}
    for e in ledger.entries:
        if not _entry_in_month(e.date, month):
            continue
        v = e.vendor.strip().lower()
        if v not in by_vendor:
            by_vendor[v] = {"_total": 0.0}
        by_vendor[v]["_total"] += float(e.amount_usd)
        cat = e.category.strip().lower() or "uncategorized"
        by_vendor[v][cat] = by_vendor[v].get(cat, 0.0) + float(e.amount_usd)

    vendors: list[VendorMonthRow] = []
    total = 0.0
    for vendor, buckets in sorted(by_vendor.items()):
        amt = buckets.pop("_total", 0.0)
        total += amt
        bk = budget_key_for_vendor(vendor)
        cap = budgets.get(bk) if bk else None
        util = (amt / float(cap)) if (cap is not None and cap > 0) else None
        if util is not None:
            util = round(float(util), 6)
        vendors.append(
            VendorMonthRow(
                vendor=vendor,
                amount_usd=round(amt, 6),
                categories=dict(buckets),
                budget_cap_usd=cap,
                budget_utilization=util,
            )
        )
    return MonthlySummaryResult(
        month=month,
        vendors=vendors,
        total_usd=round(total, 6),
        monthly_budgets=dict(budgets),
    )


@dataclass(frozen=True)
class BurnRateResult:
    window_days: int
    total_usd: float
    daily_average_usd: float
    as_of: str


def get_daily_burn_rate(*, window_days: int = 30) -> BurnRateResult:
    """Trailing ``window_days`` average daily spend (UTC calendar windows)."""
    if window_days < 1:
        msg = "window_days must be >= 1"
        raise ValueError(msg)
    ledger = load_cost_ledger()
    end = datetime.now(tz=UTC).date()
    start = end - timedelta(days=window_days - 1)
    total = 0.0
    for e in ledger.entries:
        if not _DATE_RE.match(e.date):
            continue
        y, m, d = (int(x) for x in e.date.split("-"))
        ed = datetime(y, m, d, tzinfo=UTC).date()
        if start <= ed <= end:
            total += float(e.amount_usd)
    daily = total / float(window_days) if window_days else 0.0
    return BurnRateResult(
        window_days=window_days,
        total_usd=round(total, 6),
        daily_average_usd=round(daily, 6),
        as_of=datetime.now(tz=UTC).date().isoformat(),
    )


@dataclass(frozen=True)
class BudgetAlert:
    vendor: str
    budget_key: str
    spent_usd: float
    budget_usd: float
    utilization: float
    status: AlertStatus


def current_utc_month() -> str:
    """Current calendar month in UTC as ``YYYY-MM``."""
    return datetime.now(tz=UTC).strftime("%Y-%m")


def normalized_month(month: str | None) -> str:
    """Return ``month`` or current UTC month; validate ``YYYY-MM``."""
    key = month or current_utc_month()
    _parse_month(key)
    return key


def check_budget_alerts(
    *,
    month: str | None = None,
    approaching_threshold: float = 0.8,
) -> list[BudgetAlert]:
    """Vendors at or above ``approaching_threshold`` of monthly budget, or over 100%."""
    month_key = normalized_month(month)
    summary = get_monthly_summary(month_key)
    budgets = summary.monthly_budgets
    alerts: list[BudgetAlert] = []

    spend_by_budget_key: dict[str, float] = {}
    representative_vendor: dict[str, str] = {}
    for row in summary.vendors:
        bk = budget_key_for_vendor(row.vendor)
        if bk is None:
            continue
        spend_by_budget_key[bk] = spend_by_budget_key.get(bk, 0.0) + row.amount_usd
        representative_vendor.setdefault(bk, row.vendor)

    for budget_key, cap in budgets.items():
        if cap is None or cap <= 0:
            continue
        spent = spend_by_budget_key.get(budget_key, 0.0)
        util = spent / float(cap) if cap else 0.0
        if util >= 1.0:
            status: AlertStatus = "exceeded"
        elif util >= approaching_threshold:
            status = "approaching"
        else:
            continue
        vend = representative_vendor.get(budget_key, budget_key)
        alerts.append(
            BudgetAlert(
                vendor=vend,
                budget_key=budget_key,
                spent_usd=round(spent, 6),
                budget_usd=float(cap),
                utilization=round(util, 6),
                status=status,
            )
        )
    alerts.sort(key=lambda a: (-a.utilization, a.budget_key))
    return alerts
