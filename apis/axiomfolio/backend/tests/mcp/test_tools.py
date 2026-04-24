"""End-to-end tests for the MCP transport, auth, and tool catalog.

Exercises the full stack: REST CRUD -> token mint -> bearer-authed
JSON-RPC dispatcher -> per-user tool execution. Critical scenarios:

* Cross-tenant isolation: User B cannot see User A's positions, trades,
  dividends, picks.
* Revoked + expired tokens return 401.
* Caller cannot override ``user_id`` via JSON-RPC arguments.
* JSON-RPC error envelopes are well-formed for the standard error
  codes (-32600/-32601/-32602/-32603).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.mcp.auth import generate_token, hash_token
from backend.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerAccount,
    BrokerType,
)
from backend.models.entitlement import (
    Entitlement,
    EntitlementStatus,
    SubscriptionTier,
)
from backend.models.mcp_token import MCPToken
from backend.models.position import Position, PositionStatus, PositionType
from backend.models.trade import Trade
from backend.models.transaction import Dividend
from backend.models.user import User, UserRole


def _grant_tier(db_session, user: User, tier: SubscriptionTier) -> None:
    """Grant ``user`` an active entitlement at ``tier``.

    Used by MCP tests to exercise scope-gated tools. Without this, users
    default to FREE via auto-creation in ``EntitlementService.get_or_create``
    and only see portfolio-scope tools.
    """
    db_session.add(
        Entitlement(
            user_id=user.id,
            tier=tier,
            status=EntitlementStatus.ACTIVE,
            metadata_json={"source": "test_fixture"},
        )
    )
    db_session.flush()


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def two_users(db_session):
    """Create two distinct users with one broker account each."""
    user_a = User(
        username="mcp_user_a",
        email="mcp_a@example.com",
        full_name="MCP User A",
        role=UserRole.OWNER,
        is_active=True,
        is_approved=True,
        is_verified=True,
        password_hash="x",
    )
    user_b = User(
        username="mcp_user_b",
        email="mcp_b@example.com",
        full_name="MCP User B",
        role=UserRole.OWNER,
        is_active=True,
        is_approved=True,
        is_verified=True,
        password_hash="x",
    )
    db_session.add_all([user_a, user_b])
    db_session.flush()

    acct_a = BrokerAccount(
        user_id=user_a.id,
        broker=BrokerType.IBKR,
        account_number="DU_A_001",
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
    )
    acct_b = BrokerAccount(
        user_id=user_b.id,
        broker=BrokerType.IBKR,
        account_number="DU_B_001",
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
    )
    db_session.add_all([acct_a, acct_b])
    db_session.flush()

    return {
        "user_a": user_a,
        "user_b": user_b,
        "acct_a": acct_a,
        "acct_b": acct_b,
    }


def _mint_token(db_session, user, *, expires_delta: timedelta | None = None) -> str:
    """Insert an active MCP token row, returning the plaintext value."""
    plaintext, h = generate_token()
    expires_at = datetime.now(timezone.utc) + (expires_delta or timedelta(days=30))
    db_session.add(
        MCPToken(
            user_id=user.id,
            name="test-token",
            token_hash=h,
            expires_at=expires_at,
        )
    )
    db_session.flush()
    return plaintext


@pytest.fixture
def client(db_session):
    """TestClient wired to the test ``db_session``.

    We override ``get_db`` so token CRUD and the JSON-RPC transport see
    the same transaction the test fixtures wrote into. ``get_current_user``
    is overridden per-test as needed via :func:`_login_as`.

    Constructed WITHOUT ``with`` so FastAPI startup events (which include
    ``seed_schedules`` running on its own connection outside our test
    transaction) do not fire and pollute other tests.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def _login_as(user):
    """Override ``get_current_user`` to impersonate ``user`` for token CRUD."""
    app.dependency_overrides[get_current_user] = lambda: user


def _logout():
    app.dependency_overrides.pop(get_current_user, None)


def _seed_position(db, user, account, *, symbol: str, qty: str, price: str):
    db.add(
        Position(
            user_id=user.id,
            account_id=account.id,
            symbol=symbol,
            position_type=PositionType.LONG,
            status=PositionStatus.OPEN,
            quantity=Decimal(qty),
            average_cost=Decimal(price),
            current_price=Decimal(price),
            market_value=Decimal(qty) * Decimal(price),
            currency="USD",
        )
    )


def _seed_trade(db, account, *, symbol: str, side: str, qty: str, price: str, days_ago: int = 1):
    db.add(
        Trade(
            account_id=account.id,
            symbol=symbol,
            side=side,
            quantity=Decimal(qty),
            price=Decimal(price),
            total_value=Decimal(qty) * Decimal(price),
            commission=Decimal("0"),
            fees=Decimal("0"),
            execution_time=datetime.now(timezone.utc) - timedelta(days=days_ago),
            order_type="MARKET",
            status="EXECUTED",
            is_opening=True,
        )
    )


def _seed_dividend(db, account, *, symbol: str, gross: float, days_ago: int = 5):
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    shares = 100.0
    db.add(
        Dividend(
            account_id=account.id,
            symbol=symbol,
            ex_date=ts,
            pay_date=ts + timedelta(days=2),
            dividend_per_share=gross / shares,
            shares_held=shares,
            total_dividend=gross,
            tax_withheld=gross * 0.15,
            net_dividend=gross * 0.85,
            currency="USD",
        )
    )


# ----------------------------------------------------------------------
# Token CRUD
# ----------------------------------------------------------------------


class TestTokenCRUD:
    def test_create_returns_plaintext_once(self, client, two_users, db_session):
        _login_as(two_users["user_a"])
        r = client.post(
            "/api/v1/mcp/tokens",
            json={"name": "my-laptop"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["name"] == "my-laptop"
        assert body["is_active"] is True
        token = body["token"]
        assert token.startswith("mcp_axfolio_")
        # Subsequent listing must NEVER include plaintext.
        r2 = client.get("/api/v1/mcp/tokens")
        assert r2.status_code == 200
        rows = r2.json()
        assert len(rows) == 1
        assert "token" not in rows[0]
        assert rows[0]["name"] == "my-laptop"

    def test_revoke_blocks_subsequent_use(self, client, two_users, db_session):
        _login_as(two_users["user_a"])
        token = _mint_token(db_session, two_users["user_a"])
        # Confirm it works
        ok = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert ok.status_code == 200
        # Find the row id and revoke
        listed = client.get("/api/v1/mcp/tokens").json()
        token_id = listed[0]["id"]
        rev = client.delete(f"/api/v1/mcp/tokens/{token_id}")
        assert rev.status_code == 204
        # Now the token is rejected
        bad = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        assert bad.status_code == 401

    def test_revoke_other_users_token_returns_404(self, client, two_users, db_session):
        # User A has a token
        token_a = _mint_token(db_session, two_users["user_a"])
        listed_id = (
            db_session.query(MCPToken)
            .filter(MCPToken.token_hash == hash_token(token_a))
            .one()
            .id
        )
        # User B tries to revoke A's token
        _login_as(two_users["user_b"])
        r = client.delete(f"/api/v1/mcp/tokens/{listed_id}")
        assert r.status_code == 404


# ----------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------


class TestBearerAuth:
    def test_missing_header_is_401(self, client):
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert r.status_code == 401

    def test_bad_prefix_is_401(self, client):
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": "Bearer not_an_mcp_token"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert r.status_code == 401

    def test_unknown_token_is_401(self, client):
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={
                "Authorization": "Bearer mcp_axfolio_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert r.status_code == 401

    def test_expired_token_is_401(self, client, two_users, db_session):
        token = _mint_token(
            db_session, two_users["user_a"], expires_delta=timedelta(seconds=-60)
        )
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert r.status_code == 401

    def test_inactive_user_is_401(self, client, two_users, db_session):
        two_users["user_a"].is_active = False
        db_session.flush()
        token = _mint_token(db_session, two_users["user_a"])
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert r.status_code == 401


# ----------------------------------------------------------------------
# tools/list and JSON-RPC envelope
# ----------------------------------------------------------------------


class TestJSONRPCContract:
    def test_tools_list_returns_catalog(self, client, two_users, db_session):
        # Grant ENTERPRISE so every scope is allowed; asserts the full
        # catalog is reachable for a maximally-entitled user. Per-tier
        # gating behavior is covered by test_tools_list_free_tier_only_portfolio.
        _grant_tier(db_session, two_users["user_a"], SubscriptionTier.ENTERPRISE)
        token = _mint_token(db_session, two_users["user_a"])
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 7, "method": "tools/list"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["jsonrpc"] == "2.0"
        assert body["id"] == 7
        names = {t["name"] for t in body["result"]["tools"]}
        assert {
            "get_holdings",
            "get_recent_trades",
            "get_dividend_summary",
            "get_stage_summary",
            "get_recent_explanations",
            "get_pick_history",
        } <= names

    def test_tools_list_free_tier_only_portfolio(self, client, two_users, db_session):
        """FREE tier must only see portfolio-scoped tools (tier gate)."""
        token = _mint_token(db_session, two_users["user_a"])
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 17, "method": "tools/list"},
        )
        assert r.status_code == 200
        names = {t["name"] for t in r.json()["result"]["tools"]}
        # FREE grants mcp.read_portfolio only.
        assert "get_holdings" in names
        assert "get_recent_trades" in names
        assert "get_dividend_summary" in names
        # Signals / trade_cards / replay must be hidden.
        assert "get_stage_summary" not in names
        assert "get_recent_explanations" not in names
        assert "get_pick_history" not in names

    def test_unknown_method_returns_minus_32601(self, client, two_users, db_session):
        token = _mint_token(db_session, two_users["user_a"])
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 9, "method": "frobnicate"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["error"]["code"] == -32601

    def test_bad_jsonrpc_version_returns_minus_32600(self, client, two_users, db_session):
        token = _mint_token(db_session, two_users["user_a"])
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "1.0", "id": 9, "method": "tools/list"},
        )
        assert r.status_code == 200
        assert r.json()["error"]["code"] == -32600

    def test_caller_cannot_inject_user_id(self, client, two_users, db_session):
        """Defense-in-depth: ``user_id`` is reserved and must be rejected."""
        token = _mint_token(db_session, two_users["user_a"])
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "get_holdings",
                    "arguments": {"user_id": two_users["user_b"].id},
                },
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["error"]["code"] == -32602
        assert "user_id" in body["error"]["message"]

    def test_unknown_arg_rejected(self, client, two_users, db_session):
        token = _mint_token(db_session, two_users["user_a"])
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {
                    "name": "get_holdings",
                    "arguments": {"unknown_arg": 1},
                },
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["error"]["code"] == -32602


# ----------------------------------------------------------------------
# Cross-tenant isolation
# ----------------------------------------------------------------------


class TestCrossTenantIsolation:
    """User B's token must NEVER surface User A's data."""

    def test_holdings_isolated(self, client, two_users, db_session):
        _seed_position(
            db_session, two_users["user_a"], two_users["acct_a"],
            symbol="AAA", qty="10", price="100",
        )
        _seed_position(
            db_session, two_users["user_b"], two_users["acct_b"],
            symbol="BBB", qty="5", price="50",
        )
        db_session.flush()

        token_a = _mint_token(db_session, two_users["user_a"])
        token_b = _mint_token(db_session, two_users["user_b"])

        def _holdings(token: str) -> list[str]:
            r = client.post(
                "/api/v1/mcp/jsonrpc",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "get_holdings", "arguments": {}},
                },
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert "result" in body, body
            return [h["symbol"] for h in body["result"]["content"]["holdings"]]

        a_symbols = _holdings(token_a)
        b_symbols = _holdings(token_b)
        assert a_symbols == ["AAA"]
        assert b_symbols == ["BBB"]

    def test_trades_isolated(self, client, two_users, db_session):
        _seed_trade(db_session, two_users["acct_a"], symbol="AAA", side="BUY", qty="10", price="100")
        _seed_trade(db_session, two_users["acct_b"], symbol="BBB", side="BUY", qty="5", price="50")
        db_session.flush()

        token_a = _mint_token(db_session, two_users["user_a"])
        token_b = _mint_token(db_session, two_users["user_b"])

        def _trade_symbols(token: str) -> set[str]:
            r = client.post(
                "/api/v1/mcp/jsonrpc",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "get_recent_trades", "arguments": {"days": 7}},
                },
            )
            assert r.status_code == 200
            body = r.json()
            assert "result" in body, body
            return {t["symbol"] for t in body["result"]["content"]["trades"]}

        assert _trade_symbols(token_a) == {"AAA"}
        assert _trade_symbols(token_b) == {"BBB"}

    def test_dividends_isolated(self, client, two_users, db_session):
        _seed_dividend(db_session, two_users["acct_a"], symbol="AAA", gross=10.0)
        _seed_dividend(db_session, two_users["acct_b"], symbol="BBB", gross=20.0)
        db_session.flush()

        token_a = _mint_token(db_session, two_users["user_a"])
        token_b = _mint_token(db_session, two_users["user_b"])

        def _div_symbols(token: str) -> set[str]:
            r = client.post(
                "/api/v1/mcp/jsonrpc",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "get_dividend_summary", "arguments": {"days": 30}},
                },
            )
            assert r.status_code == 200
            body = r.json()
            assert "result" in body, body
            return {d["symbol"] for d in body["result"]["content"]["by_symbol"]}

        assert _div_symbols(token_a) == {"AAA"}
        assert _div_symbols(token_b) == {"BBB"}


# ----------------------------------------------------------------------
# Tool argument validation
# ----------------------------------------------------------------------


class TestToolArgValidation:
    def test_negative_days_rejected(self, client, two_users, db_session):
        token = _mint_token(db_session, two_users["user_a"])
        r = client.post(
            "/api/v1/mcp/jsonrpc",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get_recent_trades",
                    "arguments": {"days": -5},
                },
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["error"]["code"] == -32602
