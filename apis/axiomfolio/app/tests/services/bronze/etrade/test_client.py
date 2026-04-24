"""Unit tests for :class:`app.services.bronze.etrade.client.ETradeBronzeClient`.

Covers:
* success-path JSON unwrapping for each of the four endpoints
* 4xx responses raise :class:`ETradeAPIError` with ``permanent=True``
* 5xx responses raise :class:`ETradeAPIError` with ``permanent=False`` (retry-safe)
* network exceptions from the adapter raise ``permanent=False``
* missing or malformed JSON bodies surface as permanent errors

The adapter's signing logic is not re-tested here (it's already covered by
``backend/tests/oauth/test_etrade_adapter.py``); we inject a mock in its place
so these tests run with ``no_db`` semantics and zero network I/O.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from app.services.bronze.etrade.client import (
    ETradeAPIError,
    ETradeBronzeClient,
)

pytestmark = pytest.mark.no_db


class _FakeResponse:
    """Minimal stand-in for :class:`requests.Response`."""

    def __init__(
        self,
        status_code: int,
        json_body: Any = None,
        text: str = "",
        raise_json: bool = False,
    ) -> None:
        self.status_code = status_code
        self._json = json_body
        self.text = text or (str(json_body) if json_body is not None else "")
        self.content = (self.text or "").encode("utf-8")
        self._raise_json = raise_json

    def json(self) -> Any:
        if self._raise_json:
            raise ValueError("not JSON")
        return self._json


def _make_client_with_response(resp: _FakeResponse) -> ETradeBronzeClient:
    adapter = MagicMock()
    adapter._signed_request.return_value = resp
    return ETradeBronzeClient(
        access_token="tok",
        access_token_secret="sec",
        adapter=adapter,
    )


def test_construction_requires_both_secrets() -> None:
    with pytest.raises(ETradeAPIError) as exc:
        ETradeBronzeClient(access_token="", access_token_secret="sec")
    assert exc.value.permanent is True


def test_list_accounts_unwraps_nested_envelope() -> None:
    body: dict[str, Any] = {
        "AccountListResponse": {
            "Accounts": {
                "Account": [
                    {"accountId": "111", "accountIdKey": "abc"},
                    {"accountId": "222", "accountIdKey": "def"},
                ]
            }
        }
    }
    client = _make_client_with_response(_FakeResponse(200, json_body=body))
    accounts = client.list_accounts()
    assert [a["accountId"] for a in accounts] == ["111", "222"]


def test_list_accounts_single_account_object_becomes_list() -> None:
    body = {
        "AccountListResponse": {
            "Accounts": {"Account": {"accountId": "111", "accountIdKey": "abc"}}
        }
    }
    client = _make_client_with_response(_FakeResponse(200, json_body=body))
    assert [a["accountId"] for a in client.list_accounts()] == ["111"]


def test_get_portfolio_flattens_across_multiple_portfolios() -> None:
    body = {
        "PortfolioResponse": {
            "AccountPortfolio": [
                {"Position": [{"Product": {"symbol": "AAPL"}}]},
                {"Position": {"Product": {"symbol": "MSFT"}}},
            ]
        }
    }
    client = _make_client_with_response(_FakeResponse(200, json_body=body))
    positions = client.get_portfolio("KEY")
    assert [p["Product"]["symbol"] for p in positions] == ["AAPL", "MSFT"]


def test_get_balance_returns_inner_envelope() -> None:
    body = {"BalanceResponse": {"Computed": {"cashBalance": 1000.0}}}
    client = _make_client_with_response(_FakeResponse(200, json_body=body))
    bal = client.get_balance("KEY")
    assert bal["Computed"]["cashBalance"] == 1000.0


def test_get_transactions_returns_empty_list_on_missing_envelope() -> None:
    client = _make_client_with_response(_FakeResponse(200, json_body={}))
    assert client.get_transactions("KEY") == []


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429])
def test_4xx_is_permanent(status: int) -> None:
    client = _make_client_with_response(
        _FakeResponse(status, json_body={"error": "nope"}, text='{"error":"nope"}')
    )
    with pytest.raises(ETradeAPIError) as exc:
        client.list_accounts()
    assert exc.value.permanent is True
    assert exc.value.status == status


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_5xx_is_transient(status: int) -> None:
    client = _make_client_with_response(_FakeResponse(status, text="upstream boom"))
    with pytest.raises(ETradeAPIError) as exc:
        client.list_accounts()
    assert exc.value.permanent is False
    assert exc.value.status == status


def test_network_error_is_transient() -> None:
    adapter = MagicMock()
    adapter._signed_request.side_effect = requests.ConnectionError("DNS fail")
    client = ETradeBronzeClient(access_token="tok", access_token_secret="sec", adapter=adapter)
    with pytest.raises(ETradeAPIError) as exc:
        client.list_accounts()
    assert exc.value.permanent is False


def test_non_json_body_is_permanent() -> None:
    client = _make_client_with_response(
        _FakeResponse(200, text="<html>oops</html>", raise_json=True)
    )
    with pytest.raises(ETradeAPIError) as exc:
        client.list_accounts()
    assert exc.value.permanent is True


def test_json_root_not_object_is_permanent() -> None:
    client = _make_client_with_response(_FakeResponse(200, json_body=[1, 2, 3]))
    with pytest.raises(ETradeAPIError) as exc:
        client.list_accounts()
    assert exc.value.permanent is True


def test_empty_account_id_key_raises_permanent() -> None:
    client = _make_client_with_response(_FakeResponse(200, json_body={}))
    for fn in (client.get_balance, client.get_portfolio, client.get_transactions):
        with pytest.raises(ETradeAPIError) as exc:
            fn("")
        assert exc.value.permanent is True


def test_urls_use_json_suffix() -> None:
    """E*TRADE returns XML unless the path ends with ``.json`` — this is the
    only way we avoid having to teach the adapter about headers."""
    adapter = MagicMock()
    adapter._signed_request.return_value = _FakeResponse(200, json_body={})
    client = ETradeBronzeClient(access_token="tok", access_token_secret="sec", adapter=adapter)
    client.list_accounts()
    client.get_portfolio("KEY")
    client.get_balance("KEY")
    client.get_transactions("KEY")
    called_paths = [call.args[1] for call in adapter._signed_request.call_args_list]
    assert all(".json" in p for p in called_paths), called_paths
