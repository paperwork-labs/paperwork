"""Tests for the broker-agnostic FIFO closing-lot matcher.

These tests use the shared ``db_session`` fixture from ``backend/tests/conftest.py``
so they run against the real SQLAlchemy schema (nothing is mocked out from
the ORM layer).

The matcher is the fix for the Tax Center being empty on Schwab accounts —
see ``docs/plans/broker_parity_medallion_v1_*.plan.md`` Phase 2 / PR E.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import pytest

from backend.models.broker_account import (
    AccountType,
    BrokerAccount,
    BrokerType,
)
from backend.models.trade import Trade
from backend.models.user import User
from backend.services.portfolio.closing_lot_matcher import (
    MatchResult,
    reconcile_closing_lots,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(session, *, username: str) -> User:
    user = session.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        email=f"{username}@example.test",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_account(
    session,
    *,
    user: User,
    account_number: str,
    broker: BrokerType = BrokerType.SCHWAB,
) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user.id,
        broker=broker,
        account_number=account_number,
        account_name=f"{broker.value} {account_number}",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(acct)
    session.commit()
    session.refresh(acct)
    return acct


def _add_trade(
    session,
    *,
    account: BrokerAccount,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    execution_id: str,
    execution_time: datetime,
    commission: Decimal = Decimal("0"),
    is_opening: Optional[bool] = None,
    status: str = "FILLED",
    trade_metadata: Optional[dict] = None,
) -> Trade:
    if is_opening is None:
        is_opening = side.upper() == "BUY"
    trade = Trade(
        account_id=account.id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        total_value=quantity * price,
        commission=commission,
        execution_id=execution_id,
        execution_time=execution_time,
        status=status,
        is_opening=is_opening,
        is_paper_trade=False,
        trade_metadata=trade_metadata or {},
    )
    session.add(trade)
    session.flush()
    return trade


def _closed_lots(session, account: BrokerAccount):
    return (
        session.query(Trade)
        .filter(
            Trade.account_id == account.id,
            Trade.status == "CLOSED_LOT",
        )
        .order_by(Trade.execution_time.asc(), Trade.id.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fifo_single_buy_single_sell_same_qty(db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")
    user = _make_user(db_session, username="lotmatch_user_1")
    acct = _make_account(db_session, user=user, account_number="LM001")

    t0 = datetime(2024, 1, 10, 14, 30, tzinfo=timezone.utc)
    t1 = datetime(2024, 6, 10, 14, 30, tzinfo=timezone.utc)
    _add_trade(
        db_session,
        account=acct,
        symbol="AAPL",
        side="BUY",
        quantity=Decimal("10"),
        price=Decimal("150"),
        execution_id="BUY-1",
        execution_time=t0,
        commission=Decimal("1"),
    )
    _add_trade(
        db_session,
        account=acct,
        symbol="AAPL",
        side="SELL",
        quantity=Decimal("10"),
        price=Decimal("200"),
        execution_id="SELL-1",
        execution_time=t1,
        commission=Decimal("1"),
    )

    result = reconcile_closing_lots(db_session, acct)
    assert isinstance(result, MatchResult)
    assert result.created == 1
    assert result.updated == 0
    assert result.unmatched_quantity == Decimal("0")

    lots = _closed_lots(db_session, acct)
    assert len(lots) == 1
    lot = lots[0]
    assert lot.symbol == "AAPL"
    assert Decimal(str(lot.quantity)) == Decimal("10")
    # realized = (200*10 - 1) - (150*10 + 1) = 1999 - 1501 = 498
    assert Decimal(str(lot.realized_pnl)) == Decimal("498")
    meta = lot.trade_metadata or {}
    assert meta["method"] == "FIFO"
    assert meta["is_long_term"] is False  # ~5 months
    assert pytest.approx(meta["cost_basis"], rel=1e-6) == 1501.0


def test_fifo_partial_sell_splits_lot(db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")
    user = _make_user(db_session, username="lotmatch_user_2")
    acct = _make_account(db_session, user=user, account_number="LM002")

    t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2024, 2, 1, tzinfo=timezone.utc)
    _add_trade(
        db_session, account=acct, symbol="MSFT", side="BUY",
        quantity=Decimal("100"), price=Decimal("300"),
        execution_id="BUY-100", execution_time=t0,
    )
    _add_trade(
        db_session, account=acct, symbol="MSFT", side="SELL",
        quantity=Decimal("40"), price=Decimal("400"),
        execution_id="SELL-40", execution_time=t1,
    )

    result = reconcile_closing_lots(db_session, acct)
    assert result.created == 1
    lots = _closed_lots(db_session, acct)
    assert len(lots) == 1
    lot = lots[0]
    assert Decimal(str(lot.quantity)) == Decimal("40")
    # realized = 40*400 - 40*300 = 4000
    assert Decimal(str(lot.realized_pnl)) == Decimal("4000")
    meta = lot.trade_metadata or {}
    # >365 days held
    assert meta["is_long_term"] is True


def test_fifo_sell_spans_multiple_lots(db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")
    user = _make_user(db_session, username="lotmatch_user_3")
    acct = _make_account(db_session, user=user, account_number="LM003")

    _add_trade(
        db_session, account=acct, symbol="NVDA", side="BUY",
        quantity=Decimal("10"), price=Decimal("100"),
        execution_id="B1", execution_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    _add_trade(
        db_session, account=acct, symbol="NVDA", side="BUY",
        quantity=Decimal("10"), price=Decimal("120"),
        execution_id="B2", execution_time=datetime(2024, 2, 1, tzinfo=timezone.utc),
    )
    _add_trade(
        db_session, account=acct, symbol="NVDA", side="SELL",
        quantity=Decimal("15"), price=Decimal("200"),
        execution_id="S1", execution_time=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )

    result = reconcile_closing_lots(db_session, acct)
    assert result.created == 2  # one slice per source lot
    lots = _closed_lots(db_session, acct)
    assert len(lots) == 2
    # First slice consumes the full 10@100 (FIFO), second takes 5@120
    q_total = sum(Decimal(str(l.quantity)) for l in lots)
    assert q_total == Decimal("15")
    pnl_total = sum(Decimal(str(l.realized_pnl)) for l in lots)
    # (10*(200-100)) + (5*(200-120)) = 1000 + 400 = 1400
    assert pnl_total == Decimal("1400")


def test_matcher_is_idempotent_across_runs(db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")
    user = _make_user(db_session, username="lotmatch_user_4")
    acct = _make_account(db_session, user=user, account_number="LM004")

    _add_trade(
        db_session, account=acct, symbol="TSLA", side="BUY",
        quantity=Decimal("5"), price=Decimal("200"),
        execution_id="B", execution_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    _add_trade(
        db_session, account=acct, symbol="TSLA", side="SELL",
        quantity=Decimal("5"), price=Decimal("250"),
        execution_id="S", execution_time=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )

    r1 = reconcile_closing_lots(db_session, acct)
    assert r1.created == 1
    r2 = reconcile_closing_lots(db_session, acct)
    # Second run must upsert, not duplicate
    assert r2.created == 0
    assert r2.updated == 1
    assert len(_closed_lots(db_session, acct)) == 1


def test_short_term_loss_flags_wash_sale_heuristic(db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")
    user = _make_user(db_session, username="lotmatch_user_5")
    acct = _make_account(db_session, user=user, account_number="LM005")

    t_buy_original = datetime(2024, 3, 1, tzinfo=timezone.utc)
    t_sell_loss = datetime(2024, 4, 15, tzinfo=timezone.utc)
    t_buy_replacement = t_sell_loss + timedelta(days=10)

    _add_trade(
        db_session, account=acct, symbol="META", side="BUY",
        quantity=Decimal("10"), price=Decimal("500"),
        execution_id="B-ORIG", execution_time=t_buy_original,
    )
    _add_trade(
        db_session, account=acct, symbol="META", side="SELL",
        quantity=Decimal("10"), price=Decimal("450"),
        execution_id="S-LOSS", execution_time=t_sell_loss,
    )
    _add_trade(
        db_session, account=acct, symbol="META", side="BUY",
        quantity=Decimal("10"), price=Decimal("460"),
        execution_id="B-REPLACE", execution_time=t_buy_replacement,
    )

    reconcile_closing_lots(db_session, acct)
    lots = _closed_lots(db_session, acct)
    assert len(lots) == 1
    meta = lots[0].trade_metadata or {}
    assert meta.get("wash_sale") is True
    assert float(meta.get("wash_sale_loss", 0)) == pytest.approx(500.0)


def test_unmatched_sell_emits_warning_and_counter(db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")
    user = _make_user(db_session, username="lotmatch_user_6")
    acct = _make_account(db_session, user=user, account_number="LM006")

    # SELL without any prior BUY (e.g., transferred-in position)
    _add_trade(
        db_session, account=acct, symbol="GOOG", side="SELL",
        quantity=Decimal("7"), price=Decimal("150"),
        execution_id="ORPHAN", execution_time=datetime(2024, 5, 1, tzinfo=timezone.utc),
    )

    result = reconcile_closing_lots(db_session, acct)
    assert result.created == 0
    assert result.unmatched_quantity == Decimal("7")
    assert len(result.warnings) == 1
    assert "GOOG" in result.warnings[0]


def test_options_are_skipped_not_misclassified(db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")
    user = _make_user(db_session, username="lotmatch_user_7")
    acct = _make_account(db_session, user=user, account_number="LM007")

    # Schwab-style OCC option symbol (>15 chars, contains spaces or digits+letters)
    opt_symbol = "AAPL  250117C00200000"
    _add_trade(
        db_session, account=acct, symbol=opt_symbol, side="BUY",
        quantity=Decimal("2"), price=Decimal("5"),
        execution_id="OPT-B", execution_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        trade_metadata={"asset_category": "OPT"},
    )
    _add_trade(
        db_session, account=acct, symbol=opt_symbol, side="SELL",
        quantity=Decimal("2"), price=Decimal("8"),
        execution_id="OPT-S", execution_time=datetime(2024, 2, 1, tzinfo=timezone.utc),
        trade_metadata={"asset_category": "OPT"},
    )

    result = reconcile_closing_lots(db_session, acct)
    assert result.created == 0
    assert result.skipped >= 2
    lots = _closed_lots(db_session, acct)
    assert len(lots) == 0


def test_cross_tenant_isolation(db_session):
    """Matcher for user A must NEVER touch user B's trades."""
    if db_session is None:
        pytest.skip("DB session unavailable")
    user_a = _make_user(db_session, username="lotmatch_tenant_a")
    user_b = _make_user(db_session, username="lotmatch_tenant_b")
    acct_a = _make_account(db_session, user=user_a, account_number="TENANT-A")
    acct_b = _make_account(db_session, user=user_b, account_number="TENANT-B")

    # Identical symbol + timing in both accounts to stress isolation
    for acct, suffix in ((acct_a, "A"), (acct_b, "B")):
        _add_trade(
            db_session, account=acct, symbol="SPY", side="BUY",
            quantity=Decimal("10"), price=Decimal("400"),
            execution_id=f"B-{suffix}",
            execution_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        _add_trade(
            db_session, account=acct, symbol="SPY", side="SELL",
            quantity=Decimal("10"), price=Decimal("450"),
            execution_id=f"S-{suffix}",
            execution_time=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )

    r_a = reconcile_closing_lots(db_session, acct_a)
    lots_a = _closed_lots(db_session, acct_a)
    lots_b = _closed_lots(db_session, acct_b)
    assert r_a.created == 1
    assert len(lots_a) == 1
    # User B's account must be completely untouched.
    assert len(lots_b) == 0

    # Now run for user B; must not re-process user A
    r_b = reconcile_closing_lots(db_session, acct_b)
    assert r_b.created == 1
    assert r_b.updated == 0
    # User A is still unchanged (still 1 closed lot, not 2)
    assert len(_closed_lots(db_session, acct_a)) == 1


def test_synth_execution_id_fits_column_limit_for_long_sell_keys(db_session):
    """Regression (PR 394 follow-up): ``Trade.execution_id`` is
    ``String(50)``. A prior iteration emitted ``SYNTH:{full_sell_key}:{idx}``
    which could exceed 50 chars (IBKR/Schwab emit 30-40 char execution
    ids) and blow up with IntegrityError on flush. The current layout
    hashes the sell key to a short digest; pin the bound.
    """
    if db_session is None:
        pytest.skip("DB session unavailable")
    user = _make_user(db_session, username="lotmatch_synthlen")
    acct = _make_account(db_session, user=user, account_number="LM-SYNTH")

    long_sell_key = "SCHW-" + "X" * 44  # 49 chars — at the column limit
    _add_trade(
        db_session, account=acct, symbol="SPY", side="BUY",
        quantity=Decimal("10"), price=Decimal("400"),
        execution_id="B-LONG",
        execution_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    _add_trade(
        db_session, account=acct, symbol="SPY", side="SELL",
        quantity=Decimal("10"), price=Decimal("450"),
        execution_id=long_sell_key,
        execution_time=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    r = reconcile_closing_lots(db_session, acct)
    assert r.created == 1
    lots = _closed_lots(db_session, acct)
    assert len(lots) == 1
    assert lots[0].execution_id is not None
    assert len(lots[0].execution_id) <= 50
    # Original sell key is preserved in metadata for traceability.
    meta = lots[0].trade_metadata or {}
    assert meta.get("source_sell_execution_id") == long_sell_key


def test_matcher_ignores_trades_without_execution_time(db_session):
    """FIFO is undefined without a timestamp. Previously we loaded every
    FILLED trade (including rows missing ``execution_time``) and sorted
    on ``None``, producing unpredictable ordering. The matcher now filters
    those out and counts them as skipped rather than processing them.
    """
    if db_session is None:
        pytest.skip("DB session unavailable")
    user = _make_user(db_session, username="lotmatch_no_exec_time")
    acct = _make_account(db_session, user=user, account_number="LM-NOTIME")

    _add_trade(
        db_session, account=acct, symbol="AAPL", side="BUY",
        quantity=Decimal("10"), price=Decimal("100"),
        execution_id="B-OK",
        execution_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    # Orphan SELL with no execution_time — must be skipped entirely.
    orphan = Trade(
        account_id=acct.id,
        symbol="AAPL",
        side="SELL",
        quantity=Decimal("10"),
        price=Decimal("200"),
        execution_id="S-NOTS",
        execution_time=None,
        status="FILLED",
        is_opening=False,
        is_paper_trade=False,
    )
    db_session.add(orphan)
    db_session.flush()

    r = reconcile_closing_lots(db_session, acct)
    # The orphan SELL is ignored; the BUY alone produces no closed lots.
    assert r.created == 0
    assert r.unmatched_quantity == Decimal("0")


def test_unsupported_method_raises(db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")
    user = _make_user(db_session, username="lotmatch_user_8")
    acct = _make_account(db_session, user=user, account_number="LM008")
    with pytest.raises(NotImplementedError):
        reconcile_closing_lots(db_session, acct, method="LIFO")
