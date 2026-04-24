"""Open option positions for Tax Center (unrealized, holding class)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.routes.portfolio.stocks import _user_account_ids
from app.database import get_db
from app.models.broker_account import BrokerAccount
from app.models.option_tax_lot import OptionTaxLot
from app.models.options import Option
from app.models.user import User

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


class RealizedOptionItem(BaseModel):
    id: int
    symbol: str
    underlying: str
    option_type: str
    strike: Decimal
    expiry: date
    multiplier: int
    quantity_opened: Decimal
    quantity_closed: Decimal
    cost_basis_per_contract: Optional[Decimal] = None
    proceeds_per_contract: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    holding_class: Optional[Literal["short_term", "long_term"]] = None
    closed_at: Optional[datetime] = None
    opening_trade_id: int
    closing_trade_id: Optional[int] = None


class RealizedOptionsCounts(BaseModel):
    short_term: int
    long_term: int
    total: int


class RealizedOptionsTaxResponse(BaseModel):
    items: List[RealizedOptionItem]
    total_realized_pnl_short: Optional[Decimal] = None
    total_realized_pnl_long: Optional[Decimal] = None
    counts: RealizedOptionsCounts


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


def _rollup_realized_pnls(values: List[Optional[Decimal]]) -> Optional[Decimal]:
    if not values:
        return Decimal("0")
    if any(v is None for v in values):
        return None
    return sum((v if v is not None else _ZERO) for v in values)


@router.get("/realized", response_model=Dict[str, Any])
def get_realized_options_tax(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    year: Optional[int] = Query(
        None,
        description="Tax year filter on closed_at (defaults to current calendar year).",
    ),
) -> Dict[str, Any]:
    """Closed option lots (realized PnL) for Tax Center, grouped by holding class."""
    tax_year = year if year is not None else date.today().year
    acct_ids = _user_account_ids(db, current_user.id)
    if not acct_ids:
        payload = RealizedOptionsTaxResponse(
            items=[],
            total_realized_pnl_short=Decimal("0"),
            total_realized_pnl_long=Decimal("0"),
            counts=RealizedOptionsCounts(short_term=0, long_term=0, total=0),
        )
        return {"status": "success", "data": payload.model_dump(mode="json")}

    rows = (
        db.query(OptionTaxLot)
        .join(BrokerAccount, OptionTaxLot.broker_account_id == BrokerAccount.id)
        .filter(
            OptionTaxLot.user_id == current_user.id,
            BrokerAccount.user_id == current_user.id,
            BrokerAccount.is_enabled == True,
            OptionTaxLot.broker_account_id.in_(acct_ids),
            OptionTaxLot.closed_at.isnot(None),
            extract("year", OptionTaxLot.closed_at) == tax_year,
        )
        .order_by(OptionTaxLot.closed_at.desc(), OptionTaxLot.id.desc())
        .all()
    )

    items: List[RealizedOptionItem] = []
    for r in rows:
        hc: Optional[Literal["short_term", "long_term"]] = None
        if r.holding_class in ("short_term", "long_term"):
            hc = r.holding_class  # type: ignore[assignment]
        closed = r.closed_at
        if closed is not None and closed.tzinfo is None:
            closed = closed.replace(tzinfo=timezone.utc)
        items.append(
            RealizedOptionItem(
                id=r.id,
                symbol=r.symbol,
                underlying=r.underlying,
                option_type=r.option_type,
                strike=_to_decimal(r.strike) or _ZERO,
                expiry=r.expiry,
                multiplier=int(r.multiplier),
                quantity_opened=_to_decimal(r.quantity_opened) or _ZERO,
                quantity_closed=_to_decimal(r.quantity_closed) or _ZERO,
                cost_basis_per_contract=_to_decimal(r.cost_basis_per_contract),
                proceeds_per_contract=_to_decimal(r.proceeds_per_contract),
                realized_pnl=_to_decimal(r.realized_pnl),
                holding_class=hc,
                closed_at=closed,
                opening_trade_id=r.opening_trade_id,
                closing_trade_id=r.closing_trade_id,
            )
        )

    st_pnls = [i.realized_pnl for i in items if i.holding_class == "short_term"]
    lt_pnls = [i.realized_pnl for i in items if i.holding_class == "long_term"]
    total_short = _rollup_realized_pnls(st_pnls)
    total_long = _rollup_realized_pnls(lt_pnls)

    counts = RealizedOptionsCounts(
        short_term=sum(1 for i in items if i.holding_class == "short_term"),
        long_term=sum(1 for i in items if i.holding_class == "long_term"),
        total=len(items),
    )

    payload = RealizedOptionsTaxResponse(
        items=items,
        total_realized_pnl_short=total_short,
        total_realized_pnl_long=total_long,
        counts=counts,
    )
    return {"status": "success", "data": payload.model_dump(mode="json")}
