"""Integration tests for SchwabExecutor.

These tests stub the network transport at :meth:`SchwabClient._request_with_meta`
and :meth:`SchwabClient.resolve_account_hash_fresh` so we can assert the
full executor/client flow without hitting Schwab. ``responses`` is not
installed in the test environment (and does not cover ``aiohttp`` anyway),
so we follow the same pattern used by
``backend/tests/services/clients/test_schwab_client.py``: patch the internal
async helpers directly.

Acceptance coverage (per ``docs/plans/WAVE_F_TRADING_PARITY.md`` F3):

* ``preview_order``, ``place_order``, ``cancel_order``, ``get_order_status``
  happy paths.
* ``account_hash`` is resolved from ``account_id`` on every write call -- no
  stale hash reused across re-auth events.
* Token refresh via the F0 ``ensure_broker_token`` mixin runs before every
  write call; failures surface as ``OrderResult.error``.
* 4xx responses from Schwab surface as populated ``OrderResult.error``
  (never a silent fallback).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from backend.services.execution import schwab_executor as schwab_executor_module
from backend.services.execution.broker_base import (
    ActionSide,
    IBOrderType,
    OrderRequest,
)
from backend.services.execution.schwab_executor import SchwabExecutor

# These tests never touch the DB -- OAuth Session and BrokerOAuthConnection
# are both fully mocked. Skip the conftest DB fixtures (which would otherwise
# require a live Postgres).
pytestmark = pytest.mark.no_db


# ---------------------------------------------------------------------------
# Fake SchwabClient
# ---------------------------------------------------------------------------


class FakeSchwabClient:
    """Minimal stand-in for :class:`SchwabClient` used by the executor tests.

    Records every call so tests can assert "one hash lookup per write",
    "place payload matches what the executor built", etc.
    """

    def __init__(
        self,
        *,
        place_response: Optional[Dict[str, Any]] = None,
        cancel_response: Optional[Dict[str, Any]] = None,
        status_response: Optional[Dict[str, Any]] = None,
        preview_response: Optional[Dict[str, Any]] = None,
        resolve_response: Optional[str] = "HASH-ABC",
        connect_ok: bool = True,
    ) -> None:
        self.place_response = place_response or {
            "broker_order_id": "ORDER-123",
            "status": "submitted",
            "http_status": 201,
            "raw": None,
            "error": None,
        }
        self.cancel_response = cancel_response or {
            "status": "cancelled",
            "http_status": 200,
            "raw": {"status": "CANCELED"},
            "error": None,
        }
        self.status_response = status_response or {
            "status": "filled",
            "filled_quantity": 10.0,
            "avg_fill_price": 150.25,
            "http_status": 200,
            "raw": {"status": "FILLED"},
            "error": None,
        }
        self.preview_response = preview_response or {
            "estimated_commission": 0.0,
            "estimated_margin_impact": 1500.0,
            "estimated_equity_with_loan": 50_000.0,
            "http_status": 200,
            "raw": {},
            "error": None,
        }
        self.resolve_response = resolve_response
        self.connect_ok = connect_ok
        self.credentials_seen: List[Tuple[str, str]] = []
        self.resolve_calls: List[str] = []
        self.place_calls: List[Tuple[str, Dict[str, Any]]] = []
        self.cancel_calls: List[Tuple[str, str]] = []
        self.status_calls: List[Tuple[str, str]] = []
        self.preview_calls: List[Tuple[str, Dict[str, Any]]] = []

    async def connect_with_credentials(self, access: str, refresh: str, **_: Any) -> bool:
        self.credentials_seen.append((access, refresh))
        return self.connect_ok

    async def resolve_account_hash_fresh(self, account_number: str) -> Optional[str]:
        self.resolve_calls.append(account_number)
        return self.resolve_response

    async def place_order(self, account_hash: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.place_calls.append((account_hash, payload))
        return self.place_response

    async def cancel_order(self, account_hash: str, order_id: str) -> Dict[str, Any]:
        self.cancel_calls.append((account_hash, order_id))
        return self.cancel_response

    async def get_order_status(self, account_hash: str, order_id: str) -> Dict[str, Any]:
        self.status_calls.append((account_hash, order_id))
        return self.status_response

    async def preview_order(self, account_hash: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.preview_calls.append((account_hash, payload))
        return self.preview_response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_connection() -> MagicMock:
    conn = MagicMock(name="BrokerOAuthConnection")
    conn.id = 42
    conn.provider_account_id = "SCHWAB-ACCT-001"
    conn.access_token_encrypted = "ciphertext-access"
    conn.refresh_token_encrypted = "ciphertext-refresh"
    return conn


@pytest.fixture
def fake_session() -> MagicMock:
    return MagicMock(name="Session")


@pytest.fixture
def context_resolver(fake_session, fake_connection):
    def _resolve():
        return (fake_session, fake_connection)

    return _resolve


@pytest.fixture(autouse=True)
def stub_token_refresh_and_decrypt(monkeypatch):
    """Default autouse stubs so individual tests can override only what matters."""

    def _ok_refresh(db, conn, **_kwargs):
        return conn

    # Stub ensure_broker_token at the executor's import site so every test
    # starts from a "token fresh" state. Individual tests that exercise the
    # refresh failure path override this.
    monkeypatch.setattr(
        schwab_executor_module, "ensure_broker_token", _ok_refresh,
    )
    # Decrypt is a pass-through plain-text mirror in tests; real decryption
    # is exercised by backend/tests/services/oauth.
    monkeypatch.setattr(
        schwab_executor_module, "decrypt", lambda ct: f"plain:{ct}",
    )
    yield


def _build_executor(
    *,
    client: FakeSchwabClient,
    context_resolver,
) -> Tuple[SchwabExecutor, List[FakeSchwabClient]]:
    """Build an executor whose factory records every client it produces.

    The returned ``clients`` list is mutated in-place; callers can assert
    how many fresh clients the executor created (must be one per write call
    so the account-hash lookup is never reused across re-auth events).
    """
    clients: List[FakeSchwabClient] = []

    def _factory():
        # Return the same fake for every call so test assertions on
        # ``resolve_calls`` reflect the full test-run history, while still
        # constructing a logical new session each write.
        clients.append(client)
        return client

    return SchwabExecutor(
        context_resolver=context_resolver,
        client_factory=_factory,
    ), clients


def _buy_market(symbol: str = "AAPL", qty: float = 10) -> OrderRequest:
    return OrderRequest(
        symbol=symbol,
        side=ActionSide.BUY,
        order_type=IBOrderType.MKT,
        quantity=qty,
    )


# ---------------------------------------------------------------------------
# Protocol smoke
# ---------------------------------------------------------------------------


def test_broker_name_and_paper_flag():
    ex = SchwabExecutor()
    assert ex.broker_name == "schwab"
    assert ex.is_paper_trading() is False


def test_registered_in_default_router():
    from backend.services.execution.broker_router import create_default_router

    router = create_default_router()
    executor = router.get("schwab")
    assert isinstance(executor, SchwabExecutor)
    assert executor.broker_name == "schwab"


# ---------------------------------------------------------------------------
# Happy-path: preview / place / cancel / status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_place_order_happy_path(context_resolver):
    client = FakeSchwabClient()
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    result = await ex.place_order(_buy_market("AAPL", 10))

    assert result.error is None, result.error
    assert result.status == "submitted"
    assert result.broker_order_id == "ORDER-123"
    assert result.raw.get("broker") == "schwab"

    # The client must have received the Schwab-shaped payload built by the
    # executor (no hand-constructed dicts leaking in).
    assert len(client.place_calls) == 1
    account_hash, payload = client.place_calls[0]
    assert account_hash == "HASH-ABC"
    assert payload["orderType"] == "MARKET"
    assert payload["orderStrategyType"] == "SINGLE"
    assert payload["orderLegCollection"][0]["instruction"] == "BUY"
    assert payload["orderLegCollection"][0]["quantity"] == 10
    assert payload["orderLegCollection"][0]["instrument"]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_preview_order_happy_path(context_resolver):
    client = FakeSchwabClient()
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    preview = await ex.preview_order(_buy_market("MSFT", 5))

    assert preview.error is None, preview.error
    assert preview.estimated_commission == 0.0
    assert preview.estimated_margin_impact == 1500.0
    assert len(client.preview_calls) == 1
    assert client.preview_calls[0][0] == "HASH-ABC"


@pytest.mark.asyncio
async def test_cancel_order_happy_path(context_resolver):
    client = FakeSchwabClient()
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    result = await ex.cancel_order("ORDER-999")

    assert result.error is None, result.error
    assert result.status == "cancelled"
    assert result.broker_order_id == "ORDER-999"
    assert client.cancel_calls == [("HASH-ABC", "ORDER-999")]


@pytest.mark.asyncio
async def test_get_order_status_polls_and_maps(context_resolver):
    client = FakeSchwabClient()
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    result = await ex.get_order_status("ORDER-999")

    assert result.error is None
    assert result.status == "filled"
    assert result.filled_quantity == 10.0
    assert result.avg_fill_price == 150.25
    # Polled once -- Schwab does not push status updates so every call hits
    # the order endpoint.
    assert client.status_calls == [("HASH-ABC", "ORDER-999")]


# ---------------------------------------------------------------------------
# Account-hash resolution: one lookup per write, no stale caching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_hash_resolved_per_place_call(context_resolver, fake_connection):
    """Each write call must do exactly one fresh account-hash lookup."""
    client = FakeSchwabClient()
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    await ex.place_order(_buy_market("AAPL", 1))
    await ex.place_order(_buy_market("MSFT", 2))
    await ex.cancel_order("ORDER-9")
    await ex.get_order_status("ORDER-9")

    # 4 write calls -> 4 hash resolutions against the sync resolver. None
    # reused between calls (which would let a rotated hash post-reauth
    # be reused).
    assert client.resolve_calls == [
        fake_connection.provider_account_id,
    ] * 4


@pytest.mark.asyncio
async def test_account_hash_rotation_picked_up_on_next_call(context_resolver):
    """A hash that rotates between calls is used on the next call, not cached."""
    client = FakeSchwabClient()
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    # First call: hash "HASH-OLD".
    client.resolve_response = "HASH-OLD"
    r1 = await ex.place_order(_buy_market("AAPL", 1))
    assert r1.error is None
    assert client.place_calls[-1][0] == "HASH-OLD"

    # Provider rotates the hash (simulated re-auth). Next call must pick up
    # the new hash -- never the cached one.
    client.resolve_response = "HASH-NEW"
    r2 = await ex.place_order(_buy_market("MSFT", 1))
    assert r2.error is None
    assert client.place_calls[-1][0] == "HASH-NEW"


@pytest.mark.asyncio
async def test_order_request_account_id_override(context_resolver, fake_connection):
    """``OrderRequest.account_id`` overrides ``connection.provider_account_id``."""
    client = FakeSchwabClient()
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    req = OrderRequest(
        symbol="AAPL",
        side=ActionSide.BUY,
        order_type=IBOrderType.MKT,
        quantity=1,
        account_id="OVERRIDE-9",
    )
    await ex.place_order(req)
    assert client.resolve_calls[-1] == "OVERRIDE-9"


# ---------------------------------------------------------------------------
# Token refresh via mixin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_broker_token_called_before_every_write(
    context_resolver, monkeypatch
):
    calls: List[int] = []

    def _spy(db, conn, **_kwargs):
        calls.append(conn.id)
        return conn

    monkeypatch.setattr(schwab_executor_module, "ensure_broker_token", _spy)

    client = FakeSchwabClient()
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    await ex.place_order(_buy_market())
    await ex.cancel_order("ORDER-1")
    await ex.get_order_status("ORDER-1")
    await ex.preview_order(_buy_market())

    # One token-freshness check per write call -- matches the F0 contract.
    assert calls == [42, 42, 42, 42]


@pytest.mark.asyncio
async def test_token_refresh_failure_surfaces_as_order_error(
    context_resolver, monkeypatch
):
    from backend.services.execution.oauth_executor_mixin import TokenRefreshError

    def _boom(db, conn, **_kwargs):
        raise TokenRefreshError(f"connection {conn.id} is REVOKED")

    monkeypatch.setattr(schwab_executor_module, "ensure_broker_token", _boom)

    client = FakeSchwabClient()
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    result = await ex.place_order(_buy_market())
    assert result.error is not None
    assert "token refresh failed" in result.error
    # Critically: we never reached the Schwab client -- no order leaked out.
    assert client.place_calls == []
    assert client.resolve_calls == []


# ---------------------------------------------------------------------------
# 4xx error surfacing (no silent fallback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_place_order_4xx_surfaces_as_error(context_resolver):
    client = FakeSchwabClient(
        place_response={
            "broker_order_id": None,
            "status": "error",
            "http_status": 400,
            "raw": {"errors": [{"message": "insufficient buying power"}]},
            "error": "HTTP 400: insufficient buying power",
        },
    )
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    result = await ex.place_order(_buy_market("AAPL", 1000))
    assert result.error is not None
    assert "400" in result.error or "buying power" in result.error
    assert result.status == "error"
    assert result.broker_order_id is None


@pytest.mark.asyncio
async def test_cancel_order_4xx_surfaces_as_error(context_resolver):
    client = FakeSchwabClient(
        cancel_response={
            "status": "error",
            "http_status": 422,
            "raw": {"errors": [{"message": "order already filled"}]},
            "error": "HTTP 422: order already filled",
        },
    )
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    result = await ex.cancel_order("ORDER-999")
    assert result.error is not None
    assert "422" in result.error or "already filled" in result.error
    assert result.status == "error"


@pytest.mark.asyncio
async def test_missing_context_resolver_surfaces_as_error():
    """An unbound executor must never silently succeed."""
    ex = SchwabExecutor()  # no resolver

    result = await ex.place_order(_buy_market())
    assert result.error is not None
    assert "not bound" in result.error.lower()


@pytest.mark.asyncio
async def test_unresolvable_account_hash_surfaces_as_error(context_resolver):
    client = FakeSchwabClient(resolve_response=None)
    ex, _ = _build_executor(client=client, context_resolver=context_resolver)

    result = await ex.place_order(_buy_market())
    assert result.error is not None
    assert "account_hash" in result.error
    assert client.place_calls == []


# ---------------------------------------------------------------------------
# Payload construction (defensive -- the client lives in the danger zone of
# the trading stack, so payload-shape regressions must be caught here).
# ---------------------------------------------------------------------------


def test_build_order_payload_market_buy():
    from backend.services.clients.schwab_client import SchwabClient

    payload = SchwabClient.build_order_payload(
        symbol="aapl", side="buy", quantity=10, order_type="MARKET",
    )
    assert payload["orderType"] == "MARKET"
    assert payload["orderLegCollection"][0]["instrument"]["symbol"] == "AAPL"
    assert "price" not in payload
    assert "stopPrice" not in payload


def test_build_order_payload_limit_requires_limit_price():
    from backend.services.clients.schwab_client import SchwabClient

    with pytest.raises(ValueError, match="limit_price"):
        SchwabClient.build_order_payload(
            symbol="AAPL", side="buy", quantity=1, order_type="LIMIT",
        )


def test_build_order_payload_stop_limit_includes_both_prices():
    from backend.services.clients.schwab_client import SchwabClient

    payload = SchwabClient.build_order_payload(
        symbol="AAPL",
        side="sell",
        quantity=5,
        order_type="STOP_LIMIT",
        limit_price=99.0,
        stop_price=100.0,
    )
    assert payload["orderType"] == "STOP_LIMIT"
    assert payload["price"] == 99.0
    assert payload["stopPrice"] == 100.0


def test_build_order_payload_rejects_bogus_side():
    from backend.services.clients.schwab_client import SchwabClient

    with pytest.raises(ValueError, match="side"):
        SchwabClient.build_order_payload(
            symbol="AAPL", side="bogus", quantity=1, order_type="MARKET",
        )


# ---------------------------------------------------------------------------
# Client-level helpers (Location parsing, status mapping)
# ---------------------------------------------------------------------------


def test_extract_order_id_from_location_header():
    from backend.services.clients.schwab_client import SchwabClient

    assert (
        SchwabClient._extract_order_id_from_location(
            "https://api.schwabapi.com/trader/v1/accounts/H/orders/777"
        )
        == "777"
    )
    assert (
        SchwabClient._extract_order_id_from_location(
            "https://api.schwabapi.com/trader/v1/accounts/H/orders/777/"
        )
        == "777"
    )
    assert SchwabClient._extract_order_id_from_location("") is None


@pytest.mark.asyncio
async def test_client_place_order_parses_location_header():
    """End-to-end: client-level place_order parses the Location header."""
    from backend.services.clients.schwab_client import SchwabClient

    client = SchwabClient()
    client.connected = True
    client._access_token = "t"

    async def _mock_request_with_meta(
        method: str,
        path: str,
        *,
        params=None,
        json_body=None,
        expected_statuses=None,
    ) -> Dict[str, Any]:
        assert method == "POST"
        assert path == "/accounts/HASH/orders"
        assert json_body["orderType"] == "MARKET"
        return {
            "status": 201,
            "data": None,
            "headers": {
                "location": "https://api.schwabapi.com/trader/v1/accounts/HASH/orders/555"
            },
            "error": None,
        }

    client._request_with_meta = _mock_request_with_meta  # type: ignore[assignment]
    payload = SchwabClient.build_order_payload(
        symbol="AAPL", side="buy", quantity=1, order_type="MARKET",
    )
    result = await client.place_order("HASH", payload)
    assert result["broker_order_id"] == "555"
    assert result["status"] == "submitted"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_client_place_order_missing_location_surfaces_error():
    from backend.services.clients.schwab_client import SchwabClient

    client = SchwabClient()
    client.connected = True
    client._access_token = "t"

    async def _mock_request_with_meta(method, path, **_kwargs):
        return {"status": 201, "data": {}, "headers": {}, "error": None}

    client._request_with_meta = _mock_request_with_meta  # type: ignore[assignment]
    payload = SchwabClient.build_order_payload(
        symbol="AAPL", side="buy", quantity=1, order_type="MARKET",
    )
    result = await client.place_order("HASH", payload)
    assert result["error"] is not None
    assert result["broker_order_id"] is None


@pytest.mark.asyncio
async def test_client_get_order_status_maps_working():
    from backend.services.clients.schwab_client import SchwabClient

    client = SchwabClient()
    client.connected = True
    client._access_token = "t"

    async def _mock_request_with_meta(method, path, **_kwargs):
        return {
            "status": 200,
            "data": {"status": "WORKING", "filledQuantity": 0},
            "headers": {},
            "error": None,
        }

    client._request_with_meta = _mock_request_with_meta  # type: ignore[assignment]
    result = await client.get_order_status("HASH", "1")
    assert result["status"] == "working"
    assert result["filled_quantity"] == 0.0


@pytest.mark.asyncio
async def test_client_get_order_status_maps_filled_with_avg_price():
    from backend.services.clients.schwab_client import SchwabClient

    client = SchwabClient()
    client.connected = True
    client._access_token = "t"

    async def _mock_request_with_meta(method, path, **_kwargs):
        return {
            "status": 200,
            "data": {
                "status": "FILLED",
                "filledQuantity": 10,
                "orderActivityCollection": [
                    {
                        "executionLegs": [
                            {"quantity": 4, "price": 100.0},
                            {"quantity": 6, "price": 110.0},
                        ]
                    }
                ],
            },
            "headers": {},
            "error": None,
        }

    client._request_with_meta = _mock_request_with_meta  # type: ignore[assignment]
    result = await client.get_order_status("HASH", "1")
    assert result["status"] == "filled"
    assert result["filled_quantity"] == 10.0
    # Weighted avg: (4*100 + 6*110) / 10 = 106.0
    assert result["avg_fill_price"] == pytest.approx(106.0)


@pytest.mark.asyncio
async def test_resolve_account_hash_fresh_pops_cache_before_lookup():
    """Ensure the fresh resolver drops stale entries before hitting the API."""
    from backend.services.clients.schwab_client import SchwabClient

    client = SchwabClient()
    client.connected = True
    client._access_token = "t"
    client._account_hash_map = {"ACCT-1": "HASH-OLD"}

    async def _mock_get_accounts():
        # If the pop didn't happen, _resolve_account_hash would return
        # HASH-OLD from cache without calling this. Returning HASH-NEW here
        # proves the cache was cleared.
        return [{"account_number": "ACCT-1", "hash_value": "HASH-NEW"}]

    client.get_accounts = _mock_get_accounts  # type: ignore[assignment]
    resolved = await client.resolve_account_hash_fresh("ACCT-1")
    assert resolved == "HASH-NEW"
    assert client._account_hash_map.get("ACCT-1") == "HASH-NEW"
