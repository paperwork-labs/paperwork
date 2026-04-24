"""Historical import route tests (G23)."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

try:
    from app.api.dependencies import get_current_user, get_optional_user
    from app.api.main import app
    from app.database import get_db
    from app.models.broker_account import AccountType, BrokerAccount, BrokerType
    from app.models.historical_import_run import (
        HistoricalImportRun,
        HistoricalImportSource,
        HistoricalImportStatus,
    )
    from app.models.user import User, UserRole

    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@pytest.fixture
def client():
    if not AVAILABLE:
        pytest.skip("Dependencies not available")
    return TestClient(app, raise_server_exceptions=False)


def _setup_overrides(db_session, user):
    def _get_db():
        yield db_session

    def _get_user():
        return user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    app.dependency_overrides[get_optional_user] = _get_user


def _teardown_overrides():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)


def _make_user(db_session, username: str) -> User:
    user = User(
        email=f"{username}@example.com",
        username=username,
        password_hash="x",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_account(db_session, user: User, number: str) -> BrokerAccount:
    account = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.IBKR,
        account_number=number,
        account_type=AccountType.TAXABLE,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_malformed_xml_returns_structured_error(client, db_session):
    user = _make_user(db_session, "hist_xml_user")
    account = _make_account(db_session, user, "U-HIST-1")
    _setup_overrides(db_session, user)
    try:
        resp = client.post(
            f"/api/v1/accounts/{account.id}/historical-import",
            json={
                "date_from": "2023-01-01",
                "date_to": "2023-12-31",
                "xml_content": "<FlexQueryResponse><oops></FlexQueryResponse>",
            },
        )
        assert resp.status_code == 422
        payload = resp.json()
        assert payload["detail"]["code"] == "malformed_xml"
    finally:
        _teardown_overrides()


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_run_lookup_is_tenant_scoped(client, db_session):
    user_a = _make_user(db_session, "hist_run_a")
    user_b = _make_user(db_session, "hist_run_b")
    account_a = _make_account(db_session, user_a, "U-HIST-A")
    account_b = _make_account(db_session, user_b, "U-HIST-B")
    run_b = HistoricalImportRun(
        user_id=user_b.id,
        account_id=account_b.id,
        source=HistoricalImportSource.CSV,
        status=HistoricalImportStatus.QUEUED,
        date_from=date(2024, 1, 1),
        date_to=date(2024, 1, 31),
    )
    db_session.add(run_b)
    db_session.commit()
    db_session.refresh(run_b)

    _setup_overrides(db_session, user_a)
    try:
        resp = client.get(
            f"/api/v1/accounts/{account_a.id}/historical-import/{run_b.id}"
        )
        assert resp.status_code == 404
    finally:
        _teardown_overrides()
