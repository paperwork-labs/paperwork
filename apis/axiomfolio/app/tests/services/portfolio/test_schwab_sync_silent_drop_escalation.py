"""Schwab _sync_options escalates when API returns options but nothing is persisted."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.services.portfolio import schwab_sync_service
from app.services.portfolio.schwab_sync_service import SchwabSyncService
from app.models.user import User


class AllDroppedOptionsClient:
    """Two option rows, both missing underlying so sync drops all."""

    async def get_options_positions(self, account_number: str) -> list:
        return [
            {
                "symbol": "",
                "option_symbol": "X  260101C00001000",
                "quantity": 1,
                "strike": 1.0,
                "expiration": "2026-01-01",
                "put_call": "CALL",
            },
            {
                "symbol": "",
                "option_symbol": "Y  260102C00002000",
                "quantity": 1,
                "strike": 2.0,
                "expiration": "2026-01-02",
                "put_call": "CALL",
            },
        ]


def _account(session) -> BrokerAccount:
    u = (
        session.query(User)
        .filter(User.email == "silent_drop@example.com")
        .first()
    )
    if not u:
        u = User(
            username="silent_drop_t",
            email="silent_drop@example.com",
            password_hash="x",
            is_active=True,
        )
        session.add(u)
        session.commit()
        session.refresh(u)
    ba = (
        session.query(BrokerAccount)
        .filter(BrokerAccount.user_id == u.id, BrokerAccount.account_number == "SCHWAB_SD")
        .first()
    )
    if not ba:
        ba = BrokerAccount(
            user_id=u.id,
            broker=BrokerType.SCHWAB,
            account_number="SCHWAB_SD",
            account_name="Test",
            account_type=AccountType.TAXABLE,
            currency="USD",
        )
        session.add(ba)
        session.commit()
        session.refresh(ba)
    return ba


@pytest.mark.asyncio
async def test_sync_options_silent_drop_error_and_flag(db_session) -> None:
    acct = _account(db_session)
    svc = SchwabSyncService(client=AllDroppedOptionsClient())
    with patch.object(schwab_sync_service.logger, "error") as mock_err:
        result = await svc._sync_options(acct, db_session)
    assert result.get("options_silent_drop") is True
    assert result.get("options_created", 0) == 0
    assert result.get("options_updated", 0) == 0
    mock_err.assert_called_once()
    assert "silent-fallback" in str(mock_err.call_args)
