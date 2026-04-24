"""Integration tests for :class:`TradierExecutor`.

Scope:

* Preview / place / cancel / status happy paths against the 4 Tradier
  REST endpoints mocked with the ``responses`` library.
* ``broker_order_id`` populated from Tradier's ``order.id``.
* 4xx error surface — permanent provider errors surface on
  ``OrderResult.error`` / ``PreviewResult.error``, never as silent empty
  success.
* Token refresh — a connection whose ``access_token`` has already expired
  drives ``ensure_broker_token`` through a real refresh stub. The
  subsequent Tradier request must carry the *new* bearer token.

These tests never hit the network (``responses`` intercepts at the
``requests`` adapter layer) and never hit Postgres (the executor's
``session_factory`` is injected with a stub that returns pre-built ORM
objects). They are safe to run standalone with ``pytest -q`` — no
database fixture required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import responses
from responses import matchers

from app.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from app.models.order import Order
from app.services.execution.broker_base import (
    ActionSide,
    IBOrderType,
    OrderRequest,
)
from app.services.execution.tradier_executor import TradierExecutor

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

SANDBOX_BASE = "https://sandbox.tradier.com"
ACCOUNT_ID = "VA12345678"
BROKER_ORDER_ID = "987654321"


def _make_connection(
    *,
    access_token_plaintext: str = "old-access-token",
    status: str = OAuthConnectionStatus.ACTIVE.value,
    token_expires_at: datetime | None = None,
    broker_slug: str = "tradier_sandbox",
    provider_account_id: str = ACCOUNT_ID,
    id_: int = 42,
) -> BrokerOAuthConnection:
    """Build an in-memory ``BrokerOAuthConnection`` without touching the DB.

    The "ciphertext" here is just the plaintext prefixed so the patched
    ``decrypt`` can recover it deterministically — no Fernet key required.
    """

    if token_expires_at is None:
        token_expires_at = datetime.now(UTC) + timedelta(hours=12)

    conn = BrokerOAuthConnection()
    conn.id = id_
    conn.user_id = 7
    conn.broker = broker_slug
    conn.provider_account_id = provider_account_id
    conn.status = status
    conn.access_token_encrypted = f"CIPHER::{access_token_plaintext}"
    conn.refresh_token_encrypted = "CIPHER::refresh-token-x"
    conn.token_expires_at = token_expires_at
    conn.environment = "sandbox"
    conn.rotation_count = 0
    return conn


def _make_order_row(
    *,
    broker_order_id: str = BROKER_ORDER_ID,
    broker_type: str = "tradier_sandbox",
    account_id: str = ACCOUNT_ID,
) -> Order:
    order = Order()
    order.id = 1
    order.symbol = "AAPL"
    order.side = "buy"
    order.order_type = "market"
    order.quantity = 10
    order.status = "submitted"
    order.broker_order_id = broker_order_id
    order.broker_type = broker_type
    order.account_id = account_id
    order.user_id = 7
    order.created_at = datetime.now(UTC)
    return order


class _StubSession:
    """MagicMock-style Session that satisfies the executor's query shape.

    The executor calls two query chains:

    1. ``db.query(BrokerOAuthConnection).filter(...).order_by(...).first()``
       to load the connection by ``(broker, provider_account_id)``.
    2. ``db.query(Order).filter(...).order_by(...).first()`` to look up the
       persisted order by ``(broker_order_id, broker_type)``.

    We stash pre-built objects keyed by model class and return them
    regardless of filter shape — the tests assert higher-level behavior
    (HTTP called / token used) rather than specific SQL expressions.
    """

    def __init__(
        self,
        *,
        connection: BrokerOAuthConnection | None = None,
        order: Order | None = None,
    ) -> None:
        self._by_class: dict[Any, Any] = {}
        if connection is not None:
            self._by_class[BrokerOAuthConnection] = connection
        if order is not None:
            self._by_class[Order] = order
        self.commits: int = 0
        self.closed: bool = False

    def query(self, model: Any) -> _StubQuery:
        return _StubQuery(self._by_class.get(model))

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closed = True


class _StubQuery:
    def __init__(self, result: Any) -> None:
        self._result = result

    def filter(self, *args: Any, **kwargs: Any) -> _StubQuery:
        return self

    def order_by(self, *args: Any, **kwargs: Any) -> _StubQuery:
        return self

    def first(self) -> Any:
        return self._result

    def all(self) -> list[Any]:
        return [self._result] if self._result is not None else []


def _decrypt_stub(ciphertext: str) -> str:
    """Reverse the ``CIPHER::`` prefix used by ``_make_connection``."""

    if ciphertext is None:
        raise ValueError("cannot decrypt None")
    if ciphertext.startswith("CIPHER::"):
        return ciphertext[len("CIPHER::") :]
    raise ValueError(f"unexpected ciphertext: {ciphertext!r}")


@pytest.fixture
def patched_decrypt():
    """Patch the executor's ``decrypt`` to decode our test prefix."""

    with patch(
        "app.services.execution.tradier_executor.decrypt",
        side_effect=_decrypt_stub,
    ) as m:
        yield m


@pytest.fixture
def noop_ensure_token():
    """Patch ``ensure_broker_token`` to a no-op (happy-path tests)."""

    with patch(
        "app.services.execution.tradier_executor.ensure_broker_token",
        return_value=None,
    ) as m:
        yield m


# ---------------------------------------------------------------------------
# Happy paths (preview / place / cancel / status)
# ---------------------------------------------------------------------------


class TestPreviewOrder:
    @responses.activate
    def test_preview_happy_path(self, patched_decrypt, noop_ensure_token):
        conn = _make_connection()
        session = _StubSession(connection=conn)
        executor = TradierExecutor(
            environment="sandbox",
            session_factory=lambda: session,
        )

        responses.add(
            responses.POST,
            f"{SANDBOX_BASE}/v1/accounts/{ACCOUNT_ID}/orders",
            json={
                "order": {
                    "status": "ok",
                    "commission": 0.35,
                    "cost": 2635.90,
                    "margin_change": 2635.90,
                    "result": True,
                    "preview": True,
                }
            },
            status=200,
            match=[
                matchers.header_matcher({"Authorization": "Bearer old-access-token"}),
                matchers.urlencoded_params_matcher(
                    {
                        "class": "equity",
                        "symbol": "AAPL",
                        "side": "buy",
                        "quantity": "10",
                        "type": "market",
                        "duration": "day",
                        "preview": "true",
                    }
                ),
            ],
        )

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.MKT,
            quantity=10,
            account_id=ACCOUNT_ID,
        )

        import asyncio

        result = asyncio.run(executor.preview_order(req))

        assert result.error is None, result.error
        assert result.estimated_commission == pytest.approx(0.35)
        assert result.estimated_margin_impact == pytest.approx(2635.90)
        assert result.raw["broker"] == "tradier_sandbox"
        noop_ensure_token.assert_called_once()


class TestPlaceOrder:
    @responses.activate
    def test_place_happy_path_populates_broker_order_id(self, patched_decrypt, noop_ensure_token):
        conn = _make_connection()
        session = _StubSession(connection=conn)
        executor = TradierExecutor(
            environment="sandbox",
            session_factory=lambda: session,
        )

        responses.add(
            responses.POST,
            f"{SANDBOX_BASE}/v1/accounts/{ACCOUNT_ID}/orders",
            json={
                "order": {
                    "id": 987654321,
                    "status": "ok",
                    "partner_id": "c4998eb7-06e8-4820-a7ab-55d9760065b5",
                }
            },
            status=200,
        )

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.MKT,
            quantity=10,
            account_id=ACCOUNT_ID,
        )

        import asyncio

        result = asyncio.run(executor.place_order(req))

        assert result.error is None, result.error
        assert result.status == "submitted"
        # Tradier returns a numeric id — the executor MUST stringify it
        # so the OrderRequest.broker_order_id column (String) stays
        # type-consistent downstream.
        assert result.broker_order_id == "987654321"
        assert result.raw["broker"] == "tradier_sandbox"

    @responses.activate
    def test_place_with_limit_price_sends_price_param(self, patched_decrypt, noop_ensure_token):
        conn = _make_connection()
        session = _StubSession(connection=conn)
        executor = TradierExecutor(
            environment="sandbox",
            session_factory=lambda: session,
        )

        responses.add(
            responses.POST,
            f"{SANDBOX_BASE}/v1/accounts/{ACCOUNT_ID}/orders",
            json={"order": {"id": 111, "status": "ok"}},
            status=200,
            match=[
                matchers.urlencoded_params_matcher(
                    {
                        "class": "equity",
                        "symbol": "AAPL",
                        "side": "buy",
                        "quantity": "5",
                        "type": "limit",
                        "duration": "day",
                        "price": "180.5",
                    }
                ),
            ],
        )

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.LMT,
            quantity=5,
            limit_price=180.5,
            account_id=ACCOUNT_ID,
        )

        import asyncio

        result = asyncio.run(executor.place_order(req))
        assert result.error is None, result.error
        assert result.broker_order_id == "111"


class TestCancelOrder:
    @responses.activate
    def test_cancel_happy_path(self, patched_decrypt, noop_ensure_token):
        conn = _make_connection()
        order = _make_order_row()
        session = _StubSession(connection=conn, order=order)
        executor = TradierExecutor(
            environment="sandbox",
            session_factory=lambda: session,
        )

        responses.add(
            responses.DELETE,
            f"{SANDBOX_BASE}/v1/accounts/{ACCOUNT_ID}/orders/{BROKER_ORDER_ID}",
            json={"order": {"id": int(BROKER_ORDER_ID), "status": "ok"}},
            status=200,
        )

        import asyncio

        result = asyncio.run(executor.cancel_order(BROKER_ORDER_ID))

        assert result.error is None, result.error
        assert result.status == "cancelled"
        assert result.broker_order_id == BROKER_ORDER_ID


class TestGetOrderStatus:
    @responses.activate
    def test_status_happy_path(self, patched_decrypt, noop_ensure_token):
        conn = _make_connection()
        order = _make_order_row()
        session = _StubSession(connection=conn, order=order)
        executor = TradierExecutor(
            environment="sandbox",
            session_factory=lambda: session,
        )

        responses.add(
            responses.GET,
            f"{SANDBOX_BASE}/v1/accounts/{ACCOUNT_ID}/orders/{BROKER_ORDER_ID}",
            json={
                "order": {
                    "id": int(BROKER_ORDER_ID),
                    "status": "filled",
                    "symbol": "AAPL",
                    "side": "buy",
                    "quantity": 10,
                    "type": "market",
                    "exec_quantity": 10,
                    "avg_fill_price": 150.25,
                }
            },
            status=200,
        )

        import asyncio

        result = asyncio.run(executor.get_order_status(BROKER_ORDER_ID))

        assert result.error is None, result.error
        assert result.status == "filled"
        assert result.filled_quantity == pytest.approx(10.0)
        assert result.avg_fill_price == pytest.approx(150.25)
        assert result.broker_order_id == BROKER_ORDER_ID


# ---------------------------------------------------------------------------
# Error surface (no silent fallbacks)
# ---------------------------------------------------------------------------


class TestErrorSurface:
    @responses.activate
    def test_4xx_surfaces_via_order_result_error(self, patched_decrypt, noop_ensure_token):
        """Permanent provider errors never masquerade as silent success.

        Tradier returns 400 with an error body for bad orders (e.g.
        insufficient buying power). The executor MUST convert this into
        an ``OrderResult(error=...)`` with the provider message — never
        return ``OrderResult()`` with ``status="submitted"`` and no id.
        """

        conn = _make_connection()
        session = _StubSession(connection=conn)
        executor = TradierExecutor(
            environment="sandbox",
            session_factory=lambda: session,
        )

        responses.add(
            responses.POST,
            f"{SANDBOX_BASE}/v1/accounts/{ACCOUNT_ID}/orders",
            json={"errors": {"error": ["insufficient buying power"]}},
            status=400,
        )

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.MKT,
            quantity=10000,
            account_id=ACCOUNT_ID,
        )

        import asyncio

        result = asyncio.run(executor.place_order(req))

        assert result.error is not None
        assert "400" in result.error or "insufficient" in result.error.lower()
        assert result.status == "error"
        assert result.broker_order_id is None

    @responses.activate
    def test_preview_rejection_in_200_body_surfaces_as_error(
        self, patched_decrypt, noop_ensure_token
    ):
        """Tradier sometimes returns HTTP 200 with status != "ok".

        This is the sneakiest failure mode — HTTP green, provider red.
        The executor must NOT report ``PreviewResult.ok`` in that case
        (which would pass ``no_silent_fallback.mdc`` review by accident).
        """

        conn = _make_connection()
        session = _StubSession(connection=conn)
        executor = TradierExecutor(
            environment="sandbox",
            session_factory=lambda: session,
        )

        responses.add(
            responses.POST,
            f"{SANDBOX_BASE}/v1/accounts/{ACCOUNT_ID}/orders",
            json={
                "order": {
                    "status": "rejected",
                    "message": "symbol not found",
                }
            },
            status=200,
        )

        req = OrderRequest(
            symbol="FAKE",
            side=ActionSide.BUY,
            order_type=IBOrderType.MKT,
            quantity=1,
            account_id=ACCOUNT_ID,
        )

        import asyncio

        result = asyncio.run(executor.preview_order(req))
        assert result.ok is False
        assert "symbol not found" in (result.error or "")

    def test_missing_account_id_refuses(self, patched_decrypt, noop_ensure_token):
        """``req.account_id`` is required to resolve the OAuth connection."""

        session = _StubSession(connection=None)
        executor = TradierExecutor(
            environment="sandbox",
            session_factory=lambda: session,
        )

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.MKT,
            quantity=1,
            account_id=None,
        )

        import asyncio

        result = asyncio.run(executor.place_order(req))
        assert result.error is not None
        assert "account_id" in result.error


# ---------------------------------------------------------------------------
# Token refresh — exercises ``ensure_broker_token`` end-to-end
# ---------------------------------------------------------------------------


class TestTokenRefresh:
    """When the stored access token is stale ``ensure_broker_token`` refreshes it.

    This test exercises the real ``ensure_broker_token`` code path. We
    stub only the Redis lock (fakeredis-style in-process dict) and the
    downstream ``_refresh_one`` helper; the executor's own flow is
    unmodified. The assertion that matters: the Tradier request carries
    the *new* bearer token, proving the executor decrypts the
    post-refresh ciphertext rather than a stale local copy.
    """

    @responses.activate
    def test_expired_token_is_refreshed_before_place(self, patched_decrypt):
        # Start with an already-expired token. ``_needs_refresh`` returns
        # True because ``token_expires_at`` is in the past.
        conn = _make_connection(
            access_token_plaintext="old-access-token",
            token_expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session = _StubSession(connection=conn)

        # Fake Redis: ``set`` always returns True (acquired), ``delete``
        # is a no-op. This mimics a healthy lock path.
        fake_redis = MagicMock()
        fake_redis.set.return_value = True
        fake_redis.delete.return_value = 1

        # Stubbed refresh: rotate the ciphertext to a new-plaintext and
        # push the expiry forward. Matches the real ``_refresh_one``
        # contract in ``app.tasks.portfolio.oauth_token_refresh``.
        def fake_refresh_one(db, conn_):
            conn_.access_token_encrypted = "CIPHER::new-access-token"
            conn_.token_expires_at = datetime.now(UTC) + timedelta(hours=12)
            conn_.status = OAuthConnectionStatus.ACTIVE.value
            conn_.rotation_count = (conn_.rotation_count or 0) + 1
            return "written"

        # Tradier place endpoint — the Authorization header MUST carry
        # the NEW access token. If the executor decrypts the pre-refresh
        # ciphertext we'll see ``Bearer old-access-token`` and the
        # matcher will fail.
        responses.add(
            responses.POST,
            f"{SANDBOX_BASE}/v1/accounts/{ACCOUNT_ID}/orders",
            json={"order": {"id": 555, "status": "ok"}},
            status=200,
            match=[
                matchers.header_matcher({"Authorization": "Bearer new-access-token"}),
            ],
        )

        executor = TradierExecutor(
            environment="sandbox",
            session_factory=lambda: session,
        )

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.MKT,
            quantity=3,
            account_id=ACCOUNT_ID,
        )

        # Patch only the two integration points the mixin reaches out
        # to: the Redis client (for the lock) and ``_refresh_one`` (for
        # the actual refresh). Everything else in the mixin runs as-is.
        with (
            patch("app.services.market.market_data_service.infra") as mock_infra,
            patch(
                "app.tasks.portfolio.oauth_token_refresh._refresh_one",
                side_effect=fake_refresh_one,
            ) as mock_refresh_one,
        ):
            mock_infra.redis_client = fake_redis

            import asyncio

            result = asyncio.run(executor.place_order(req))

        assert result.error is None, result.error
        assert result.broker_order_id == "555"
        # The mixin reached for the refresh under the lock.
        mock_refresh_one.assert_called_once()
        # Rotation count was bumped — the refresh actually ran.
        assert conn.rotation_count == 1
        # The session observed a commit (the mixin commits after refresh).
        assert session.commits >= 1
