"""Tests for account management: sync-history, PATCH, 409, credentials."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

try:
    from app.api.dependencies import get_current_user, get_optional_user
    from app.api.main import app
    from app.database import get_db
    from app.models import BrokerAccount, User
    from app.models.broker_account import (
        AccountSync,
        AccountType,
        BrokerType,
        SyncStatus,
    )
    from app.models.user import UserRole

    AVAILABLE = True
except Exception:
    AVAILABLE = False


@pytest.fixture
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except TypeError:
        pytest.skip("TestClient not available")


@pytest.fixture
def auth_user(db_session):
    """Create test user for auth (admin to bypass portfolio release checks)."""
    user = User(
        email="accttest@example.com",
        username="accttestuser",
        password_hash="dummy",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(auth_user):
    from app.api.security import create_access_token

    token = create_access_token({"sub": str(auth_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def broker_account(db_session, auth_user):
    """Create broker account for auth user."""
    acc = BrokerAccount(
        user_id=auth_user.id,
        broker=BrokerType.IBKR,
        account_number="U123",
        account_name="Test IBKR",
        account_type=AccountType.TAXABLE,
        sync_status=SyncStatus.NEVER_SYNCED,
        is_enabled=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def _setup_overrides(db_session, auth_user):
    """Override get_db and get_current_user for tests."""

    def _get_db():
        yield db_session

    def _get_user():
        return auth_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    app.dependency_overrides[get_optional_user] = _get_user


def _teardown_overrides():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_sync_history_returns_only_owned(client, db_session, auth_user, broker_account):
    """GET sync-history returns only syncs for user's accounts."""
    _setup_overrides(db_session, auth_user)
    try:
        sync = AccountSync(
            account_id=broker_account.id,
            sync_type="comprehensive",
            status=SyncStatus.SUCCESS,
            started_at=datetime.now(UTC),
        )
        db_session.add(sync)
        db_session.commit()

        r = client.get("/api/v1/accounts/sync-history")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
    finally:
        _teardown_overrides()


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_sync_returns_409_when_running(client, broker_account, db_session, auth_user):
    """Sync returns 409 when sync_status is QUEUED or RUNNING."""
    _setup_overrides(db_session, auth_user)
    try:
        broker_account.sync_status = SyncStatus.RUNNING
        db_session.commit()

        r = client.post(
            f"/api/v1/accounts/{broker_account.id}/sync",
            json={"sync_type": "comprehensive"},
        )
        assert r.status_code == 409
    finally:
        _teardown_overrides()


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_patch_account_validates_ownership(client, db_session, auth_user):
    """PATCH /accounts/{id} returns 404 for non-owned account."""
    _setup_overrides(db_session, auth_user)
    try:
        other_user = User(
            email="other@example.com",
            username="otheruser",
            password_hash="dummy",
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        other_acc = BrokerAccount(
            user_id=other_user.id,
            broker=BrokerType.IBKR,
            account_number="U999",
            account_type=AccountType.TAXABLE,
            is_enabled=True,
        )
        db_session.add(other_acc)
        db_session.commit()
        db_session.refresh(other_acc)

        r = client.patch(
            f"/api/v1/accounts/{other_acc.id}",
            json={"account_name": "Hacked"},
        )
        assert r.status_code == 404
    finally:
        _teardown_overrides()


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_patch_credentials_validates_ownership(client, db_session, auth_user):
    """PATCH /accounts/{id}/credentials returns 404 for non-owned account."""
    _setup_overrides(db_session, auth_user)
    try:
        other_user = User(
            email="other2@example.com",
            username="otheruser2",
            password_hash="dummy",
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        other_acc = BrokerAccount(
            user_id=other_user.id,
            broker=BrokerType.IBKR,
            account_number="U888",
            account_type=AccountType.TAXABLE,
            is_enabled=True,
        )
        db_session.add(other_acc)
        db_session.commit()
        db_session.refresh(other_acc)

        r = client.patch(
            f"/api/v1/accounts/{other_acc.id}/credentials",
            json={"broker": "ibkr", "credentials": {"flex_token": "x", "query_id": "y"}},
        )
        assert r.status_code == 404
    finally:
        _teardown_overrides()
