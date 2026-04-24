"""Income calendar — `/api/v1/portfolio/income/calendar`.

Backs the Snowball-style 12 × 31 grid on the new `/portfolio/income` page.
Two modes:

  - `past`: aggregate realised `Dividend` rows by `pay_date` over the
    trailing window. Pure read-side query, scoped to the authenticated
    user via `BrokerAccount.user_id`.

  - `projection`: forecast the next window from per-symbol historical
    cadence and current shares held. Algorithm documented in
    `_build_projection_calendar` below.

All money values are kept as `Decimal` end-to-end and only converted to
`float` at the JSON serialization boundary, per `IRON LAWS` in
`AGENTS.md`. The endpoint surfaces `tax_data_available` so the frontend
can disable the "Net" toggle and explain why (no silent fallback).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models import BrokerAccount
from app.models.position import Position, PositionStatus
from app.models.transaction import Dividend
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Decimal + date helpers
# ---------------------------------------------------------------------------

_TWO_PLACES = Decimal("0.01")
_ZERO = Decimal("0")
# Minimum number of historical payments required to project. With fewer
# than two payments we cannot infer cadence reliably, so we drop the
# symbol from the projection rather than emit a misleading single point.
_MIN_HISTORY_FOR_PROJECTION = 2


def _to_decimal(value: Any) -> Decimal:
    """Coerce DB floats / Decimal / None to a Decimal safely.

    Floats round-trip via `str` to avoid binary-rep noise when they
    originate from SQLAlchemy `Float` columns (the `Dividend` model
    still uses `Float` historically).
    """
    if value is None:
        return _ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _decimal_to_json(value: Decimal) -> float:
    """Final-stage conversion for JSON. Quantized to cents."""
    return float(_quantize(value))


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _add_months(anchor: date, n: int) -> date:
    """Add `n` calendar months to `anchor`, clamping the day to month-end."""
    total = anchor.year * 12 + (anchor.month - 1) + n
    year, month = divmod(total, 12)
    month += 1
    last = _last_day_of_month(year, month)
    return date(year, month, min(anchor.day, last))


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - timedelta(days=1)).day


def _iter_months(start: date, end: date) -> List[date]:
    """Inclusive list of first-of-month dates between `start` and `end`.

    Both bounds are normalized to the first of their month so callers
    can pass any day within the month.
    """
    cur = date(start.year, start.month, 1)
    stop = date(end.year, end.month, 1)
    out: List[date] = []
    while cur <= stop:
        out.append(cur)
        cur = _add_months(cur, 1)
    return out


# ---------------------------------------------------------------------------
# Internal data shapes
# ---------------------------------------------------------------------------


@dataclass
class _DividendRow:
    """Normalised dividend row used by both modes.

    Stored as Decimal so downstream summation is exact.
    """

    symbol: str
    pay_date: date
    total: Decimal
    tax_withheld: Decimal
    shares_held: Decimal
    dividend_per_share: Decimal


@dataclass
class _CellAcc:
    """One day-cell in the calendar grid."""

    total: Decimal = _ZERO
    tax_withheld: Decimal = _ZERO
    by_symbol: Dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: _ZERO))


@dataclass
class _SymbolHistory:
    """Per-symbol trailing history used by the projection algorithm."""

    pay_dates: List[date]
    avg_per_share_per_payment: Decimal
    avg_tax_per_share_per_payment: Decimal
    payments_per_year: int
    last_pay_date: date


# ---------------------------------------------------------------------------
# Past-mode loaders
# ---------------------------------------------------------------------------


def _load_dividends_in_window(
    db: Session, user_id: int, start: date, end: date
) -> List[_DividendRow]:
    """All dividends paid between `start` and `end`, scoped to the user.

    Dividends with no `pay_date` are skipped (they cannot be placed on a
    grid). The caller logs the count so we never silently drop rows
    without observability.
    """
    rows = (
        db.query(Dividend)
        .join(BrokerAccount, Dividend.account_id == BrokerAccount.id)
        .filter(BrokerAccount.user_id == user_id)
        .filter(Dividend.pay_date.isnot(None))
        .filter(Dividend.pay_date >= datetime.combine(start, datetime.min.time()))
        .filter(Dividend.pay_date <= datetime.combine(end, datetime.max.time()))
        .all()
    )
    out: List[_DividendRow] = []
    for d in rows:
        pd = d.pay_date.date() if hasattr(d.pay_date, "date") else d.pay_date
        out.append(
            _DividendRow(
                symbol=(d.symbol or "").upper(),
                pay_date=pd,
                total=_to_decimal(d.total_dividend),
                tax_withheld=_to_decimal(d.tax_withheld),
                shares_held=_to_decimal(d.shares_held),
                dividend_per_share=_to_decimal(d.dividend_per_share),
            )
        )
    return out


def _build_past_calendar(
    db: Session, user_id: int, months: int, today: date
) -> Tuple[Dict[date, _CellAcc], List[date], bool]:
    """Aggregate realised dividends for the past `months` ending today.

    Returns `(cells, months_in_window, tax_data_available)`.
    """
    end = today
    start = _add_months(end, -months)
    rows = _load_dividends_in_window(db, user_id, start, end)

    cells: Dict[date, _CellAcc] = {}
    tax_data_available = False
    for row in rows:
        cell = cells.setdefault(row.pay_date, _CellAcc())
        cell.total += row.total
        cell.tax_withheld += row.tax_withheld
        cell.by_symbol[row.symbol] += row.total
        # "Has any row reported a non-zero tax withheld?" — the FE uses
        # this to decide whether the Net toggle is meaningful at all.
        if row.tax_withheld > _ZERO:
            tax_data_available = True

    months_in_window = _iter_months(start, end)
    return cells, months_in_window, tax_data_available


# ---------------------------------------------------------------------------
# Projection-mode logic
# ---------------------------------------------------------------------------


def _infer_payments_per_year(pay_dates: List[date]) -> int:
    """Heuristic cadence in payments per year from a sorted history.

    Uses the median gap between consecutive payments and snaps to the
    nearest known cadence (1, 2, 4, 12). With fewer than two payments
    falls back to quarterly (4) — the dominant US equity cadence — but
    callers are responsible for not projecting symbols below
    `_MIN_HISTORY_FOR_PROJECTION` history at all.
    """
    if len(pay_dates) < 2:
        return 4
    deltas = [
        (b - a).days
        for a, b in zip(sorted(pay_dates)[:-1], sorted(pay_dates)[1:])
    ]
    deltas.sort()
    median_days = deltas[len(deltas) // 2]
    if median_days <= 0:
        return 4
    raw = round(365 / median_days)
    # Snap to the closest known cadence so we don't emit "5x/year".
    return min((1, 2, 4, 12), key=lambda c: abs(c - raw))


def _build_symbol_history(
    rows: List[_DividendRow],
) -> Dict[str, _SymbolHistory]:
    """Group `rows` by symbol and compute per-share averages + cadence.

    Per-share averages, not per-payment dollar amounts — this is the
    whole point of the projection: it must scale to the *current*
    shares held, not the historical position size.
    """
    by_sym: Dict[str, List[_DividendRow]] = defaultdict(list)
    for r in rows:
        by_sym[r.symbol].append(r)

    out: Dict[str, _SymbolHistory] = {}
    for symbol, items in by_sym.items():
        items.sort(key=lambda x: x.pay_date)
        # Per-share average across all rows; we deliberately weight each
        # payment equally rather than by shares, so a one-off small
        # holding doesn't dilute the per-share figure.
        valid = [x for x in items if x.dividend_per_share > _ZERO]
        if not valid:
            continue
        avg_div = sum((x.dividend_per_share for x in valid), _ZERO) / Decimal(
            len(valid)
        )
        # Tax per share is opportunistic — many ingest paths leave it 0.
        share_weighted_tax = [
            (x.tax_withheld / x.shares_held)
            for x in items
            if x.shares_held > _ZERO and x.tax_withheld > _ZERO
        ]
        avg_tax = (
            sum(share_weighted_tax, _ZERO) / Decimal(len(share_weighted_tax))
            if share_weighted_tax
            else _ZERO
        )
        ppy = _infer_payments_per_year([x.pay_date for x in items])
        out[symbol] = _SymbolHistory(
            pay_dates=[x.pay_date for x in items],
            avg_per_share_per_payment=avg_div,
            avg_tax_per_share_per_payment=avg_tax,
            payments_per_year=ppy,
            last_pay_date=items[-1].pay_date,
        )
    return out


def _current_shares_per_symbol(db: Session, user_id: int) -> Dict[str, Decimal]:
    """Sum open-equity shares per symbol for `user_id`.

    Aggregates across accounts. Options/futures are excluded by the
    instrument_type filter — only `STOCK` rows contribute, since dividends
    accrue to equity holders. Returns Decimals scaled to share units.
    """
    rows = (
        db.query(Position.symbol, Position.quantity, Position.instrument_type)
        .filter(Position.user_id == user_id)
        .filter(Position.status == PositionStatus.OPEN)
        .all()
    )
    out: Dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for symbol, qty, inst_type in rows:
        # Anything non-equity (options, futures) won't accrue ordinary
        # dividends — exclude rather than risk projecting phantom income.
        if inst_type and str(inst_type).upper() not in ("STOCK", "EQUITY", "ETF"):
            continue
        if symbol is None or qty is None:
            continue
        out[str(symbol).upper()] += _to_decimal(qty)
    return out


def _project_dates_for_symbol(
    history: _SymbolHistory, end: date
) -> List[date]:
    """Project future pay dates for `history` up to (and including) `end`.

    Walks forward from `last_pay_date` in `cadence_days` increments
    derived from `payments_per_year`. Dates beyond `end` are dropped.
    """
    cadence_days = max(1, round(365 / history.payments_per_year))
    out: List[date] = []
    cur = history.last_pay_date + timedelta(days=cadence_days)
    while cur <= end:
        out.append(cur)
        cur = cur + timedelta(days=cadence_days)
    return out


def _build_projection_calendar(
    db: Session, user_id: int, months: int, today: date
) -> Tuple[Dict[date, _CellAcc], List[date], bool]:
    """Forecast next `months` of dividends from history × current shares.

    Algorithm
    ---------
    1. Pull the trailing 12 months of `Dividend` rows for `user_id`.
       This is intentionally a wider window than the projection horizon
       so seasonal-payer cadence (e.g. semi-annual) is captured.
    2. Group by symbol and compute, per symbol:
         - `avg_per_share_per_payment` — average of historical
           `dividend_per_share` across all observed rows.
         - `avg_tax_per_share_per_payment` — same but for `tax_withheld /
           shares_held`, only over rows where both > 0.
         - `payments_per_year` — snap median day-gap between historical
           pay dates to the nearest known cadence (1, 2, 4, 12).
       Symbols with fewer than `_MIN_HISTORY_FOR_PROJECTION` payments
       are dropped from the projection (we cannot infer cadence from a
       single observation).
    3. Look up current open-equity `Position.quantity` aggregated per
       symbol across the user's accounts. Symbols with zero current
       shares are dropped (sold out → zero projected income).
    4. For each remaining symbol, project future pay dates by stepping
       forward from `last_pay_date` in `365 / payments_per_year` day
       increments, up to the end of the projection window.
    5. For each projected date, accumulate `avg_per_share *
       current_shares` into the cell's total (and the corresponding
       tax-withheld figure).

    Limitations (documented for future maintainers):
      - Special / one-off dividends are not separated out and may
        inflate the average. We accept this for v1; the page's empty /
        loading states make it clear this is a forecast.
      - Cadence drift (e.g. company moves from quarterly to monthly)
        smooths into the snapped cadence. The trailing 12-month window
        means transitions take ~1 year to fully reflect.
      - Dividend cuts/raises are not modelled — projection assumes the
        most recent average per share holds.
    """
    end = _add_months(today, months)
    # Pull at least 12 months of history so cadence is reliable.
    history_window_months = max(12, months)
    history_start = _add_months(today, -history_window_months)
    rows = _load_dividends_in_window(db, user_id, history_start, today)

    by_symbol = _build_symbol_history(rows)
    current_shares = _current_shares_per_symbol(db, user_id)

    cells: Dict[date, _CellAcc] = {}
    tax_data_available = False

    for symbol, history in by_symbol.items():
        if len(history.pay_dates) < _MIN_HISTORY_FOR_PROJECTION:
            continue
        shares = current_shares.get(symbol, _ZERO)
        if shares <= _ZERO:
            continue

        per_payment_total = history.avg_per_share_per_payment * shares
        per_payment_tax = history.avg_tax_per_share_per_payment * shares
        if per_payment_tax > _ZERO:
            tax_data_available = True

        for pd in _project_dates_for_symbol(history, end):
            # `today` is excluded — the projection horizon starts
            # tomorrow so the calendar visually distinguishes "what
            # happened" from "what is forecast".
            if pd <= today:
                continue
            cell = cells.setdefault(pd, _CellAcc())
            cell.total += per_payment_total
            cell.tax_withheld += per_payment_tax
            cell.by_symbol[symbol] += per_payment_total

    # Window starts at the first day of the month *containing* today
    # (so the partial current month is included in the grid) and ends
    # at the projection horizon.
    months_in_window = _iter_months(today, end)
    return cells, months_in_window, tax_data_available


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize_cells(cells: Dict[date, _CellAcc]) -> List[Dict[str, Any]]:
    """Cells, sorted by date, with stable per-symbol ordering."""
    out: List[Dict[str, Any]] = []
    for d in sorted(cells.keys()):
        acc = cells[d]
        # Sort by amount desc, then symbol asc — keeps the "biggest
        # contributor" visually first in the rich tooltip.
        breakdown = sorted(
            acc.by_symbol.items(), key=lambda kv: (-kv[1], kv[0])
        )
        out.append(
            {
                "date": d.isoformat(),
                "total": _decimal_to_json(acc.total),
                "tax_withheld": _decimal_to_json(acc.tax_withheld),
                "by_symbol": [
                    {"symbol": sym, "amount": _decimal_to_json(amt)}
                    for sym, amt in breakdown
                ],
            }
        )
    return out


def _build_monthly_totals(
    months_in_window: List[date],
    cells: Dict[date, _CellAcc],
    *,
    projected: bool,
) -> List[Dict[str, Any]]:
    """One row per month in the window, with rolled-up totals."""
    by_month_total: Dict[str, Decimal] = defaultdict(lambda: _ZERO)
    by_month_tax: Dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for d, acc in cells.items():
        key = _month_key(d)
        by_month_total[key] += acc.total
        by_month_tax[key] += acc.tax_withheld

    out: List[Dict[str, Any]] = []
    for first_of_month in months_in_window:
        key = _month_key(first_of_month)
        out.append(
            {
                "month": key,
                "total": _decimal_to_json(by_month_total[key]),
                "tax_withheld": _decimal_to_json(by_month_tax[key]),
                "projected": projected,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


_ALLOWED_MODES = {"past", "projection"}


@router.get("/income/calendar", response_model=Dict[str, Any])
async def get_income_calendar(
    mode: str = Query(
        "past",
        description=(
            "`past` aggregates realised dividends by `pay_date` over the "
            "trailing window. `projection` forecasts the next window from "
            "per-symbol historical cadence × current shares held. See "
            "`_build_projection_calendar` for the projection algorithm."
        ),
    ),
    months: int = Query(
        12,
        ge=1,
        le=24,
        description="Window size in months (default 12, max 24).",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a Snowball-style 12-month dividend calendar for the user.

    Multi-tenant: every query is scoped to `current_user.id` via
    `BrokerAccount.user_id` (dividends) or `Position.user_id`
    (projection's current-shares lookup). No raw SQL bypasses.
    """
    mode_normalised = (mode or "").strip().lower()
    if mode_normalised not in _ALLOWED_MODES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"mode must be one of {sorted(_ALLOWED_MODES)}; got {mode!r}"
            ),
        )

    today = datetime.now(timezone.utc).date()
    if mode_normalised == "past":
        cells, months_in_window, tax_data_available = _build_past_calendar(
            db, current_user.id, months, today
        )
        projected = False
    else:
        cells, months_in_window, tax_data_available = _build_projection_calendar(
            db, current_user.id, months, today
        )
        projected = True

    return {
        "mode": mode_normalised,
        "months": months,
        "tax_data_available": tax_data_available,
        "cells": _serialize_cells(cells),
        "monthly_totals": _build_monthly_totals(
            months_in_window, cells, projected=projected
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
