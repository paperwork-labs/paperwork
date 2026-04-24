import uuid
import pytest

from app.services.portfolio.broker_sync_service import broker_sync_service
from app.models.broker_account import BrokerAccount, BrokerType, AccountType


def _ensure_account(session) -> BrokerAccount:
    from app.models.user import User

    user = session.query(User).filter(User.username == "route_tester").first()
    if not user:
        user = User(username="route_tester", email="route_tester@example.com", password_hash="x", is_active=True)
        session.add(user)
        session.commit()
        session.refresh(user)
    acct = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.SCHWAB,
        account_number=f"S{uuid.uuid4().hex[:6]}",
        account_name="Route Schwab",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(acct)
    session.commit()
    session.refresh(acct)
    return acct


def test_broker_sync_routes_to_schwab(monkeypatch, db_session):
    # Global singleton may cache a real Schwab service from an earlier test.
    broker_sync_service._broker_services.pop(BrokerType.SCHWAB, None)

    calls = {"count": 0}

    class DummyService:
        # Sync return (same contract as unittest.Mock.return_value in
        # test_broker_sync_service.py). An async def here fails under
        # pytest-asyncio: broker_sync_service._run uses run_until_complete,
        # which raises when an event loop is already running.
        def sync_account_comprehensive(self, account_number, session):
            calls["count"] += 1
            return {"status": "success", "account_number": account_number}

    # Patch the SchwabSyncService used inside the router
    import app.services.portfolio.schwab_sync_service as schwab_module

    monkeypatch.setattr(schwab_module, "SchwabSyncService", lambda: DummyService())

    acct = _ensure_account(db_session)
    result = broker_sync_service.sync_account(account_id=acct.account_number, db=db_session, sync_type="comprehensive")
    assert result["status"] == "success"
    assert calls["count"] == 1


