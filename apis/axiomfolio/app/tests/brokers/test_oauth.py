"""OAuth broker API hardening (constraints, errors, multi-tenant state)."""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

os.environ.setdefault("OAUTH_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ETRADE_SANDBOX_KEY", "dummy-consumer-key")
os.environ.setdefault("ETRADE_SANDBOX_SECRET", "dummy-consumer-secret")
os.environ.setdefault(
    "OAUTH_ALLOWED_CALLBACK_URLS",
    "https://app.example/cb",
)

from app.api.dependencies import get_current_user
from app.api.main import app
from app.database import get_db
from app.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from app.models.user import User, UserRole
from app.services.oauth import (
    OAuthError,
    OAuthInitiateResult,
    OAuthTokens,
    register_adapter,
    state_store,
)
from app.services.oauth.base import OAuthBrokerAdapter
from app.services.oauth.encryption import encrypt
from app.services.oauth.etrade import ETradeSandboxAdapter


def _make_user(db_session) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"brokers_oauth_{suffix}@example.com",
        username=f"brokers_oauth_{suffix}",
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


class _PermanentExchangeFailureAdapter(OAuthBrokerAdapter):
    broker_id = "etrade_sandbox"
    environment = "sandbox"

    def initiate_url(self, *, user_id, callback_url):
        return OAuthInitiateResult(
            authorize_url="https://example.com/auth",
            state="S",
            extra={},
        )

    def exchange_code(self, ctx):
        raise OAuthError(
            "token exchange failed",
            permanent=True,
            broker=self.broker_id,
        )

    def refresh(self, *, access_token, refresh_token):
        raise NotImplementedError

    def revoke(self, *, access_token, refresh_token=None):
        return None


def test_duplicate_null_provider_account_blocked(db_session):
    """Functional unique index: only one (user, broker) when provider id is null."""

    if db_session is None:
        pytest.skip("database not configured")
    user = _make_user(db_session)
    a = BrokerOAuthConnection(
        user_id=user.id,
        broker="etrade_sandbox",
        provider_account_id=None,
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt("x"),
        environment="sandbox",
        rotation_count=0,
    )
    b = BrokerOAuthConnection(
        user_id=user.id,
        broker="etrade_sandbox",
        provider_account_id=None,
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt("y"),
        environment="sandbox",
        rotation_count=0,
    )
    db_session.add(a)
    db_session.flush()
    db_session.add(b)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_token_exchange_permanent_failure_returns_400(client, route_user):
    register_adapter(_PermanentExchangeFailureAdapter)
    state_store.clear_memory_store()
    try:
        state_store.save_extra(
            "etrade_sandbox",
            "EX-STATE",
            {"_user_id": route_user.id},
        )
        res = client.post(
            "/api/v1/oauth/etrade_sandbox/callback",
            json={"state": "EX-STATE", "code": "v"},
        )
        assert res.status_code == 400, res.text
        assert "token exchange" in res.json()["detail"].lower() or res.json()["detail"]
    finally:
        register_adapter(ETradeSandboxAdapter)


def test_state_ttl_expired_returns_401(client, route_user):
    state_store.clear_memory_store()
    state_store.save_extra(
        "etrade_sandbox",
        "SHORT-TTL",
        {"_user_id": route_user.id},
        ttl_seconds=1,
    )
    time.sleep(1.25)
    res = client.post(
        "/api/v1/oauth/etrade_sandbox/callback",
        json={"state": "SHORT-TTL", "code": "v"},
    )
    assert res.status_code == 401, res.text


def test_cross_tenant_cannot_consume_state(client, route_user, other_user):
    class _OkAdapter(OAuthBrokerAdapter):
        broker_id = "etrade_sandbox"
        environment = "sandbox"

        def initiate_url(self, *, user_id, callback_url):
            return OAuthInitiateResult(authorize_url="u", state="s", extra={})

        def exchange_code(self, ctx):
            return OAuthTokens(
                access_token="a",
                refresh_token="r",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )

        def refresh(self, *, access_token, refresh_token):
            raise NotImplementedError

        def revoke(self, *, access_token, refresh_token=None):
            return None

    register_adapter(_OkAdapter)
    state_store.clear_memory_store()
    try:
        state_store.save_extra(
            "etrade_sandbox",
            "TENANT-STATE",
            {"_user_id": other_user.id},
        )
        res = client.post(
            "/api/v1/oauth/etrade_sandbox/callback",
            json={"state": "TENANT-STATE", "code": "v"},
        )
        assert res.status_code == 403, res.text
    finally:
        register_adapter(ETradeSandboxAdapter)
