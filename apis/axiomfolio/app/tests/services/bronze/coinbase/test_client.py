"""Unit tests for Coinbase bronze client helpers (no HTTP)."""

from __future__ import annotations

import pytest

from app.services.bronze.coinbase.client import CoinbaseAPIError, _next_page_path


def test_next_page_path_rejects_foreign_https_host() -> None:
    with pytest.raises(CoinbaseAPIError) as exc_info:
        _next_page_path(
            {
                "next_uri": "https://evil.example.com/steal",
            }
        )
    assert "unexpected pagination host" in str(exc_info.value).lower()
    assert "evil.example.com" in str(exc_info.value)


def test_next_page_path_accepts_coinbase_https_uri() -> None:
    out = _next_page_path(
        {
            "next_uri": "https://api.coinbase.com/v2/accounts?cursor=abc",
        }
    )
    assert out == "/v2/accounts?cursor=abc"
    assert out.startswith("/")
