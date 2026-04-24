"""Tests for :mod:`app.services.portfolio.plaid.client`.

Scope:
* ``PlaidClient.__init__`` raises :class:`PlaidConfigurationError` when env
  vars are missing or invalid.
* ``_resolve_products`` and ``_extract_plaid_error`` behave as specified
  (unknown product token is loud; malformed error body yields a structured
  dict, not KeyError).
* Token encryption is a pass-through to :mod:`app.services.oauth.encryption`
  and never leaks plaintext.

These tests do NOT hit the real Plaid API; they monkeypatch
``settings.*`` attributes and assert on pure-function behavior.
"""

from __future__ import annotations

import pytest

from app.config import settings

try:
    from app.services.portfolio.plaid import client as plaid_client_module
    from app.services.portfolio.plaid.client import (
        PlaidAPIError,
        PlaidClient,
        PlaidConfigurationError,
        _extract_plaid_error,
        _resolve_products,
    )
    AVAILABLE = True
except Exception:  # pragma: no cover - skip when plaid sdk is not installed
    AVAILABLE = False


pytestmark = [
    pytest.mark.no_db,
    pytest.mark.skipif(not AVAILABLE, reason="plaid-python not available"),
]


@pytest.fixture
def plaid_env(monkeypatch):
    """Apply a sandbox Plaid config to ``settings`` for the test."""
    monkeypatch.setattr(settings, "PLAID_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "PLAID_SECRET", "test-secret")
    monkeypatch.setattr(settings, "PLAID_ENV", "sandbox")
    monkeypatch.setattr(settings, "PLAID_PRODUCTS", "investments")
    monkeypatch.setattr(settings, "PLAID_WEBHOOK_URL", "")
    yield


def test_client_requires_client_id(monkeypatch):
    monkeypatch.setattr(settings, "PLAID_CLIENT_ID", "")
    monkeypatch.setattr(settings, "PLAID_SECRET", "s")
    with pytest.raises(PlaidConfigurationError):
        PlaidClient()


def test_client_requires_secret(monkeypatch):
    monkeypatch.setattr(settings, "PLAID_CLIENT_ID", "c")
    monkeypatch.setattr(settings, "PLAID_SECRET", "")
    with pytest.raises(PlaidConfigurationError):
        PlaidClient()


def test_client_rejects_unknown_env(monkeypatch, plaid_env):
    monkeypatch.setattr(settings, "PLAID_ENV", "staging")
    with pytest.raises(PlaidConfigurationError):
        PlaidClient()


def test_client_accepts_sandbox(plaid_env):
    client = PlaidClient()
    assert client.environment == "sandbox"
    client.close()


def test_resolve_products_rejects_empty(monkeypatch, plaid_env):
    monkeypatch.setattr(settings, "PLAID_PRODUCTS", "")
    with pytest.raises(PlaidConfigurationError):
        _resolve_products()


def test_resolve_products_rejects_typo(monkeypatch, plaid_env):
    monkeypatch.setattr(settings, "PLAID_PRODUCTS", "investmennts")
    with pytest.raises(PlaidConfigurationError):
        _resolve_products()


def test_resolve_products_accepts_investments(plaid_env):
    products = _resolve_products()
    assert len(products) == 1


def test_extract_plaid_error_from_json_body():
    class _Exc:
        body = (
            '{"error_code":"ITEM_LOGIN_REQUIRED",'
            '"error_type":"ITEM_ERROR",'
            '"display_message":"login required",'
            '"request_id":"abc123"}'
        )

    parsed = _extract_plaid_error(_Exc())
    assert parsed["error_code"] == "ITEM_LOGIN_REQUIRED"
    assert parsed["error_type"] == "ITEM_ERROR"
    assert parsed["display_message"] == "login required"
    assert parsed["request_id"] == "abc123"


def test_extract_plaid_error_from_bytes_body():
    class _Exc:
        body = b'{"error_code":"RATE_LIMIT_EXCEEDED"}'

    parsed = _extract_plaid_error(_Exc())
    assert parsed["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert parsed["error_type"] is None


def test_extract_plaid_error_handles_malformed_body():
    class _Exc:
        body = "not-json"

    parsed = _extract_plaid_error(_Exc())
    assert parsed == {
        "error_code": None,
        "error_type": None,
        "display_message": None,
        "request_id": None,
    }


def test_encrypt_decrypt_roundtrip(plaid_env):
    plaintext = "access-sandbox-test-token-xyz"
    ct = PlaidClient.encrypt_access_token(plaintext)
    assert ct != plaintext, "ciphertext must not equal plaintext"
    assert plaintext not in ct, "plaintext must not appear inside ciphertext"
    assert PlaidClient.decrypt_access_token(ct) == plaintext


def test_create_link_token_surfaces_plaid_error(plaid_env, monkeypatch):
    """If the SDK raises ApiException, PlaidClient.create_link_token must
    translate to PlaidAPIError (never a bare ApiException)."""
    from plaid.exceptions import ApiException

    class _FakePlaidApi:
        def link_token_create(self, _req):
            exc = ApiException(status=400, reason="bad")
            exc.body = '{"error_code":"INVALID_FIELD","error_type":"INVALID_REQUEST"}'
            raise exc

    client = PlaidClient()
    monkeypatch.setattr(client, "_api", _FakePlaidApi(), raising=True)
    try:
        with pytest.raises(PlaidAPIError) as ei:
            client.create_link_token(user_id=7)
        assert ei.value.error_code == "INVALID_FIELD"
        assert ei.value.error_type == "INVALID_REQUEST"
    finally:
        client.close()
