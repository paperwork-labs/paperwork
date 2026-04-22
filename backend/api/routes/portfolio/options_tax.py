"""Open option positions for Tax Center (unrealized, holding class)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.api.routes.portfolio.stocks import _user_account_ids
from backend.database import get_db
from backend.models.options import Option
from backend.models.user import User

router = APIRouter(tags=["portfolio"])

_ZERO = Decimal("0")


class OptionsTaxItem(BaseModel):
    id: int
    symbol: str
    option_type: str
    open_quantity: int
    multiplier: Decimal
    cost_basis: Optional[Decimal] = Field(
        default=None,
        description="Total cost basis in account currency when known (from Option.total_cost).",
    )
    mark: Optional[Decimal] = Field(default=None, description="Current option mark per contract unit.")
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_pct: Optional[Decimal] = None
    days_to_expiry: Optional[int] = None
    tax_holding_class: Optional[Literal["short_term", "long_term"]] = None
    opened_at: Optional[datetime] = Field(
        default=None,
        description="Position first seen timestamp (Option.created_at); used for holding class.",
    )


class OptionsTaxCounts(BaseModel):
    longs: int
    shorts: int


class OptionsTaxSummaryResponse(BaseModel):
    items: List[OptionsTaxItem]
    total_unrealized_pnl: Optional[Decimal] = None
    counts: OptionsTaxCounts


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _cost_basis_per_unit(total_cost: Optional[Decimal], qty: int, mult: Decimal) -> Optional[Decimal]:
    if total_cost is None:
        return None
    denom = Decimal(qty) * mult
    if denom == _ZERO:
        return None
    return total_cost / denom


def _holding_class(opened_at: Optional[datetime], as_of: date) -> Optional[Literal["short_term", "long_term"]]:
    if opened_at is None:
        return None
    acq = opened_at.date()
    days_held = (as_of - acq).days
    return "long_term" if days_held >= 365 else "short_term"


def _build_item(row: Option, as_of: date) -> OptionsTaxItem:
    mult = _to_decimal(row.multiplier) or Decimal("100")
    qty = int(row.open_quantity)
    total_cost = _to_decimal(row.total_cost)
    mark = _to_decimal(row.current_price)

    cb_unit = _cost_basis_per_unit(total_cost, qty, mult)
    unrealized: Optional[Decimal] = None
    if mark is not None and cb_unit is not None:
        unrealized = (mark - cb_unit) * Decimal(qty) * mult

    unrealized_pct: Optional[Decimal] = None
    if unrealized is not None and total_cost is not None and total_cost != _ZERO:
        unrealized_pct = (unrealized / total_cost) * Decimal("100")

    days_te: Optional[int] = None
    if row.expiry_date is not None:
        days_te = (row.expiry_date - as_of).days

    opened = row.created_at
    if opened is not None and opened.tzinfo is None:
        opened = opened.replace(tzinfo=timezone.utc)

    return OptionsTaxItem(
        id=row.id,
        symbol=row.symbol,
        option_type=str(row.option_type),
        open_quantity=qty,
        multiplier=mult,
        cost_basis=total_cost,
        mark=mark,
        unrealized_pnl=unrealized,
        unrealized_pnl_pct=unrealized_pct,
        days_to_expiry=days_te,
        tax_holding_class=_holding_class(opened, as_of),
        opened_at=opened,
    )


@router.get("/tax-summary", response_model=Dict[str, Any])
def get_open_options_tax_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List open option positions with unrealized PnL and holding-term class."""
    as_of = date.today()
    acct_ids = _user_account_ids(db, current_user.id)
    if not acct_ids:
        rows = []
    else:
        rows = (
            db.query(Option)
            .filter(
                Option.user_id == current_user.id,
                Option.open_quantity != 0,
                Option.account_id.in_(acct_ids),
            )
            .order_by(Option.symbol.asc(), Option.id.asc())
            .all()
        )

    items = [_build_item(r, as_of) for r in rows]

    longs = sum(1 for i in items if i.open_quantity > 0)
    shorts = sum(1 for i in items if i.open_quantity < 0)

    total_unrealized: Optional[Decimal] = None
    if items:
        if all(i.unrealized_pnl is not None for i in items):
            total_unrealized = sum((i.unrealized_pnl or _ZERO) for i in items)
        else:
            total_unrealized = None
    else:
        total_unrealized = Decimal("0")

    payload = OptionsTaxSummaryResponse(
        items=items,
        total_unrealized_pnl=total_unrealized,
        counts=OptionsTaxCounts(longs=longs, shorts=shorts),
    )
    # Decimal -> string for JSON (avoid float drift)
    return {
        "status": "success",
        "data": payload.model_dump(mode="json"),
    }
