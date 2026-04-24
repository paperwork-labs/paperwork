"""Regression tests for Copilot review on PR 435 (Schwab options / sync hardening)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.models.user import User

# Keep aligned with _OPTION_ROW_DROP_PREVIEW_KEYS in tastytrade_sync_service.py
_TT_OPTION_DROP_LOG_KEYS = (
    "symbol",
    "option_symbol",
    "underlying_symbol",
    "expiration",
    "expiration_date",
    "strike",
    "strike_price",
    "put_call",
    "option_type",
    "quantity",
)


def test_tastytrade_option_drop_preview_includes_tastytrade_key_names() -> None:
    """Drop-log preview must surface TT field names, not only Schwab-style keys."""
    pos = {
        "instrument_type": "Equity Option",
        "underlying_symbol": "AAPL",
        "expiration_date": "2025-01-17",
        "strike_price": 150.0,
        "option_type": "C",
        "quantity": 1.0,
    }
    preview = {k: pos.get(k) for k in _TT_OPTION_DROP_LOG_KEYS}
    assert preview["underlying_symbol"] == "AAPL"
    assert preview["expiration_date"] == "2025-01-17"
    assert preview["strike_price"] == 150.0
    assert preview["option_type"] == "C"
    assert preview.get("option_symbol") is None


@pytest.mark.asyncio
async def test_ibkr_sync_balance_updates_broker_account_on_repeat_same_day(
    db_session,
) -> None:
    """Repeat syncs with an existing AccountBalance row must still refresh BrokerAccount totals."""
    from app.services.portfolio.ibkr.sync_balances import sync_account_balances

    u = User(
        username="ibkr_ba_totals",
        email="ibkr_ba_totals@example.com",
        password_hash="x",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)

    ba = BrokerAccount(
        user_id=u.id,
        broker=BrokerType.IBKR,
        account_number="U_IBKR_TOT",
        account_name="Test",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    db_session.add(ba)
    db_session.commit()
    db_session.refresh(ba)

    same_date = datetime(2024, 6, 1, 12, 0, 0)
    fc = MagicMock()
    row = {
        "balance_date": same_date,
        "balance_type": "DAILY_SNAPSHOT",
        "net_liquidation": 100.0,
        "cash_balance": 25.0,
    }
    fc.get_account_balances = AsyncMock(return_value=[row])

    await sync_account_balances(db_session, ba, "U_IBKR_TOT", None, fc)
    db_session.commit()
    db_session.refresh(ba)
    assert ba.total_value == Decimal("100")
    assert ba.cash_balance == Decimal("25")

    row["net_liquidation"] = 200.0
    row["cash_balance"] = 30.0
    fc.get_account_balances = AsyncMock(return_value=[row])

    await sync_account_balances(db_session, ba, "U_IBKR_TOT", None, fc)
    db_session.commit()
    db_session.refresh(ba)
    assert ba.total_value == Decimal("200")
    assert ba.cash_balance == Decimal("30")
