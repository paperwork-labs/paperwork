from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.models.position import Position, PositionStatus, PositionType
from app.models.user import User
from app.services.portfolio.ibkr.historical_import import (
    HistoricalImportService,
    ParsedTradeRecord,
    build_year_chunks,
)

def _make_user(db_session) -> User:
    user = User(
        email="hist_import_service@example.com",
        username="hist_import_service",
        password_hash="x",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_account(db_session, user_id: int) -> BrokerAccount:
    account = BrokerAccount(
        user_id=user_id,
        broker=BrokerType.IBKR,
        account_number="U-HIST-SVC",
        account_type=AccountType.TAXABLE,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.mark.no_db
def test_build_year_chunks_splits_multi_year_range():
    chunks = build_year_chunks(date(2021, 1, 1), date(2023, 6, 1))
    assert len(chunks) == 3
    assert chunks[0] == (date(2021, 1, 1), date(2021, 12, 31))
    assert chunks[-1][0] == date(2023, 1, 1)
    assert chunks[-1][1] == date(2023, 6, 1)


@pytest.mark.no_db
def test_build_year_chunks_handles_leap_year_boundaries():
    chunks = build_year_chunks(date(2019, 7, 1), date(2020, 3, 1))
    assert chunks == [
        (date(2019, 7, 1), date(2019, 12, 31)),
        (date(2020, 1, 1), date(2020, 3, 1)),
    ]


def test_upsert_position_allows_short_after_oversell(db_session):
    user = _make_user(db_session)
    account = _make_account(db_session, user.id)
    service = HistoricalImportService(db_session)

    buy_record = ParsedTradeRecord(
        symbol="AAPL",
        side="BUY",
        quantity=Decimal("5"),
        price=Decimal("100"),
        executed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        execution_id="exec-buy",
    )
    sell_record = ParsedTradeRecord(
        symbol="AAPL",
        side="SELL",
        quantity=Decimal("8"),
        price=Decimal("110"),
        executed_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        execution_id="exec-sell",
    )

    # Use the internal position upsert directly to isolate short transition logic.
    service._upsert_position(account, buy_record)
    db_session.flush()
    service._upsert_position(account, sell_record)
    db_session.flush()

    position = (
        db_session.query(Position)
        .filter(Position.account_id == account.id, Position.symbol == "AAPL")
        .first()
    )
    assert position is not None
    assert Decimal(str(position.quantity)) == Decimal("-3")
    assert position.position_type == PositionType.SHORT
    assert position.status == PositionStatus.OPEN
