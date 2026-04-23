"""Wave F Phase 2 — E*TRADE live executor tests.

Coverage:

* 2-step preview → place happy path (the preview ``previewId`` is echoed
  into the place request).
* Cancel happy path.
* Status happy path with filled-quantity / average-price extraction.
* ``ETRADE_ALLOW_LIVE=False`` blocks prod registration in
  ``create_default_router`` (``router.get("etrade")`` raises).
* ``ETRADE_ALLOW_LIVE=True`` allows prod registration.
* Constructing an ``ETradeExecutor(environment="prod")`` with the flag off
  raises ``RuntimeError`` at import time (fail-early per the safety contract).
* Token refresh is exercised via the F0 mixin; a failure surfaces as
  ``OrderResult.error`` (no silent fallback).

We never hit the real E*TRADE sandbox. ``responses`` mocks the HTTP layer
and a fake ``BrokerOAuthConnection`` / ``ensure_broker_token`` stand in for
the DB + token-refresh plumbing (wire-up lands with the OrderManager
integration in a later wave).
"""

from __future__ import annotations

import os

# Ensure the encryption keys are configured before any module imports
# backend.config / backend.services.oauth.encryption transitively.
os.environ.setdefault("OAUTH_TOKEN_ENCRYPTION_KEY", "")
os.environ.setdefault("ENCRYPTION_KEY", "")
os.environ.setdefault("ETRADE_SANDBOX_KEY", "dummy-key")
os.environ.setdefault("ETRADE_SANDBOX_SECRET", "dummy-secret")

import importlib
import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
import responses

from backend.services.execution.broker_base import OrderRequest
from backend.services.execution import etrade_executor as etrade_executor_mod
from backend.services.execution.etrade_executor import ETradeExecutor
from backend.services.execution import oauth_executor_mixin
from backend.services.execution.oauth_executor_mixin import TokenRefreshError

# All executor-level tests are pure unit tests; no DB required. The
# ``asyncio`` mark is applied per-class / per-test (not globally) so plain
# sync tests don't trigger the pytest-asyncio "marked but not async" warning.
pytestmark = [pytest.mark.no_db]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeConn:
    """Minimal stand-in for BrokerOAuthConnection.

    The executor only touches ``id``, ``access_token_encrypted``, and
    ``refresh_token_encrypted`` — and decrypt() is monkeypatched to
    identity so the ciphertext columns can hold plaintext test values.
    """

    def __init__(
        self,
        *,
        conn_id: int = 1,
        access_token: str = "access-tok",
        token_secret: str = "tok-secret",
    ) -> None:
        self.id = conn_id
        self.access_token_encrypted = access_token
        self.refresh_token_encrypted = token_secret


@pytest.fixture(autouse=True)
def _identity_decrypt(monkeypatch):
    """Skip real Fernet decryption in unit tests."""
    monkeypatch.setattr(
        etrade_executor_mod,
        "decrypt",
        lambda s: s,
    )
    yield


@pytest.fixture(autouse=True)
def _no_token_refresh(monkeypatch):
    """Default: ensure_broker_token is a no-op unless a test overrides it."""
    monkeypatch.setattr(
        etrade_executor_mod,
        "ensure_broker_token",
        lambda db, conn, **kwargs: conn,
    )
    yield


@pytest.fixture
def fake_conn() -> _FakeConn:
    return _FakeConn()


@pytest.fixture
def executor(fake_conn) -> ETradeExecutor:
    """Sandbox executor with a canned resolver returning our fake conn."""

    def _resolve(req: OrderRequest):
        return MagicMock(name="db_session"), fake_conn, "ACCT-KEY-X"

    return ETradeExecutor(
        environment="sandbox",
        consumer_key="ck",
        consumer_secret="cs",
        connection_resolver=_resolve,
    )


def _preview_body(preview_id: int = 987654321) -> Dict[str, Any]:
    return {
        "PreviewOrderResponse": {
            "PreviewIds": [{"previewId": preview_id}],
            "Order": [{}],
        }
    }


def _place_body(order_id: int = 123456789, preview_id: int = 987654321) -> Dict[str, Any]:
    return {
        "PlaceOrderResponse": {
            "OrderIds": [{"orderId": order_id}],
            "PreviewIds": [{"previewId": preview_id}],
            "Order": [{}],
        }
    }


def _status_body(
    order_id: int = 123456789,
    status: str = "OPEN",
    filled_qty: float = 0.0,
    avg_price: float = 0.0,
) -> Dict[str, Any]:
    return {
        "OrdersResponse": {
            "Order": [
                {
                    "orderId": order_id,
                    "OrderDetail": [
                        {
                            "status": status,
                            "filledQuantity": filled_qty,
                            "averageExecutionPrice": avg_price,
                        }
                    ],
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# Construction / safety gate
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_sandbox_ok_without_flag(self, monkeypatch) -> None:
        from backend.config import settings
        monkeypatch.setattr(settings, "ETRADE_ALLOW_LIVE", False, raising=False)
        ex = ETradeExecutor(environment="sandbox", consumer_key="ck", consumer_secret="cs")
        assert ex.broker_name == "etrade_sandbox"
        assert ex.is_paper_trading() is True

    def test_prod_requires_flag(self, monkeypatch) -> None:
        from backend.config import settings
        monkeypatch.setattr(settings, "ETRADE_ALLOW_LIVE", False, raising=False)
        with pytest.raises(RuntimeError) as ei:
            ETradeExecutor(environment="prod", consumer_key="ck", consumer_secret="cs")
        assert "ETRADE_ALLOW_LIVE" in str(ei.value)

    def test_prod_allowed_with_flag(self, monkeypatch) -> None:
        from backend.config import settings
        monkeypatch.setattr(settings, "ETRADE_ALLOW_LIVE", True, raising=False)
        ex = ETradeExecutor(environment="prod", consumer_key="ck", consumer_secret="cs")
        assert ex.broker_name == "etrade"
        assert ex.is_paper_trading() is False

    def test_invalid_environment_rejected(self) -> None:
        with pytest.raises(ValueError):
            ETradeExecutor(environment="staging", consumer_key="ck", consumer_secret="cs")


# ---------------------------------------------------------------------------
# Router registration gate
# ---------------------------------------------------------------------------


class TestRouterRegistrationGate:
    """``create_default_router`` enforces the ETRADE_ALLOW_LIVE gate."""

    def test_flag_false_blocks_prod_registration(self, monkeypatch) -> None:
        from backend.config import settings
        from backend.services.execution import broker_router as br_module

        monkeypatch.setattr(settings, "ETRADE_ALLOW_LIVE", False, raising=False)
        importlib.reload(br_module)
        router = br_module.create_default_router()

        assert "etrade_sandbox" in router.available_brokers
        assert "etrade" not in router.available_brokers
        with pytest.raises(ValueError):
            router.get("etrade")

    def test_flag_true_allows_prod_registration(self, monkeypatch) -> None:
        from backend.config import settings
        from backend.services.execution import broker_router as br_module

        monkeypatch.setattr(settings, "ETRADE_ALLOW_LIVE", True, raising=False)
        importlib.reload(br_module)
        try:
            router = br_module.create_default_router()
            assert "etrade" in router.available_brokers
            assert "etrade_sandbox" in router.available_brokers
            # Resolvable without raising
            ex = router.get("etrade")
            assert ex.broker_name == "etrade"
            assert ex.is_paper_trading() is False
        finally:
            # Restore to False so any subsequent test (or the module-level
            # `broker_router` singleton) observes the safe default.
            monkeypatch.setattr(settings, "ETRADE_ALLOW_LIVE", False, raising=False)
            importlib.reload(br_module)


# ---------------------------------------------------------------------------
# Place (2-step preview → place) happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPlaceOrderTwoStep:
    @responses.activate
    async def test_preview_then_place(self, executor, fake_conn) -> None:
        preview_id = 55555
        order_id = 987

        responses.add(
            responses.POST,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/preview.json",
            json=_preview_body(preview_id=preview_id),
            status=200,
        )
        responses.add(
            responses.POST,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/place.json",
            json=_place_body(order_id=order_id, preview_id=preview_id),
            status=200,
        )

        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=10
        )
        result = await executor.place_order(req)

        assert result.ok, f"expected ok OrderResult, got {result!r}"
        assert result.status == "submitted"
        assert result.broker_order_id == str(order_id)
        assert result.raw["preview_id"] == preview_id
        # Assert both HTTP calls happened in order
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url.endswith("/orders/preview.json")
        assert responses.calls[1].request.url.endswith("/orders/place.json")
        # Authorization headers must be present on both calls
        for call in responses.calls:
            auth = call.request.headers.get("Authorization", "")
            assert auth.startswith("OAuth "), auth
            assert 'oauth_consumer_key="ck"' in auth
            assert 'oauth_signature_method="HMAC-SHA1"' in auth
            assert 'oauth_token="access-tok"' in auth
        # Place request echoes the previewId from step 1
        place_body = json.loads(responses.calls[1].request.body)
        assert place_body["PlaceOrderRequest"]["PreviewIds"] == [
            {"previewId": preview_id}
        ]
        # Client order id is shared across both calls
        preview_req_body = json.loads(responses.calls[0].request.body)
        assert (
            preview_req_body["PreviewOrderRequest"]["clientOrderId"]
            == place_body["PlaceOrderRequest"]["clientOrderId"]
        )


# ---------------------------------------------------------------------------
# Preview-only happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPreviewOrder:
    @responses.activate
    async def test_preview_returns_preview_id(self, executor) -> None:
        responses.add(
            responses.POST,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/preview.json",
            json=_preview_body(preview_id=42),
            status=200,
        )
        req = OrderRequest.from_user_input(
            symbol="MSFT", side="buy", order_type="limit", quantity=5, limit_price=300.0
        )
        preview = await executor.preview_order(req)
        assert preview.ok
        assert preview.raw["preview_id"] == 42
        assert len(responses.calls) == 1


# ---------------------------------------------------------------------------
# Cancel happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCancelOrder:
    @responses.activate
    async def test_cancel_ok(self, executor) -> None:
        responses.add(
            responses.PUT,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/cancel.json",
            json={"CancelOrderResponse": {"orderId": 789, "cancelTime": 1}},
            status=200,
        )
        result = await executor.cancel_order("789")
        assert result.ok
        assert result.status == "cancelled"
        assert result.broker_order_id == "789"
        body = json.loads(responses.calls[0].request.body)
        assert body["CancelOrderRequest"]["orderId"] == 789

    async def test_cancel_missing_id_errors(self, executor) -> None:
        result = await executor.cancel_order("")
        assert not result.ok
        assert "broker_order_id" in (result.error or "")


# ---------------------------------------------------------------------------
# Status happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetOrderStatus:
    @responses.activate
    async def test_status_returns_fill_fields(self, executor) -> None:
        responses.add(
            responses.GET,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/789.json",
            json=_status_body(
                order_id=789, status="EXECUTED", filled_qty=10, avg_price=150.25
            ),
            status=200,
        )
        result = await executor.get_order_status("789")
        assert result.ok
        assert result.status == "EXECUTED"
        assert result.filled_quantity == 10.0
        assert result.avg_fill_price == 150.25


# ---------------------------------------------------------------------------
# Token refresh — F0 mixin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTokenRefresh:
    @responses.activate
    async def test_ensure_broker_token_invoked_before_http(
        self, monkeypatch, fake_conn
    ) -> None:
        """Flow a preview → place order and assert ensure_broker_token fires
        **before** the first HTTP call on every write path."""

        calls: list[tuple[str, int]] = []

        def _fake_ensure(db, conn, **kwargs):
            calls.append(("ensure", conn.id))
            return conn

        monkeypatch.setattr(etrade_executor_mod, "ensure_broker_token", _fake_ensure)
        responses.add(
            responses.POST,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/preview.json",
            json=_preview_body(),
            status=200,
        )
        responses.add(
            responses.POST,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/place.json",
            json=_place_body(order_id=5),
            status=200,
        )
        responses.add(
            responses.PUT,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/cancel.json",
            json={"CancelOrderResponse": {"orderId": 5}},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/5.json",
            json=_status_body(order_id=5, status="OPEN"),
            status=200,
        )

        def _resolve(req):
            return MagicMock(name="db"), fake_conn, "ACCT-KEY-X"

        ex = ETradeExecutor(
            environment="sandbox",
            consumer_key="ck",
            consumer_secret="cs",
            connection_resolver=_resolve,
        )
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=1
        )
        placed = await ex.place_order(req)
        assert placed.ok
        cancelled = await ex.cancel_order(placed.broker_order_id)
        assert cancelled.ok
        status = await ex.get_order_status(placed.broker_order_id)
        assert status.ok

        # place_order wraps the 2-step preview→place under a single
        # ensure_broker_token call (one refresh serves both HTTP hops);
        # cancel_order and get_order_status each add one more.
        assert calls == [
            ("ensure", fake_conn.id),  # place_order
            ("ensure", fake_conn.id),  # cancel_order
            ("ensure", fake_conn.id),  # get_order_status
        ]

    async def test_token_refresh_failure_surfaces_as_error(
        self, monkeypatch, fake_conn
    ) -> None:
        def _raise(db, conn, **kwargs):
            raise TokenRefreshError("expired and refresh bounced")

        monkeypatch.setattr(etrade_executor_mod, "ensure_broker_token", _raise)

        def _resolve(req):
            return MagicMock(name="db"), fake_conn, "ACCT-KEY-X"

        ex = ETradeExecutor(
            environment="sandbox",
            consumer_key="ck",
            consumer_secret="cs",
            connection_resolver=_resolve,
        )
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=1
        )
        result = await ex.place_order(req)
        assert not result.ok
        assert "token refresh failed" in (result.error or "")


# ---------------------------------------------------------------------------
# Error paths — no silent fallbacks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrorSurfacing:
    @responses.activate
    async def test_preview_http_500_surfaces_as_error(self, executor) -> None:
        responses.add(
            responses.POST,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/preview.json",
            json={"error": "boom"},
            status=500,
        )
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=1
        )
        preview = await executor.preview_order(req)
        assert not preview.ok
        assert "HTTP 500" in (preview.error or "")

    @responses.activate
    async def test_place_step2_404_surfaces_stage_label(
        self, executor
    ) -> None:
        responses.add(
            responses.POST,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/preview.json",
            json=_preview_body(preview_id=1),
            status=200,
        )
        responses.add(
            responses.POST,
            "https://apisb.etrade.com/v1/accounts/ACCT-KEY-X/orders/place.json",
            json={"error": "not found"},
            status=404,
        )
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=1
        )
        result = await executor.place_order(req)
        assert not result.ok
        assert result.raw.get("stage") == "place"
        assert "HTTP 404" in (result.error or "")

    async def test_missing_resolver_errors_cleanly(self) -> None:
        """A misconfigured executor (no resolver) must not silently succeed."""

        ex = ETradeExecutor(
            environment="sandbox", consumer_key="ck", consumer_secret="cs"
        )
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=1
        )
        result = await ex.place_order(req)
        assert not result.ok
        assert "resolver" in (result.error or "")
