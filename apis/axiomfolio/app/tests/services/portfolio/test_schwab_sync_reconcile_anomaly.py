"""reconcile_closing_lots error path: anomaly counter, env-specific re-raise."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from app.config import settings
from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.models.user import User
from app.services.portfolio.schwab_sync_service import (
    RECONCILE_ANOMALY_KEY,
    SchwabSyncService,
)


class _FakeRedis:
    """In-memory stand-in for RECONCILE_ANOMALY_KEY incr + rolling expire."""

    def __init__(self) -> None:
        self._kv: dict[str, int] = {}
        self.expire_calls: list[tuple[str, int]] = []

    def incr(self, key: str) -> int:
        n = int(self._kv.get(key, 0)) + 1
        self._kv[key] = n
        return n

    def expire(self, key: str, seconds: int) -> None:
        self.expire_calls.append((key, int(seconds)))

    def get(self, key: str) -> bytes | None:
        if key not in self._kv:
            return None
        return str(self._kv[key]).encode("ascii")


class _DummySchwabClient:
    """Minimal client: enough data for sync to reach closing-lot reconciliation."""

    def __init__(self) -> None:
        self.connected = True

    async def connect_with_credentials(
        self, access_token: str, refresh_token: str, **kwargs: Any
    ) -> bool:
        return True

    def set_token_refresh_callback(self, callback: Any) -> None:
        pass

    async def get_positions(self, account_number: str) -> list[dict[str, Any]]:
        return [
            {
                "symbol": "AAPL",
                "quantity": 1,
                "average_cost": 100.0,
                "total_cost_basis": 100.0,
            },
        ]

    async def get_options_positions(self, account_number: str) -> list[dict[str, Any]]:
        return []

    async def get_transactions(self, account_number: str) -> list[dict[str, Any]]:
        return []

    async def get_account_balances(self, account_number: str) -> dict[str, Any]:
        return {}

    async def get_corporate_actions(self, account_number: str) -> list[dict[str, Any]]:
        return []


def _raiser(*_a: Any, **_kw: Any) -> None:
    raise RuntimeError("forced reconcile_closing_lots failure for test")


def _make_user_and_account(db_session) -> BrokerAccount:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"rec_anom_{suffix}@example.com",
        username=f"rec_anom_{suffix}",
        password_hash="x" * 32,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    acct = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.SCHWAB,
        account_number=f"SCH-RA-{suffix}",
        account_name="Reconcile test",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    db_session.add(acct)
    db_session.commit()
    db_session.refresh(acct)
    return acct


@pytest.mark.usefixtures("db_session")
def test_reconcile_error_production_continues_and_records_anomaly(db_session, monkeypatch) -> None:
    if db_session is None:
        pytest.skip("database not configured")

    from app.services.portfolio import schwab_sync_service

    def _fake_get_decrypted(_account_id: int, _session: Any) -> dict[str, str]:
        return {"access_token": "fake", "refresh_token": "fake"}

    monkeypatch.setattr(
        schwab_sync_service.account_credentials_service,
        "get_decrypted",
        _fake_get_decrypted,
    )
    monkeypatch.setattr(schwab_sync_service, "reconcile_closing_lots", _raiser)
    fake_r = _FakeRedis()
    monkeypatch.setattr(
        "app.services.market.market_data_service.infra",
        SimpleNamespace(redis_client=fake_r),
    )
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    # Conftest's after_transaction_end savepoint restarter conflicts with
    # ``begin_nested`` rollback when reconcile fails; a no-op nested context
    # keeps the test session valid while still exercising the sync error path.
    monkeypatch.setattr(db_session, "begin_nested", nullcontext, raising=False)

    acct = _make_user_and_account(db_session)
    service = SchwabSyncService(client=_DummySchwabClient())

    with mock.patch.object(
        schwab_sync_service.logger, "warning", wraps=schwab_sync_service.logger.warning
    ) as w_mock:
        result = asyncio.run(
            service.sync_account_comprehensive(
                account_number=acct.account_number, session=db_session
            )
        )
    w_mock.assert_any_call(
        "reconcile_closing_lots failed for user=%s account=%s: %s",
        acct.user_id,
        acct.account_number,
        mock.ANY,
    )

    assert result.get("status") == "success"
    assert "closed_lots_error" in result
    assert "forced reconcile" in (result.get("closed_lots_error") or "")
    assert fake_r._kv.get(RECONCILE_ANOMALY_KEY) == 1
    assert (RECONCILE_ANOMALY_KEY, 60 * 60 * 24 * 7) in fake_r.expire_calls


@pytest.mark.usefixtures("db_session")
def test_reconcile_error_development_re_raises(db_session, monkeypatch) -> None:
    if db_session is None:
        pytest.skip("database not configured")

    from app.services.portfolio import schwab_sync_service

    def _fake_get_decrypted(_account_id: int, _session: Any) -> dict[str, str]:
        return {"access_token": "fake", "refresh_token": "fake"}

    monkeypatch.setattr(
        schwab_sync_service.account_credentials_service,
        "get_decrypted",
        _fake_get_decrypted,
    )
    monkeypatch.setattr(schwab_sync_service, "reconcile_closing_lots", _raiser)
    fake_r = _FakeRedis()
    monkeypatch.setattr(
        "app.services.market.market_data_service.infra",
        SimpleNamespace(redis_client=fake_r),
    )
    monkeypatch.setattr(settings, "ENVIRONMENT", "development", raising=False)
    monkeypatch.setattr(db_session, "begin_nested", nullcontext, raising=False)

    acct = _make_user_and_account(db_session)
    service = SchwabSyncService(client=_DummySchwabClient())

    with mock.patch.object(
        schwab_sync_service.logger, "warning", wraps=schwab_sync_service.logger.warning
    ) as w_mock, pytest.raises(RuntimeError, match="forced reconcile"):
        asyncio.run(
            service.sync_account_comprehensive(
                account_number=acct.account_number, session=db_session
            )
        )
    w_mock.assert_any_call(
        "reconcile_closing_lots failed for user=%s account=%s: %s",
        acct.user_id,
        acct.account_number,
        mock.ANY,
    )
    assert fake_r._kv.get(RECONCILE_ANOMALY_KEY) == 1
