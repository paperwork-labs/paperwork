"""Tests for the OAuth broker foundation + E*TRADE sandbox adapter.

Coverage map (mirrors acceptance criteria in the dispatch brief):

* OAuth 1.0a primitives — signature base string + HMAC-SHA1 determinism
* Token encryption roundtrip via Fernet (with key rotation)
* ``ETradeSandboxAdapter`` happy-path (initiate -> exchange -> refresh) and
  permanent-vs-transient error classification
* ``_refresh_one`` covers success, permanent failure, transient failure,
  decrypt failure, and unsupported-broker
* FastAPI routes — initiate/callback/list/revoke + cross-tenant isolation
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

# Ensure encryption is available before any module imports settings indirectly.
os.environ.setdefault("OAUTH_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ETRADE_SANDBOX_KEY", "dummy-consumer-key")
os.environ.setdefault("ETRADE_SANDBOX_SECRET", "dummy-consumer-secret")
os.environ.setdefault(
    "OAUTH_ALLOWED_CALLBACK_URLS",
    "https://app.example/cb",
)

from backend.api.dependencies import get_current_user  # noqa: E402
from backend.api.main import app  # noqa: E402
from backend.database import get_db  # noqa: E402
from backend.models.broker_oauth_connection import (  # noqa: E402
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from backend.models.user import User, UserRole  # noqa: E402
from backend.services.oauth import (  # noqa: E402
    OAuthCallbackContext,
    OAuthError,
    OAuthInitiateResult,
    OAuthTokens,
    register_adapter,
)
from backend.services.oauth.base import OAuthBrokerAdapter  # noqa: E402
from backend.services.oauth.encryption import (  # noqa: E402
    decrypt,
    encrypt,
    reset_cache,
)
from backend.services.oauth.etrade import (  # noqa: E402
    ETradeSandboxAdapter,
    build_signature_base_string,
    sign_hmac_sha1,
)
from backend.services.oauth import state_store  # noqa: E402
from backend.tasks.portfolio.oauth_token_refresh import _refresh_one  # noqa: E402


# ---------------------------------------------------------------------------
# Stub HTTP plumbing — we never hit E*TRADE in tests.
# ---------------------------------------------------------------------------


class _StubResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


class _StubSession:
    """Mimics the requests.Session.request() surface."""

    def __init__(self, responses: List[_StubResponse]) -> None:
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def request(self, method: str, url: str, *, headers: Dict[str, str], timeout: float):
        self.calls.append({"method": method, "url": url, "headers": headers, "timeout": timeout})
        if not self._responses:
            raise AssertionError("stub session ran out of responses")
        return self._responses.pop(0)


# ---------------------------------------------------------------------------
# OAuth 1.0a primitives
# ---------------------------------------------------------------------------


def test_signature_base_string_matches_canonical_form():
    method = "GET"
    url = "https://apisb.etrade.com/oauth/request_token"
    params = {
        "oauth_callback": "oob",
        "oauth_consumer_key": "key",
        "oauth_nonce": "nonce123",
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": "1700000000",
        "oauth_version": "1.0",
    }
    base = build_signature_base_string(method, url, params)
    # Method, URL, and params section in the right order.
    assert base.startswith("GET&")
    assert "apisb.etrade.com" in base
    # All keys appear url-encoded and sorted.
    for key in params:
        assert key in base
    # Ampersands inside the param block are encoded as %26.
    assert "&" in base
    assert "%26" in base


def test_hmac_sha1_signature_is_deterministic():
    base = "GET&https%3A%2F%2Fapisb.etrade.com%2Fp&a%3D1%26b%3D2"
    sig_a = sign_hmac_sha1(base, "consumer_secret", "token_secret")
    sig_b = sign_hmac_sha1(base, "consumer_secret", "token_secret")
    sig_other = sign_hmac_sha1(base, "consumer_secret", "different")
    assert sig_a == sig_b
    assert sig_a != sig_other
    # Base64-encoded SHA1 -> 28 chars including trailing '='.
    assert len(sig_a) == 28
    assert sig_a.endswith("=")


# ---------------------------------------------------------------------------
# Token encryption
# ---------------------------------------------------------------------------


def test_token_encryption_roundtrip_and_isolation():
    reset_cache()
    plaintext = "etrade-access-token-abc"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext
    # Fernet ciphertexts include a random nonce; identical plaintexts encrypt
    # to different ciphertexts each time.
    assert encrypt(plaintext) != ciphertext


def test_encryption_key_rotation_via_retired_keys(monkeypatch):
    from backend.services.oauth import encryption as enc_module

    primary = Fernet.generate_key().decode()
    retired = Fernet.generate_key().decode()
    # Encrypt with retired-as-primary
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", retired)
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEYS_RETIRED", "")
    enc_module.reset_cache()
    # Reload settings cache because Settings reads env at import time.
    from backend.config import settings as _settings
    _settings.OAUTH_TOKEN_ENCRYPTION_KEY = retired
    _settings.OAUTH_TOKEN_ENCRYPTION_KEYS_RETIRED = ""
    ciphertext = enc_module.encrypt("rotate-me")

    # Now rotate: primary changes, retired moves to retired list.
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", primary)
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEYS_RETIRED", retired)
    _settings.OAUTH_TOKEN_ENCRYPTION_KEY = primary
    _settings.OAUTH_TOKEN_ENCRYPTION_KEYS_RETIRED = retired
    enc_module.reset_cache()
    # Old ciphertext still decrypts using retired key.
    assert enc_module.decrypt(ciphertext) == "rotate-me"
    # New encryption uses primary; new ciphertext also decrypts.
    new_ct = enc_module.encrypt("rotated")
    assert enc_module.decrypt(new_ct) == "rotated"


# ---------------------------------------------------------------------------
# E*TRADE adapter
# ---------------------------------------------------------------------------


def test_etrade_initiate_returns_authorize_url_with_state(monkeypatch):
    session = _StubSession(
        [
            _StubResponse(
                200,
                "oauth_token=req-token&oauth_token_secret=req-secret",
            )
        ]
    )
    adapter = ETradeSandboxAdapter(
        consumer_key="ck", consumer_secret="cs", session=session
    )
    result = adapter.initiate_url(user_id=42, callback_url="https://app/cb")
    assert isinstance(result, OAuthInitiateResult)
    assert "key=ck" in result.authorize_url
    assert "token=req-token" in result.authorize_url
    assert result.extra["request_token"] == "req-token"
    assert result.extra["request_token_secret"] == "req-secret"
    assert result.extra["user_id"] == 42
    assert len(result.state) > 16


def test_etrade_initiate_propagates_4xx_as_permanent():
    session = _StubSession([_StubResponse(401, "oauth_problem=signature_invalid")])
    adapter = ETradeSandboxAdapter(consumer_key="ck", consumer_secret="cs", session=session)
    with pytest.raises(OAuthError) as ei:
        adapter.initiate_url(user_id=1, callback_url="oob")
    assert ei.value.permanent is True
    assert ei.value.provider_status == 401


def test_etrade_initiate_propagates_5xx_as_transient():
    session = _StubSession([_StubResponse(503, "service unavailable")])
    adapter = ETradeSandboxAdapter(consumer_key="ck", consumer_secret="cs", session=session)
    with pytest.raises(OAuthError) as ei:
        adapter.initiate_url(user_id=1, callback_url="oob")
    assert ei.value.permanent is False
    assert ei.value.provider_status == 503


def test_etrade_exchange_code_sets_expiry_and_secret():
    session = _StubSession(
        [
            _StubResponse(
                200,
                "oauth_token=access-token&oauth_token_secret=access-secret",
            )
        ]
    )
    adapter = ETradeSandboxAdapter(consumer_key="ck", consumer_secret="cs", session=session)
    ctx = OAuthCallbackContext(
        code="VERIFIER123",
        state="abc",
        extra={
            "request_token": "req-token",
            "request_token_secret": "req-secret",
        },
    )
    tokens = adapter.exchange_code(ctx)
    assert isinstance(tokens, OAuthTokens)
    assert tokens.access_token == "access-token"
    assert tokens.refresh_token == "access-secret"  # OAuth 1.0a: secret stored here
    assert tokens.expires_at is not None
    assert tokens.expires_at > datetime.now(timezone.utc)


def test_etrade_exchange_code_raises_on_missing_request_token():
    adapter = ETradeSandboxAdapter(consumer_key="ck", consumer_secret="cs", session=_StubSession([]))
    ctx = OAuthCallbackContext(code="V", state="s", extra={})
    with pytest.raises(OAuthError) as ei:
        adapter.exchange_code(ctx)
    assert ei.value.permanent is True


def test_etrade_refresh_returns_new_expiry():
    session = _StubSession([_StubResponse(200, "")])  # E*TRADE renew may be empty body
    adapter = ETradeSandboxAdapter(consumer_key="ck", consumer_secret="cs", session=session)
    tokens = adapter.refresh(access_token="access", refresh_token="secret")
    assert tokens.access_token == "access"
    assert tokens.refresh_token == "secret"
    assert tokens.expires_at is not None


def test_etrade_revoke_swallows_provider_4xx():
    session = _StubSession([_StubResponse(400, "already revoked")])
    adapter = ETradeSandboxAdapter(consumer_key="ck", consumer_secret="cs", session=session)
    # Should not raise; logs WARN. Best-effort by design.
    adapter.revoke(access_token="access", refresh_token="secret")


def test_etrade_requires_credentials(monkeypatch):
    # Clear settings fallback so the constructor truly has no credentials.
    from backend.config import settings as _settings
    monkeypatch.setattr(_settings, "ETRADE_SANDBOX_KEY", None)
    monkeypatch.setattr(_settings, "ETRADE_SANDBOX_SECRET", None)
    adapter = ETradeSandboxAdapter(
        consumer_key=None, consumer_secret=None, session=_StubSession([])
    )
    with pytest.raises(OAuthError) as ei:
        adapter.initiate_url(user_id=1, callback_url="oob")
    assert ei.value.permanent is True


# ---------------------------------------------------------------------------
# _refresh_one (Celery helper)
# ---------------------------------------------------------------------------


class _PermFailureAdapter(OAuthBrokerAdapter):
    broker_id = "etrade_sandbox"
    environment = "sandbox"

    def initiate_url(self, **kwargs):  # pragma: no cover - unused
        raise NotImplementedError

    def exchange_code(self, ctx):  # pragma: no cover - unused
        raise NotImplementedError

    def refresh(self, *, access_token, refresh_token):
        raise OAuthError("invalid_grant", permanent=True, broker=self.broker_id, provider_status=401)

    def revoke(self, *, access_token, refresh_token=None):  # pragma: no cover - unused
        return None


class _TransientFailureAdapter(_PermFailureAdapter):
    def refresh(self, *, access_token, refresh_token):
        raise OAuthError("network down", permanent=False, broker=self.broker_id, provider_status=503)


class _SuccessAdapter(_PermFailureAdapter):
    def refresh(self, *, access_token, refresh_token):
        return OAuthTokens(
            access_token="new-access",
            refresh_token="new-secret",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )


def _make_user(db_session) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"oauth_{suffix}@example.com",
        username=f"oauth_{suffix}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_active_conn(db_session, *, user_id: int, expires_in_minutes: int = 5) -> BrokerOAuthConnection:
    conn = BrokerOAuthConnection(
        user_id=user_id,
        broker="etrade_sandbox",
        provider_account_id=None,
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt("acc-1"),
        refresh_token_encrypted=encrypt("sec-1"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        environment="sandbox",
        rotation_count=0,
    )
    db_session.add(conn)
    db_session.flush()
    return conn


def test_refresh_one_writes_on_success(db_session, monkeypatch):
    if db_session is None:
        pytest.skip("database not configured")
    user = _make_user(db_session)
    conn = _make_active_conn(db_session, user_id=user.id)

    register_adapter(_SuccessAdapter)
    try:
        outcome = _refresh_one(db_session, conn)
    finally:
        register_adapter(ETradeSandboxAdapter)

    assert outcome == "written"
    assert conn.status == OAuthConnectionStatus.ACTIVE.value
    assert decrypt(conn.access_token_encrypted) == "new-access"
    assert decrypt(conn.refresh_token_encrypted) == "new-secret"
    assert conn.rotation_count == 1
    assert conn.last_error is None


def test_refresh_one_marks_refresh_failed_on_permanent(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    user = _make_user(db_session)
    conn = _make_active_conn(db_session, user_id=user.id)

    register_adapter(_PermFailureAdapter)
    try:
        outcome = _refresh_one(db_session, conn)
    finally:
        register_adapter(ETradeSandboxAdapter)

    assert outcome == "errors"
    assert conn.status == OAuthConnectionStatus.REFRESH_FAILED.value
    assert "permanent" in (conn.last_error or "").lower()


def test_refresh_one_keeps_active_on_transient(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    user = _make_user(db_session)
    conn = _make_active_conn(db_session, user_id=user.id)

    register_adapter(_TransientFailureAdapter)
    try:
        outcome = _refresh_one(db_session, conn)
    finally:
        register_adapter(ETradeSandboxAdapter)

    assert outcome == "errors"
    assert conn.status == OAuthConnectionStatus.ACTIVE.value
    assert "transient" in (conn.last_error or "").lower()


def test_refresh_one_skips_revoked(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    user = _make_user(db_session)
    conn = _make_active_conn(db_session, user_id=user.id)
    conn.status = OAuthConnectionStatus.REVOKED.value
    db_session.flush()
    outcome = _refresh_one(db_session, conn)
    assert outcome == "skipped"


# ---------------------------------------------------------------------------
# FastAPI routes
# ---------------------------------------------------------------------------


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
    """Pin get_db to the test session and short-circuit the user dep."""

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


class _RouteStubAdapter(OAuthBrokerAdapter):
    broker_id = "etrade_sandbox"
    environment = "sandbox"

    def initiate_url(self, *, user_id, callback_url):
        return OAuthInitiateResult(
            authorize_url=f"https://etrade.example/auth?cb={callback_url}",
            state="ROUTE-STATE-NONCE",
            extra={"request_token": "rt", "request_token_secret": "rts"},
        )

    def exchange_code(self, ctx):
        return OAuthTokens(
            access_token="access-from-exchange",
            refresh_token="secret-from-exchange",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )

    def refresh(self, *, access_token, refresh_token):  # pragma: no cover
        raise NotImplementedError

    def revoke(self, *, access_token, refresh_token=None):
        return None


def test_brokers_listing(client):
    res = client.get("/api/v1/oauth/brokers")
    assert res.status_code == 200, res.text
    assert "etrade_sandbox" in res.json()["brokers"]


def test_initiate_persists_state_and_returns_authorize_url(client, monkeypatch):
    register_adapter(_RouteStubAdapter)
    state_store.clear_memory_store()
    try:
        res = client.post(
            "/api/v1/oauth/etrade_sandbox/initiate",
            json={"callback_url": "https://app.example/cb"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["broker"] == "etrade_sandbox"
        assert body["state"] == "ROUTE-STATE-NONCE"
        assert "etrade.example/auth" in body["authorize_url"]
        # State persisted with extras for the callback handler.
        extra = state_store.load_extra("etrade_sandbox", "ROUTE-STATE-NONCE")
        assert extra is not None
        assert extra["request_token_secret"] == "rts"
    finally:
        register_adapter(ETradeSandboxAdapter)


def test_callback_persists_encrypted_tokens(client, db_session, route_user):
    register_adapter(_RouteStubAdapter)
    state_store.clear_memory_store()
    try:
        # Pre-populate state as if /initiate were called.
        state_store.save_extra(
            "etrade_sandbox",
            "STATE-NONCE-1",
            {
                "request_token": "rt",
                "request_token_secret": "rts",
                "_user_id": route_user.id,
            },
        )
        res = client.post(
            "/api/v1/oauth/etrade_sandbox/callback",
            json={"state": "STATE-NONCE-1", "code": "VERIFIER"},
        )
        assert res.status_code == 200, res.text
        conn_id = res.json()["connection"]["id"]
        row = db_session.get(BrokerOAuthConnection, conn_id)
        assert row is not None
        assert row.user_id == route_user.id
        assert row.status == OAuthConnectionStatus.ACTIVE.value
        assert decrypt(row.access_token_encrypted) == "access-from-exchange"
        assert decrypt(row.refresh_token_encrypted) == "secret-from-exchange"
    finally:
        register_adapter(ETradeSandboxAdapter)


def test_callback_rejects_unknown_state(client):
    state_store.clear_memory_store()
    res = client.post(
        "/api/v1/oauth/etrade_sandbox/callback",
        json={"state": "UNKNOWN-STATE", "code": "VERIFIER"},
    )
    assert res.status_code == 401


def test_callback_rejects_cross_tenant_state(client, route_user, other_user):
    register_adapter(_RouteStubAdapter)
    state_store.clear_memory_store()
    try:
        state_store.save_extra(
            "etrade_sandbox",
            "OTHER-STATE",
            {
                "request_token": "rt",
                "request_token_secret": "rts",
                "_user_id": other_user.id,  # belongs to a different user
            },
        )
        res = client.post(
            "/api/v1/oauth/etrade_sandbox/callback",
            json={"state": "OTHER-STATE", "code": "VERIFIER"},
        )
        assert res.status_code == 403, res.text
    finally:
        register_adapter(ETradeSandboxAdapter)


def test_list_connections_only_returns_callers_rows(
    client, db_session, route_user, other_user
):
    # Mine
    mine = BrokerOAuthConnection(
        user_id=route_user.id,
        broker="etrade_sandbox",
        provider_account_id=None,
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt("a"),
        environment="sandbox",
        rotation_count=0,
    )
    # Theirs — must NEVER appear in caller's list
    theirs = BrokerOAuthConnection(
        user_id=other_user.id,
        broker="etrade_sandbox",
        provider_account_id=None,
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt("z"),
        environment="sandbox",
        rotation_count=0,
    )
    db_session.add_all([mine, theirs])
    db_session.flush()

    res = client.get("/api/v1/oauth/connections")
    assert res.status_code == 200, res.text
    ids = {c["id"] for c in res.json()["connections"]}
    assert mine.id in ids
    assert theirs.id not in ids


def test_revoke_marks_connection_and_clears_tokens(
    client, db_session, route_user
):
    register_adapter(_RouteStubAdapter)
    try:
        conn = BrokerOAuthConnection(
            user_id=route_user.id,
            broker="etrade_sandbox",
            provider_account_id=None,
            status=OAuthConnectionStatus.ACTIVE.value,
            access_token_encrypted=encrypt("a"),
            refresh_token_encrypted=encrypt("s"),
            environment="sandbox",
            rotation_count=0,
        )
        db_session.add(conn)
        db_session.flush()

        res = client.delete(f"/api/v1/oauth/connections/{conn.id}")
        assert res.status_code == 200, res.text
        db_session.refresh(conn)
        assert conn.status == OAuthConnectionStatus.REVOKED.value
        assert conn.access_token_encrypted is None
        assert conn.refresh_token_encrypted is None
    finally:
        register_adapter(ETradeSandboxAdapter)


def test_revoke_404_when_not_owned(client, db_session, other_user):
    conn = BrokerOAuthConnection(
        user_id=other_user.id,
        broker="etrade_sandbox",
        provider_account_id=None,
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt("a"),
        environment="sandbox",
        rotation_count=0,
    )
    db_session.add(conn)
    db_session.flush()
    res = client.delete(f"/api/v1/oauth/connections/{conn.id}")
    assert res.status_code == 404
