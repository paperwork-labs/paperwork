"""Tests for GET /api/v1/connections/health and aggregation helpers."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

os.environ.setdefault("OAUTH_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.api.dependencies import get_current_user  # noqa: E402
from app.api.main import app  # noqa: E402
from app.database import get_db  # noqa: E402
from app.models.broker_account import (  # noqa: E402
    AccountType,
    BrokerAccount,
    BrokerType,
    SyncStatus,
)
from app.models.broker_oauth_connection import (  # noqa: E402
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from app.models.user import User, UserRole  # noqa: E402
from app.services.connections.health_aggregate import (  # noqa: E402
    build_connections_health,
)
from app.services.oauth.encryption import encrypt  # noqa: E402


def _make_user(db_session) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"conn_health_{suffix}@example.com",
        username=f"conn_health_{suffix}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def route_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    return _make_user(db_session)


@pytest.fixture
def other_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    return _make_user(db_session)


@pytest.fixture(autouse=True)
def _wire_overrides(db_session, route_user):
    if db_session is None:
        yield
        return

    def _get_db():
        yield db_session

    def _get_user():
        return route_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_health_empty_user(client: TestClient):
    res = client.get("/api/v1/connections/health")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["connected"] == 0
    assert body["total"] == 6
    assert body["last_sync_at"] is None
    assert len(body["by_broker"]) == 6
    assert all(row["status"] == "disconnected" for row in body["by_broker"])


def test_health_cross_tenant_isolation(client: TestClient, db_session, other_user: User):
    foreign = BrokerAccount(
        user_id=other_user.id,
        broker=BrokerType.SCHWAB,
        account_number="U_FOREIGN",
        account_type=AccountType.TAXABLE,
    )
    db_session.add(foreign)
    db_session.flush()

    res = client.get("/api/v1/connections/health")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["connected"] == 0
    schwab_row = next(r for r in body["by_broker"] if r["broker"] == "schwab")
    assert schwab_row["status"] == "disconnected"


def test_health_connected_with_last_sync(client: TestClient, db_session, route_user: User):
    when = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    acct = BrokerAccount(
        user_id=route_user.id,
        broker=BrokerType.IBKR,
        account_number="U123",
        account_type=AccountType.TAXABLE,
        last_successful_sync=when,
        sync_status=SyncStatus.SUCCESS,
    )
    db_session.add(acct)
    db_session.flush()

    res = client.get("/api/v1/connections/health")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["connected"] == 1
    assert body["last_sync_at"] is not None
    ibkr_row = next(r for r in body["by_broker"] if r["broker"] == "ibkr")
    assert ibkr_row["status"] == "connected"


def test_health_oauth_expired_is_stale(client: TestClient, db_session, route_user: User):
    acct = BrokerAccount(
        user_id=route_user.id,
        broker=BrokerType.SCHWAB,
        account_number="SCHWAB_OAUTH",
        account_type=AccountType.TAXABLE,
        sync_status=SyncStatus.SUCCESS,
    )
    conn = BrokerOAuthConnection(
        user_id=route_user.id,
        broker="schwab",
        provider_account_id="p1",
        status=OAuthConnectionStatus.EXPIRED.value,
        access_token_encrypted=encrypt("tok"),
        environment="live",
        rotation_count=0,
    )
    db_session.add_all([acct, conn])
    db_session.flush()

    res = client.get("/api/v1/connections/health")
    assert res.status_code == 200, res.text
    schwab_row = next(r for r in res.json()["by_broker"] if r["broker"] == "schwab")
    assert schwab_row["status"] == "stale"


def test_health_sync_failed_is_error(client: TestClient, db_session, route_user: User):
    acct = BrokerAccount(
        user_id=route_user.id,
        broker=BrokerType.TASTYTRADE,
        account_number="TT1",
        account_type=AccountType.TAXABLE,
        sync_status=SyncStatus.FAILED,
        sync_error_message="upstream timeout",
    )
    db_session.add(acct)
    db_session.flush()

    res = client.get("/api/v1/connections/health")
    assert res.status_code == 200, res.text
    row = next(r for r in res.json()["by_broker"] if r["broker"] == "tastytrade")
    assert row["status"] == "error"
    assert "timeout" in (row.get("error_message") or "")


def test_build_connections_health_matches_route(client: TestClient, db_session, route_user: User):
    acct = BrokerAccount(
        user_id=route_user.id,
        broker=BrokerType.COINBASE,
        account_number="CB1",
        account_type=AccountType.TAXABLE,
        last_successful_sync=datetime.now(timezone.utc) - timedelta(hours=2),
        sync_status=SyncStatus.SUCCESS,
    )
    db_session.add(acct)
    db_session.flush()

    direct = build_connections_health(db_session, route_user.id)
    res = client.get("/api/v1/connections/health")
    assert res.status_code == 200
    assert res.json()["connected"] == direct["connected"]
    assert res.json()["total"] == direct["total"]
