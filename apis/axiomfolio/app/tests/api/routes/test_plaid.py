"""API route tests for :mod:`app.api.routes.plaid`.

Coverage (per plan ``docs/plans/PLAID_FIDELITY_401K.md`` §9):

* Free-tier user hitting any gated route gets HTTP 402 ``tier_required``.
* Pro-tier user exchanging a public_token gets a ``PlaidConnection`` +
  one ``BrokerAccount(connection_source='plaid')`` row, both scoped to
  their ``user_id``.
* Cross-tenant: DELETE of another tenant's connection returns 404.
* Webhook with a bad / missing signature returns 401 and writes nothing.

We stub the Plaid SDK surface by monkeypatching ``PlaidClient`` — no
network calls are issued and no plaintext tokens are needed.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

os.environ.setdefault("OAUTH_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

try:
    from app.api.dependencies import get_current_user, get_optional_user
    from app.api.main import app
    from app.config import settings
    from app.database import get_db
    from app.models.broker_account import BrokerAccount
    from app.models.entitlement import SubscriptionTier
    from app.models.plaid_connection import (
        PlaidConnection,
        PlaidConnectionStatus,
    )
    from app.models.user import User, UserRole
    from app.services.billing.entitlement_service import EntitlementService
    from app.services.portfolio.plaid import client as plaid_client_module
    AVAILABLE = True
except Exception:  # pragma: no cover
    AVAILABLE = False


pytestmark = pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(db_session) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"plaid_route_{suffix}@example.com",
        username=f"plaid_route_{suffix}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _upgrade_to_pro(db_session, user: User) -> None:
    EntitlementService.manual_set_tier(
        db_session,
        user=user,
        new_tier=SubscriptionTier.PRO,
        actor="test",
    )
    db_session.commit()


class _FakePlaidClient:
    """Stand-in for :class:`PlaidClient` used in route tests.

    Implements only the methods exercised by the route code. The
    ``_api`` attribute is ``None`` on purpose — the webhook tests
    exercise paths that fail before the Plaid JWKS lookup, so the
    route never dereferences it. If a test needs to exercise a path
    that does hit ``_api``, override this attribute on the fake.
    """

    environment = "sandbox"
    _api = None

    # intentionally simple; tests can swap attributes if they need to
    link_token_value = "link-sandbox-fake"
    access_token_value = "access-sandbox-fake"
    item_id_value = "item-fake"
    accounts_payload: List[Dict[str, Any]] = [
        {
            "account_id": "acct-1",
            "name": "401(k)",
            "official_name": "Fidelity 401(k)",
            "type": "investment",
            "subtype": "401k",
            "mask": "1234",
            "balances": {"iso_currency_code": "USD"},
        }
    ]

    def create_link_token(self, *, user_id: int, client_name: str = "x") -> str:
        return self.link_token_value

    def exchange_public_token(self, public_token: str):
        assert public_token
        return (self.access_token_value, self.item_id_value)

    @staticmethod
    def encrypt_access_token(plaintext: str) -> str:
        # Tests do not rely on real Fernet roundtrip; return a deterministic
        # non-plaintext marker so assertions can detect plaintext leakage.
        assert plaintext, "plaintext must not be empty"
        return f"ENC::{plaintext[-4:]}"

    @staticmethod
    def decrypt_access_token(ct: str) -> str:
        return "plaintext"

    def get_accounts(self, access_token_ct: str) -> List[Dict[str, Any]]:
        assert access_token_ct.startswith("ENC::")
        return self.accounts_payload

    def remove_item(self, access_token_ct: str) -> None:
        return None

    def close(self) -> None:
        return None


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


@pytest.fixture
def _wire_overrides(db_session, route_user):
    if db_session is None:
        pytest.skip("database not configured")

    def _get_db():
        yield db_session

    def _get_user():
        return route_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    app.dependency_overrides[get_optional_user] = _get_user
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)


@pytest.fixture
def plaid_env(monkeypatch):
    """Configure Plaid env vars so ``PlaidClient`` does not raise."""
    monkeypatch.setattr(settings, "PLAID_CLIENT_ID", "test-client")
    monkeypatch.setattr(settings, "PLAID_SECRET", "test-secret")
    monkeypatch.setattr(settings, "PLAID_ENV", "sandbox")
    monkeypatch.setattr(settings, "PLAID_PRODUCTS", "investments")
    monkeypatch.setattr(settings, "PLAID_WEBHOOK_URL", "")
    yield


@pytest.fixture
def fake_plaid_client(monkeypatch, plaid_env):
    """Monkeypatch ``PlaidClient`` to the fake for all routes."""
    monkeypatch.setattr(plaid_client_module, "PlaidClient", _FakePlaidClient)
    # ``app.api.routes.plaid`` imports PlaidClient by name at module
    # load time, so monkeypatch both references.
    from app.api.routes import plaid as plaid_routes

    monkeypatch.setattr(plaid_routes, "PlaidClient", _FakePlaidClient)
    yield _FakePlaidClient


# ---------------------------------------------------------------------------
# Free tier gating
# ---------------------------------------------------------------------------


def test_link_token_requires_pro_tier(
    client, db_session, route_user, _wire_overrides, fake_plaid_client
):
    r = client.post("/api/v1/plaid/link_token")
    assert r.status_code == 402, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "tier_required"
    assert detail["feature"] == "broker.plaid_investments"


def test_exchange_requires_pro_tier(
    client, db_session, route_user, _wire_overrides, fake_plaid_client
):
    r = client.post("/api/v1/plaid/exchange", json={"public_token": "pub-x"})
    assert r.status_code == 402, r.text


# ---------------------------------------------------------------------------
# Pro-tier happy path
# ---------------------------------------------------------------------------


def test_link_token_pro_tier_returns_token(
    client, db_session, route_user, _wire_overrides, fake_plaid_client
):
    _upgrade_to_pro(db_session, route_user)
    r = client.post("/api/v1/plaid/link_token")
    assert r.status_code == 200, r.text
    assert r.json()["link_token"] == "link-sandbox-fake"


def test_exchange_creates_connection_and_broker_account(
    client, db_session, route_user, _wire_overrides, fake_plaid_client
):
    _upgrade_to_pro(db_session, route_user)
    r = client.post(
        "/api/v1/plaid/exchange",
        json={
            "public_token": "pub-sandbox-x",
            "metadata": {
                "institution": {"institution_id": "ins_3", "name": "Fidelity"}
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["item_id"] == "item-fake"
    assert body["status"] == PlaidConnectionStatus.ACTIVE.value
    assert len(body["account_ids"]) == 1

    conn = (
        db_session.query(PlaidConnection)
        .filter(PlaidConnection.user_id == route_user.id)
        .one()
    )
    # Plaintext must NEVER land in the stored column.
    assert "access-sandbox" not in conn.access_token_encrypted
    assert conn.access_token_encrypted.startswith("ENC::")

    ba = (
        db_session.query(BrokerAccount)
        .filter(BrokerAccount.user_id == route_user.id)
        .one()
    )
    assert ba.connection_source == "plaid"
    assert ba.account_number == "acct-1"


# ---------------------------------------------------------------------------
# Cross-tenant isolation (DELETE)
# ---------------------------------------------------------------------------


def test_disconnect_cannot_delete_another_tenants_connection(
    client, db_session, route_user, other_user, _wire_overrides, fake_plaid_client
):
    _upgrade_to_pro(db_session, route_user)
    # Connection owned by OTHER user.
    other_conn = PlaidConnection(
        user_id=other_user.id,
        item_id="item-other",
        access_token_encrypted="ENC::oth",
        institution_id="ins_x",
        institution_name="Other Bank",
        environment="sandbox",
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    db_session.add(other_conn)
    db_session.commit()

    r = client.delete(f"/api/v1/plaid/connections/{other_conn.id}")
    assert r.status_code == 404, r.text
    db_session.refresh(other_conn)
    assert other_conn.status == PlaidConnectionStatus.ACTIVE.value


def test_list_connections_does_not_leak_other_tenants(
    client, db_session, route_user, other_user, _wire_overrides, fake_plaid_client
):
    _upgrade_to_pro(db_session, route_user)
    # Own connection.
    own = PlaidConnection(
        user_id=route_user.id,
        item_id="item-own",
        access_token_encrypted="ENC::own",
        institution_id="ins_1",
        institution_name="Own Bank",
        environment="sandbox",
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    other = PlaidConnection(
        user_id=other_user.id,
        item_id="item-other2",
        access_token_encrypted="ENC::oth",
        institution_id="ins_2",
        institution_name="Other Bank",
        environment="sandbox",
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    db_session.add_all([own, other])
    db_session.commit()

    r = client.get("/api/v1/plaid/connections")
    assert r.status_code == 200, r.text
    ids = {row["id"] for row in r.json()["connections"]}
    assert own.id in ids
    assert other.id not in ids


# ---------------------------------------------------------------------------
# Webhook signature enforcement
# ---------------------------------------------------------------------------


def test_webhook_missing_signature_returns_401(
    client, db_session, route_user, _wire_overrides, fake_plaid_client
):
    r = client.post(
        "/api/v1/plaid/webhook",
        json={"webhook_type": "ITEM", "webhook_code": "ERROR"},
    )
    assert r.status_code == 401, r.text
    assert r.json()["detail"].lower().startswith("invalid")


def test_webhook_bad_jwt_returns_401(
    client, db_session, route_user, _wire_overrides, fake_plaid_client
):
    r = client.post(
        "/api/v1/plaid/webhook",
        json={"webhook_type": "ITEM", "webhook_code": "ERROR"},
        headers={"Plaid-Verification": "not-a-real-jwt"},
    )
    assert r.status_code == 401, r.text
