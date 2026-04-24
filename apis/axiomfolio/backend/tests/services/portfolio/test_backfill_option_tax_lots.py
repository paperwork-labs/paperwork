"""backfill_option_tax_lots: broker-agnostic, idempotent, per-account isolated.

The task lives in ``backend.tasks.portfolio.reconciliation`` but we invoke
it as a plain callable (``.run`` / ``.apply``) so pytest doesn't need a
live Celery broker. The behaviour under test is the backfill loop, not
Celery plumbing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from backend.models import BrokerAccount, Trade
from backend.models.broker_account import AccountType, BrokerType
from backend.models.option_tax_lot import OptionTaxLot
from backend.models.user import User

OPT_AAPL = "AAPL  250117C00200000"
OPT_TSLA = "TSLA  250321P00200000"


def _make_user(db_session, tag: str) -> User:
    u = User(
        username=f"backfill_{tag}_{uuid.uuid4().hex[:6]}",
        email=f"backfill_{tag}_{uuid.uuid4().hex[:6]}@example.test",
        password_hash="x",
        is_active=True,
    )
    db_session.add(u)
    db_session.flush()
    return u


def _make_account(db_session, user: User, broker: BrokerType, tag: str) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user.id,
        broker=broker,
        account_number=f"{broker.value}-{tag}-{uuid.uuid4().hex[:6]}",
        account_name=f"{broker.value} {tag}",
        account_type=AccountType.TAXABLE,
        currency="USD",
        is_enabled=True,
    )
    db_session.add(acct)
    db_session.flush()
    return acct


def _add_option_round_trip(
    db_session, account_id: int, symbol: str, *, open_exec: str, close_exec: str
) -> None:
    t_open = datetime(2025, 1, 10, 16, 0, 0, tzinfo=timezone.utc)
    t_close = datetime(2025, 3, 10, 16, 0, 0, tzinfo=timezone.utc)
    db_session.add_all([
        Trade(
            account_id=account_id,
            symbol=symbol,
            side="BUY",
            quantity=Decimal("2"),
            price=Decimal("5.00"),
            total_value=Decimal("10.00"),
            commission=Decimal("0.65"),
            execution_id=open_exec,
            execution_time=t_open,
            status="FILLED",
            is_opening=True,
            is_paper_trade=False,
            trade_metadata={"asset_category": "OPT", "multiplier": 100},
        ),
        Trade(
            account_id=account_id,
            symbol=symbol,
            side="SELL",
            quantity=Decimal("2"),
            price=Decimal("8.00"),
            total_value=Decimal("16.00"),
            commission=Decimal("0.65"),
            execution_id=close_exec,
            execution_time=t_close,
            status="FILLED",
            is_opening=False,
            is_paper_trade=False,
            realized_pnl=Decimal("600.00"),
            trade_metadata={"asset_category": "OPT", "multiplier": 100},
        ),
    ])


@pytest.fixture
def _patch_sessionlocal(db_session):
    """Force the task to reuse the pytest session so the transactional
    savepoint pattern keeps tests isolated.

    The task opens/closes sessions per account. We proxy the pytest session
    so ``.close()`` is a no-op (teardown is handled by the outer fixture)
    and ``.commit()`` flushes (commits inside the outer transaction are
    forbidden; pytest rolls back on teardown).
    """

    class _SessionProxy:
        def __getattr__(self, name):
            if name in ("close", "rollback"):
                # Close/rollback would kill the outer pytest transaction.
                # The bad-account branch in the task calls rollback(); we
                # treat it as a no-op because state hygiene between
                # accounts is the task's concern, not the test session's.
                return lambda: None
            if name == "commit":
                return db_session.flush
            return getattr(db_session, name)

    proxy = _SessionProxy()

    def _factory():
        return proxy

    with patch("backend.database.SessionLocal", new=_factory):
        yield


def test_backfill_runs_across_multi_broker_user(
    db_session, _patch_sessionlocal
) -> None:
    """One user with both IBKR + Schwab option histories gets lots from BOTH."""
    if db_session is None:
        pytest.skip("no db")
    from backend.tasks.portfolio.reconciliation import backfill_option_tax_lots

    user = _make_user(db_session, "multi")
    ibkr = _make_account(db_session, user, BrokerType.IBKR, "ibkr")
    schwab = _make_account(db_session, user, BrokerType.SCHWAB, "schwab")
    _add_option_round_trip(
        db_session, ibkr.id, OPT_AAPL,
        open_exec=f"ibkr-open-{uuid.uuid4().hex[:6]}",
        close_exec=f"ibkr-close-{uuid.uuid4().hex[:6]}",
    )
    _add_option_round_trip(
        db_session, schwab.id, OPT_TSLA,
        open_exec=f"schwab-open-{uuid.uuid4().hex[:6]}",
        close_exec=f"schwab-close-{uuid.uuid4().hex[:6]}",
    )
    db_session.commit()

    result = backfill_option_tax_lots.run(user_id=user.id)

    assert result["status"] == "ok"
    assert result["accounts_total"] == 2
    assert result["accounts_processed"] == 2
    assert result["accounts_failed"] == 0
    assert result["option_lots_created"] >= 2
    brokers_touched = {d["broker"] for d in result["details"]}
    assert brokers_touched == {"ibkr", "schwab"}

    rows = (
        db_session.query(OptionTaxLot)
        .filter(OptionTaxLot.user_id == user.id)
        .all()
    )
    underlyings = {r.underlying for r in rows}
    assert underlyings == {"AAPL", "TSLA"}


def test_backfill_all_users_when_user_id_none(
    db_session, _patch_sessionlocal
) -> None:
    if db_session is None:
        pytest.skip("no db")
    from backend.tasks.portfolio.reconciliation import backfill_option_tax_lots

    u1 = _make_user(db_session, "u1")
    u2 = _make_user(db_session, "u2")
    a1 = _make_account(db_session, u1, BrokerType.IBKR, "a")
    a2 = _make_account(db_session, u2, BrokerType.SCHWAB, "b")
    _add_option_round_trip(
        db_session, a1.id, OPT_AAPL,
        open_exec=f"ao-{uuid.uuid4().hex[:6]}",
        close_exec=f"ac-{uuid.uuid4().hex[:6]}",
    )
    _add_option_round_trip(
        db_session, a2.id, OPT_TSLA,
        open_exec=f"bo-{uuid.uuid4().hex[:6]}",
        close_exec=f"bc-{uuid.uuid4().hex[:6]}",
    )
    db_session.commit()

    result = backfill_option_tax_lots.run(user_id=None)

    assert result["status"] == "ok"
    assert result["accounts_total"] >= 2
    touched_users = {d["user_id"] for d in result["details"]}
    assert u1.id in touched_users and u2.id in touched_users


def test_backfill_idempotent_on_rerun(
    db_session, _patch_sessionlocal
) -> None:
    if db_session is None:
        pytest.skip("no db")
    from backend.tasks.portfolio.reconciliation import backfill_option_tax_lots

    user = _make_user(db_session, "idem")
    acct = _make_account(db_session, user, BrokerType.IBKR, "ibkr")
    _add_option_round_trip(
        db_session, acct.id, OPT_AAPL,
        open_exec=f"io-{uuid.uuid4().hex[:6]}",
        close_exec=f"ic-{uuid.uuid4().hex[:6]}",
    )
    db_session.commit()

    first = backfill_option_tax_lots.run(user_id=user.id)
    second = backfill_option_tax_lots.run(user_id=user.id)

    assert first["accounts_failed"] == 0
    assert second["accounts_failed"] == 0
    # First run created, second only touched idempotent updates
    assert first["option_lots_created"] == 1
    assert second["option_lots_created"] == 0
    assert second["option_lots_updated"] >= 1

    n = (
        db_session.query(OptionTaxLot)
        .filter(OptionTaxLot.user_id == user.id)
        .count()
    )
    assert n == 1


def test_backfill_account_failure_does_not_poison_batch(
    db_session, _patch_sessionlocal
) -> None:
    """When one account's reconcile raises, others still complete."""
    if db_session is None:
        pytest.skip("no db")
    from backend.tasks.portfolio.reconciliation import backfill_option_tax_lots
    from backend.services.portfolio import closing_lot_matcher as _matcher

    user = _make_user(db_session, "partial")
    good = _make_account(db_session, user, BrokerType.IBKR, "good")
    bad = _make_account(db_session, user, BrokerType.SCHWAB, "bad")
    _add_option_round_trip(
        db_session, good.id, OPT_AAPL,
        open_exec=f"go-{uuid.uuid4().hex[:6]}",
        close_exec=f"gc-{uuid.uuid4().hex[:6]}",
    )
    db_session.commit()

    real = _matcher.reconcile_closing_lots

    def _selective(session, account, **kw):
        if account.id == bad.id:
            raise RuntimeError("simulated matcher failure")
        return real(session, account, **kw)

    with patch(
        "backend.services.portfolio.closing_lot_matcher.reconcile_closing_lots",
        new=_selective,
    ):
        result = backfill_option_tax_lots.run(user_id=user.id)

    assert result["accounts_total"] == 2
    assert result["accounts_processed"] + result["accounts_failed"] == 2
    # The good account still produced a lot
    rows = (
        db_session.query(OptionTaxLot)
        .filter(OptionTaxLot.broker_account_id == good.id)
        .all()
    )
    assert len(rows) == 1
