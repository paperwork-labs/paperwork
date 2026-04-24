"""Schwab sync populates OptionTaxLot via closing-lot matcher (FIFO)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.models.option_tax_lot import OptionTaxLot
from app.models.user import User
from app.services.portfolio.schwab_sync_service import SchwabSyncService

OPT = "AAPL  250117C00200000"


def _credentials(_account_id, _session) -> dict[str, str]:
    return {"access_token": "fake_at", "refresh_token": "fake_rt"}


def _user_and_account(db_session) -> BrokerAccount:
    suffix = uuid.uuid4().hex[:8]
    u = User(
        username=f"schwab_opt_{suffix}",
        email=f"schwab_opt_{suffix}@example.test",
        password_hash="x",
        is_active=True,
    )
    db_session.add(u)
    db_session.flush()
    acct = BrokerAccount(
        user_id=u.id,
        broker=BrokerType.SCHWAB,
        account_number=f"SCH-OPT-{suffix}",
        account_name="Opt test",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    db_session.add(acct)
    db_session.commit()
    db_session.refresh(acct)
    return acct


class _ClientOptionRoundTrip:
    """Minimal Schwab client: no stock/options positions; two option TRADE rows."""

    def __init__(self) -> None:
        self.connected = True

    async def connect_with_credentials(
        self, access_token: str, refresh_token: str, **kwargs: Any
    ) -> bool:
        return True

    def set_token_refresh_callback(self, callback: Any) -> None:
        pass

    async def get_positions(self, account_number: str) -> list[dict[str, Any]]:
        return []

    async def get_options_positions(self, account_number: str) -> list[dict[str, Any]]:
        return []

    async def get_transactions(self, account_number: str) -> list[dict[str, Any]]:
        t_open = datetime(2025, 1, 10, 16, 0, 0, tzinfo=UTC)
        t_close = datetime(2025, 3, 10, 16, 0, 0, tzinfo=UTC)
        return [
            {
                "id": "schwab-exec-open-1",
                "symbol": OPT,
                "action": "TRADE",
                "quantity": 2.0,
                "price": 5.0,
                "commission": 0.65,
                "amount": 0.0,
                "date": t_open,
                "instrument_asset_type": "OPTION",
                "position_effect": "OPENING",
            },
            {
                "id": "schwab-exec-close-1",
                "symbol": OPT,
                "action": "TRADE",
                "quantity": -2.0,
                "price": 8.0,
                "commission": 0.65,
                "amount": 0.0,
                "date": t_close,
                "instrument_asset_type": "OPTION",
                "position_effect": "CLOSING",
            },
        ]

    async def get_account_balances(self, account_number: str) -> dict[str, Any]:
        return {}


def test_schwab_sync_creates_option_tax_lot_with_pnl(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    if db_session is None:
        pytest.skip("no db")
    from app.services.portfolio import schwab_sync_service

    monkeypatch.setattr(
        schwab_sync_service.account_credentials_service,
        "get_decrypted",
        _credentials,
    )
    acct = _user_and_account(db_session)
    svc = SchwabSyncService(client=_ClientOptionRoundTrip())
    out = asyncio.run(
        svc.sync_account_comprehensive(account_number=acct.account_number, session=db_session)
    )
    assert out.get("option_tax_lots_created", 0) >= 1
    db_session.commit()

    rows = (
        db_session.query(OptionTaxLot)
        .filter(OptionTaxLot.broker_account_id == acct.id, OptionTaxLot.user_id == acct.user_id)
        .all()
    )
    assert len(rows) == 1
    r = rows[0]
    assert r.quantity_closed == Decimal("2")
    assert r.option_type == "call"
    assert r.underlying == "AAPL"
    assert r.holding_class == "short_term"
    assert r.realized_pnl is not None
    # Per contract: open cost 5 + 0.65/2, close proceeds 8 - 0.65/2; ×2 contracts ×100 mult
    assert r.realized_pnl == Decimal("470.0000")


def test_schwab_option_tax_lots_idempotent_second_sync(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    if db_session is None:
        pytest.skip("no db")
    from app.services.portfolio import schwab_sync_service

    monkeypatch.setattr(
        schwab_sync_service.account_credentials_service,
        "get_decrypted",
        _credentials,
    )
    acct = _user_and_account(db_session)
    client = _ClientOptionRoundTrip()
    svc = SchwabSyncService(client=client)
    for _ in range(2):
        asyncio.run(
            svc.sync_account_comprehensive(account_number=acct.account_number, session=db_session)
        )
        db_session.commit()
    n = db_session.query(OptionTaxLot).filter(OptionTaxLot.broker_account_id == acct.id).count()
    assert n == 1
