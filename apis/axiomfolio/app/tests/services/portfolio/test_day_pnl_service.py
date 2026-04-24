"""Unit + integration tests for :mod:`app.services.silver.portfolio.day_pnl_service`.

Pins the architectural contract introduced in D141:

* Day P&L is ALWAYS server-recomputed from ``(current_price, prior_close, qty)``.
* Broker ``currentDayProfitLoss`` / ``daysGain`` fields are advisory only.
* On missing prior_close or split-drift window, both fields NULL — never 0.

The RIVN regression fixture at the bottom encodes the founder's exact
prod scenario (3,500 sh, current $17.15, simulated broker day_pnl
-$55,691, prior_close $17.26 → correct day_pnl ≈ -$385).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerAccount,
    BrokerType,
)
from app.models.corporate_action import (
    CorporateAction,
    CorporateActionSource,
    CorporateActionStatus,
    CorporateActionType,
)
from app.models.market_data import PriceData
from app.models.position import Position, PositionStatus, PositionType
from app.models.user import User
from app.services.silver.portfolio.day_pnl_service import (
    compute_day_pnl,
    has_ambiguous_corporate_action,
    recompute_day_pnl_for_rows,
    recompute_position_day_pnl,
    resolve_prior_close,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def _make_account(session, user: User, *, broker: BrokerType = BrokerType.IBKR) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user.id,
        broker=broker,
        account_number=f"ACCT_{user.id}",
        account_name=f"{broker.value} {user.username}",
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        currency="USD",
    )
    session.add(acct)
    session.flush()
    return acct


def _insert_daily_bar(
    session, symbol: str, bar_date: date, close: float
) -> PriceData:
    row = PriceData(
        symbol=symbol,
        date=datetime.combine(bar_date, datetime.min.time()),
        close_price=close,
        interval="1d",
        data_source="test",
    )
    session.add(row)
    session.flush()
    return row


def _make_position(
    session,
    account: BrokerAccount,
    *,
    symbol: str,
    quantity: Decimal,
    current_price: Decimal,
    avg_cost: Decimal,
    day_pnl: Decimal | None = None,
    day_pnl_pct: Decimal | None = None,
    position_type: PositionType = PositionType.LONG,
) -> Position:
    total_cost = avg_cost * abs(quantity)
    market_value = current_price * abs(quantity)
    pos = Position(
        user_id=account.user_id,
        account_id=account.id,
        symbol=symbol,
        instrument_type="STOCK",
        position_type=position_type,
        quantity=quantity,
        status=PositionStatus.OPEN,
        average_cost=avg_cost,
        total_cost_basis=total_cost,
        current_price=current_price,
        market_value=market_value,
        unrealized_pnl=market_value - total_cost,
        unrealized_pnl_pct=((market_value - total_cost) / total_cost * 100)
        if total_cost > 0
        else Decimal("0"),
        day_pnl=day_pnl,
        day_pnl_pct=day_pnl_pct,
    )
    session.add(pos)
    session.flush()
    return pos


# ---------------------------------------------------------------------------
# Pure-math tests (no DB)
# ---------------------------------------------------------------------------


@pytest.mark.no_db
def test_compute_day_pnl_stage2_uptrend_case() -> None:
    """Positive day on a Stage 2 uptrend — sane ratio, exact Decimal."""
    day_pnl, day_pnl_pct = compute_day_pnl(
        quantity=Decimal("100"),
        current_price=Decimal("50.00"),
        prior_close=Decimal("49.00"),
        market_value=Decimal("5000.00"),
    )
    assert day_pnl == Decimal("100.00")
    # pct = 100 / (5000 - 100) = 100 / 4900 = 2.0408163...
    assert day_pnl_pct is not None
    assert abs(day_pnl_pct - Decimal("2.040816326530612244897959184")) < Decimal("0.0001")


@pytest.mark.no_db
def test_compute_day_pnl_near_stop_case() -> None:
    """Negative day with normal magnitude (stop watch)."""
    day_pnl, day_pnl_pct = compute_day_pnl(
        quantity=Decimal("200"),
        current_price=Decimal("24.50"),
        prior_close=Decimal("25.00"),
        market_value=Decimal("4900.00"),
    )
    assert day_pnl == Decimal("-100.00")
    # pct = -100 / (4900 - (-100)) = -100 / 5000 = -2
    assert day_pnl_pct == Decimal("-2")


@pytest.mark.no_db
def test_compute_day_pnl_returns_none_on_nonpositive_inputs() -> None:
    assert compute_day_pnl(
        quantity=Decimal("0"),
        current_price=Decimal("50"),
        prior_close=Decimal("49"),
        market_value=Decimal("0"),
    ) == (None, None)
    assert compute_day_pnl(
        quantity=Decimal("10"),
        current_price=Decimal("0"),
        prior_close=Decimal("49"),
        market_value=Decimal("100"),
    ) == (None, None)
    assert compute_day_pnl(
        quantity=Decimal("10"),
        current_price=Decimal("50"),
        prior_close=Decimal("-1"),
        market_value=Decimal("500"),
    ) == (None, None)


@pytest.mark.no_db
def test_compute_day_pnl_returns_none_on_none_inputs() -> None:
    assert compute_day_pnl(None, None, None, None) == (None, None)  # type: ignore[arg-type]


@pytest.mark.no_db
def test_compute_day_pnl_never_returns_zero_as_error_fallback() -> None:
    """Regression: when inputs are unknown we MUST return (None, None);
    (Decimal('0'), Decimal('0')) would hide the bug (D141 iron rule)."""
    result = compute_day_pnl(None, Decimal("1"), Decimal("1"), Decimal("1"))  # type: ignore[arg-type]
    assert result == (None, None)
    assert result != (Decimal("0"), Decimal("0"))


# ---------------------------------------------------------------------------
# DB integration tests
# ---------------------------------------------------------------------------


def test_resolve_prior_close_uses_latest_daily_bar_before_as_of(db_session) -> None:
    today = date(2026, 4, 22)
    # Two prior days + today (today must NOT be selected).
    _insert_daily_bar(db_session, "AAPL", today - timedelta(days=2), 100.0)
    _insert_daily_bar(db_session, "AAPL", today - timedelta(days=1), 101.0)
    _insert_daily_bar(db_session, "AAPL", today, 102.0)

    result = resolve_prior_close(db_session, "AAPL", as_of=today)
    assert result is not None
    close, close_date = result
    assert close == Decimal("101.0")
    assert close_date == today - timedelta(days=1)


def test_resolve_prior_close_returns_none_when_no_bars(db_session) -> None:
    assert resolve_prior_close(db_session, "NOSUCH", as_of=date(2026, 4, 22)) is None


def test_has_ambiguous_corporate_action_detects_split_in_window(db_session) -> None:
    today = date(2026, 4, 22)
    prior = today - timedelta(days=1)
    # 3-for-1 forward split with ex_date strictly between prior_close_date
    # and today.
    ca = CorporateAction(
        symbol="TSLA",
        action_type=CorporateActionType.SPLIT.value,
        ex_date=today,
        ratio_numerator=Decimal("3"),
        ratio_denominator=Decimal("1"),
        source=CorporateActionSource.MANUAL.value,
        status=CorporateActionStatus.PENDING.value,
    )
    db_session.add(ca)
    db_session.flush()

    assert (
        has_ambiguous_corporate_action(db_session, "TSLA", prior, as_of=today) is True
    )


def test_has_ambiguous_corporate_action_ignores_cash_dividends(db_session) -> None:
    today = date(2026, 4, 22)
    prior = today - timedelta(days=1)
    ca = CorporateAction(
        symbol="MSFT",
        action_type=CorporateActionType.CASH_DIVIDEND.value,
        ex_date=today,
        cash_amount=Decimal("0.75"),
        source=CorporateActionSource.FMP.value,
        status=CorporateActionStatus.PENDING.value,
    )
    db_session.add(ca)
    db_session.flush()

    # Cash dividends do NOT change price scale — not ambiguous.
    assert (
        has_ambiguous_corporate_action(db_session, "MSFT", prior, as_of=today) is False
    )


def test_recompute_position_day_pnl_happy_path(db_session) -> None:
    today = date(2026, 4, 22)
    user = _make_user(db_session, "dp_happy")
    account = _make_account(db_session, user)

    _insert_daily_bar(db_session, "NVDA", today - timedelta(days=1), 100.0)

    pos = _make_position(
        db_session,
        account,
        symbol="NVDA",
        quantity=Decimal("50"),
        current_price=Decimal("102"),
        avg_cost=Decimal("90"),
        # Broker-provided day_pnl is wrong on purpose — this is the exact
        # shape of the bug we're fixing.
        day_pnl=Decimal("-9999"),
        day_pnl_pct=Decimal("-99.9"),
    )

    recompute_position_day_pnl(db_session, pos, as_of=today)

    # 50 × (102 - 100) = 100
    assert pos.day_pnl == Decimal("100")
    # 100 / (5100 - 100) = 100 / 5000 = 2.0
    assert pos.day_pnl_pct == Decimal("2")


def test_recompute_position_day_pnl_overwrites_broker_value(db_session) -> None:
    """Broker-reported day_pnl MUST be overwritten, not respected."""
    today = date(2026, 4, 22)
    user = _make_user(db_session, "dp_broker")
    account = _make_account(db_session, user, broker=BrokerType.SCHWAB)
    _insert_daily_bar(db_session, "AMZN", today - timedelta(days=1), 150.0)

    pos = _make_position(
        db_session,
        account,
        symbol="AMZN",
        quantity=Decimal("10"),
        current_price=Decimal("155"),
        avg_cost=Decimal("140"),
        day_pnl=Decimal("88888"),
        day_pnl_pct=Decimal("77.77"),
    )
    recompute_position_day_pnl(db_session, pos, as_of=today)

    # 10 × (155 - 150) = 50; 50 / (1550 - 50) = 50 / 1500 = 3.333...
    assert pos.day_pnl == Decimal("50")
    assert pos.day_pnl_pct is not None
    assert abs(pos.day_pnl_pct - Decimal("3.33333333333333333333333333")) < Decimal(
        "0.0001"
    )


def test_recompute_split_window_nulls_day_pnl(db_session) -> None:
    """RIVN-like split-drift guard: SPLIT between prior_close and today
    forces day_pnl to NULL, not a made-up number."""
    today = date(2026, 4, 22)
    user = _make_user(db_session, "dp_split")
    account = _make_account(db_session, user)
    _insert_daily_bar(db_session, "SPLT", today - timedelta(days=2), 30.0)

    db_session.add(
        CorporateAction(
            symbol="SPLT",
            action_type=CorporateActionType.SPLIT.value,
            ex_date=today - timedelta(days=1),
            ratio_numerator=Decimal("2"),
            ratio_denominator=Decimal("1"),
            source=CorporateActionSource.FMP.value,
            status=CorporateActionStatus.PENDING.value,
        )
    )
    db_session.flush()

    pos = _make_position(
        db_session,
        account,
        symbol="SPLT",
        quantity=Decimal("100"),
        current_price=Decimal("16"),
        avg_cost=Decimal("20"),
        day_pnl=Decimal("-1400"),
        day_pnl_pct=Decimal("-46"),
    )
    recompute_position_day_pnl(db_session, pos, as_of=today)

    assert pos.day_pnl is None
    assert pos.day_pnl_pct is None


def test_recompute_missing_prior_close_nulls_day_pnl(db_session) -> None:
    """No daily bar + no snapshot → NULL, never 0."""
    today = date(2026, 4, 22)
    user = _make_user(db_session, "dp_missing")
    account = _make_account(db_session, user)

    pos = _make_position(
        db_session,
        account,
        symbol="NODATA",
        quantity=Decimal("10"),
        current_price=Decimal("5"),
        avg_cost=Decimal("5"),
        day_pnl=Decimal("-99"),
        day_pnl_pct=Decimal("-1"),
    )
    recompute_position_day_pnl(db_session, pos, as_of=today)
    assert pos.day_pnl is None
    assert pos.day_pnl_pct is None


def test_recompute_short_position_flips_sign(db_session) -> None:
    today = date(2026, 4, 22)
    user = _make_user(db_session, "dp_short")
    account = _make_account(db_session, user)
    _insert_daily_bar(db_session, "SHRT", today - timedelta(days=1), 50.0)

    # Short: qty negative. Price went UP (50 → 52) — short is losing.
    pos = _make_position(
        db_session,
        account,
        symbol="SHRT",
        quantity=Decimal("-20"),
        current_price=Decimal("52"),
        avg_cost=Decimal("55"),
        position_type=PositionType.SHORT,
    )
    recompute_position_day_pnl(db_session, pos, as_of=today)

    # Long math would be +20 × 2 = +40. Short inverts: -40.
    assert pos.day_pnl == Decimal("-40")


def test_recompute_counter_sums_to_total(db_session) -> None:
    """Per-position loop must emit counters that sum exactly to len(rows)."""
    today = date(2026, 4, 22)
    user = _make_user(db_session, "dp_counters")
    account = _make_account(db_session, user)

    _insert_daily_bar(db_session, "OK1", today - timedelta(days=1), 100.0)
    _insert_daily_bar(db_session, "OK2", today - timedelta(days=1), 50.0)
    _insert_daily_bar(db_session, "SPL", today - timedelta(days=2), 30.0)

    db_session.add(
        CorporateAction(
            symbol="SPL",
            action_type=CorporateActionType.REVERSE_SPLIT.value,
            ex_date=today - timedelta(days=1),
            ratio_numerator=Decimal("1"),
            ratio_denominator=Decimal("10"),
            source=CorporateActionSource.FMP.value,
            status=CorporateActionStatus.PENDING.value,
        )
    )
    db_session.flush()

    rows = [
        _make_position(db_session, account, symbol="OK1", quantity=Decimal("10"),
                       current_price=Decimal("101"), avg_cost=Decimal("95")),
        _make_position(db_session, account, symbol="OK2", quantity=Decimal("20"),
                       current_price=Decimal("51"), avg_cost=Decimal("48")),
        _make_position(db_session, account, symbol="SPL", quantity=Decimal("30"),
                       current_price=Decimal("16"), avg_cost=Decimal("20")),
        _make_position(db_session, account, symbol="NOBARS", quantity=Decimal("40"),
                       current_price=Decimal("9"), avg_cost=Decimal("10")),
    ]

    stats = recompute_day_pnl_for_rows(db_session, rows, "unit_test", as_of=today)
    total = (
        stats["day_pnl_recomputed"]
        + stats["day_pnl_nulled_due_to_split"]
        + stats["day_pnl_nulled_due_to_missing_prior_close"]
        + stats["day_pnl_errors"]
    )
    assert total == 4
    assert stats["day_pnl_recomputed"] == 2
    assert stats["day_pnl_nulled_due_to_split"] == 1
    assert stats["day_pnl_nulled_due_to_missing_prior_close"] == 1
    assert stats["day_pnl_errors"] == 0


# ---------------------------------------------------------------------------
# RIVN regression fixture — founder's exact scenario
# ---------------------------------------------------------------------------


def test_rivn_regression_fixture_day_pnl_is_small_not_minus_55k(db_session) -> None:
    """Founder screenshot: RIVN showed Day P&L of -$55,691 (-47.82%) on a
    3,500-share position. ``-55,691 / 3,500 ≈ -$15.91/sh`` implied a stale
    pre-split reference near $32.9 vs current $17.15. After server-side
    recompute with prior_close $17.26, day_pnl must be ≈ -$385, NOT
    -$55,691.
    """
    today = date(2026, 4, 22)
    user = _make_user(db_session, "rivn_regression")
    account = _make_account(db_session, user, broker=BrokerType.SCHWAB)

    # Prior session close — reality, not broker's stale pre-split baseline.
    _insert_daily_bar(db_session, "RIVN", today - timedelta(days=1), 17.26)

    pos = _make_position(
        db_session,
        account,
        symbol="RIVN",
        quantity=Decimal("3500"),
        current_price=Decimal("17.15"),
        avg_cost=Decimal("16.21"),
        # The bug: broker-advertised day_pnl is catastrophically wrong.
        day_pnl=Decimal("-55691"),
        day_pnl_pct=Decimal("-47.82"),
    )

    recompute_position_day_pnl(db_session, pos, as_of=today)

    # 3500 × (17.15 - 17.26) = 3500 × -0.11 = -385.00
    assert pos.day_pnl == Decimal("-385.00")
    # pct = -385 / (market_value - day_pnl)
    #     = -385 / (3500*17.15 - (-385))
    #     = -385 / (60025 + 385) = -385 / 60410
    #     ≈ -0.637%
    assert pos.day_pnl_pct is not None
    assert abs(pos.day_pnl_pct - Decimal("-0.637312")) < Decimal("0.01")
    # And the prod-screenshot lie is gone.
    assert pos.day_pnl != Decimal("-55691")
