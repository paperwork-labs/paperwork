"""API tests for the connection-options endpoint backing the Connect hub."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_current_user
from backend.api.main import app
from backend.database import get_db
from backend.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerAccount,
    BrokerType,
)
from backend.models.user import User, UserRole


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available")


def _make_user(db_session) -> User:
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"conn_{suffix}@example.com",
        username=f"conn_{suffix}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    return _make_user(db_session)


@pytest.fixture
def other_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    return _make_user(db_session)


@pytest.fixture
def _wire_overrides(db_session, auth_user):
    """Pin get_db to the test session and short-circuit auth to ``auth_user``.

    Not autouse: the cross-tenant-isolation test needs to swap the auth
    override mid-test, so it manages overrides itself.
    """

    if db_session is None:
        yield
        return

    def _get_db():
        yield db_session

    def _get_user():
        return auth_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def _add_schwab_account(
    db_session, user: User, *, last_synced_at: datetime | None = None
) -> BrokerAccount:
    acc = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.SCHWAB,
        account_number=f"SCH-{uuid.uuid4().hex[:8]}",
        account_name="Test Schwab",
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        is_enabled=True,
        last_successful_sync=last_synced_at,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def test_requires_auth(client: TestClient, db_session):
    """Without an auth override the route must reject the request.

    Mirrors the contract of every other authenticated portfolio route.
    """

    if db_session is None:
        pytest.skip("database not configured")
    # No dependency overrides wired — the global HTTPBearer should refuse.
    res = client.get("/api/v1/portfolio/connection-options")
    assert res.status_code in (401, 403)


def test_returns_full_catalog_shape(
    client: TestClient, db_session, auth_user, _wire_overrides
):
    """Catalog returns >= 20 brokers with the documented fields and enums."""

    if db_session is None:
        pytest.skip("database not configured")

    res = client.get("/api/v1/portfolio/connection-options")
    assert res.status_code == 200, res.text
    body = res.json()
    brokers = body["brokers"]
    assert isinstance(brokers, list)
    assert len(brokers) >= 20, f"expected 20+ brokers, got {len(brokers)}"

    slugs = {b["slug"] for b in brokers}
    # Sanity: a few specific slugs must be present.
    for required in ("schwab", "fidelity", "vanguard", "etrade", "robinhood_snaptrade"):
        assert required in slugs, f"missing required broker slug: {required}"

    valid_categories = {"stocks", "crypto", "retirement"}
    valid_methods = {"oauth", "import"}
    valid_statuses = {"available", "coming_v1_1", "coming_v1_2_snaptrade"}

    for broker in brokers:
        for field in (
            "slug",
            "name",
            "description",
            "logo_url",
            "category",
            "method",
            "status",
            "user_state",
        ):
            assert field in broker, f"{broker.get('slug')} missing field {field}"
        assert broker["category"] in valid_categories
        assert broker["method"] in valid_methods
        assert broker["status"] in valid_statuses
        assert broker["logo_url"].startswith("/broker-logos/")
        us = broker["user_state"]
        assert isinstance(us["connected"], bool)
        assert isinstance(us["account_count"], int)


def test_user_state_reflects_existing_broker_account(
    client: TestClient, db_session, auth_user, _wire_overrides
):
    """A Schwab BrokerAccount row should flip user_state.connected to True."""

    if db_session is None:
        pytest.skip("database not configured")

    last_sync = datetime.utcnow() - timedelta(minutes=5)
    _add_schwab_account(db_session, auth_user, last_synced_at=last_sync)

    res = client.get("/api/v1/portfolio/connection-options")
    assert res.status_code == 200, res.text
    by_slug = {b["slug"]: b for b in res.json()["brokers"]}

    schwab = by_slug["schwab"]
    assert schwab["user_state"]["connected"] is True
    assert schwab["user_state"]["account_count"] == 1
    assert schwab["user_state"]["last_synced_at"] is not None

    # Brokers without rows must remain not-connected (no leakage across slugs).
    fidelity = by_slug["fidelity"]
    assert fidelity["user_state"]["connected"] is False
    assert fidelity["user_state"]["account_count"] == 0


def test_inactive_account_does_not_count_as_connected(
    client: TestClient, db_session, auth_user, _wire_overrides
):
    """A previously-disconnected (INACTIVE/CLOSED) account must not flip the flag."""

    if db_session is None:
        pytest.skip("database not configured")

    acc = _add_schwab_account(db_session, auth_user)
    acc.status = AccountStatus.CLOSED
    db_session.commit()

    res = client.get("/api/v1/portfolio/connection-options")
    assert res.status_code == 200, res.text
    by_slug = {b["slug"]: b for b in res.json()["brokers"]}
    assert by_slug["schwab"]["user_state"]["connected"] is False


def test_cross_tenant_isolation(
    client: TestClient, db_session, auth_user, other_user
):
    """User A's BrokerAccount must NOT show as connected for User B.

    We deliberately wire overrides manually here so we can swap which user
    the auth dependency returns mid-test.
    """

    if db_session is None:
        pytest.skip("database not configured")

    # User A has a connected Schwab account.
    _add_schwab_account(db_session, auth_user)

    def _get_db():
        yield db_session

    # First request as User A — should see connected=True.
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: auth_user
    try:
        res_a = client.get("/api/v1/portfolio/connection-options")
        assert res_a.status_code == 200, res_a.text
        a_schwab = next(b for b in res_a.json()["brokers"] if b["slug"] == "schwab")
        assert a_schwab["user_state"]["connected"] is True

        # Second request as User B — must NOT see User A's account.
        app.dependency_overrides[get_current_user] = lambda: other_user
        res_b = client.get("/api/v1/portfolio/connection-options")
        assert res_b.status_code == 200, res_b.text
        b_schwab = next(b for b in res_b.json()["brokers"] if b["slug"] == "schwab")
        assert b_schwab["user_state"]["connected"] is False
        assert b_schwab["user_state"]["account_count"] == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
