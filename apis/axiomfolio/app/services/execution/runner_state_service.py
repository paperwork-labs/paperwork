"""Runner state: long position that has covered at least its initial (1R) risk.

medallion: execution
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from app.models.position import Position


def _to_decimal(v: object) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    return cast(Decimal, Decimal(str(v)))


def _unrealized_pnl_pct_long(position: Position, current_price: Decimal) -> Decimal | None:
    if not position.is_long:
        return None
    qty = _to_decimal(getattr(position, "quantity", None))
    cost = _to_decimal(getattr(position, "total_cost_basis", None))
    if qty is None or cost is None or cost <= 0 or qty == 0:
        return None
    market_value = abs(qty) * current_price
    unrealized = market_value - cost
    return (unrealized / cost) * Decimal("100")


def compute_runner_state(position: Position, current_price: Decimal) -> datetime | None:
    """Returns the timestamp the position became a runner, or None if not yet."""
    existing = cast(datetime | None, getattr(position, "runner_since", None))
    if existing is not None:
        return existing
    if not position.is_long:
        return None
    initial_risk = _to_decimal(getattr(position, "initial_risk_pct", None))
    if initial_risk is None or initial_risk <= 0:
        return None
    u_pct = _unrealized_pnl_pct_long(position, current_price)
    if u_pct is None or u_pct < initial_risk:
        return None
    return datetime.now(UTC)
