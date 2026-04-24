"""Unit tests for runner state (>=1R) detection."""

from __future__ import annotations

import pytest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from app.models.position import PositionType
from app.services.execution.runner_state_service import compute_runner_state

pytestmark = pytest.mark.no_db


@dataclass
class _LongPos:
    """Minimal stand-in for :class:`Position` with only runner-related fields."""

    position_type: Any = PositionType.LONG
    quantity: Decimal = Decimal("10")
    total_cost_basis: Decimal = Decimal("1000")
    runner_since: Optional[datetime] = None
    initial_risk_pct: Optional[Decimal] = field(default=Decimal("2"))

    @property
    def is_long(self) -> bool:
        return self.position_type in (
            PositionType.LONG,
            PositionType.OPTION_LONG,
            PositionType.FUTURE_LONG,
        )


def test_05r_no_runner() -> None:
    p = _LongPos()  # 10 sh @ 100 = 1000; +1% = 0.5R if initial=2% (1R = 2% of cost)
    price = Decimal("101")
    assert compute_runner_state(p, price) is None


def test_12r_becomes_runner() -> None:
    p = _LongPos()
    # +2.4% = 1.2R vs 2% initial; price (1000+24)/10 = 102.4
    price = Decimal("102.4")
    out = compute_runner_state(p, price)
    assert out is not None
    assert out.tzinfo == timezone.utc


def test_missing_initial_risk_returns_none() -> None:
    p = _LongPos(initial_risk_pct=None)
    price = Decimal("200")
    assert compute_runner_state(p, price) is None


def test_subsequent_does_not_reset_timestamp() -> None:
    t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    p = _LongPos(
        initial_risk_pct=Decimal("2"),
        runner_since=t0,
    )
    price = Decimal("50")
    assert compute_runner_state(p, price) == t0
