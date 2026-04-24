"""Schwab option field mapping: optionExpirationDate + OCC symbol fallback."""
from __future__ import annotations

import pytest

from backend.services.clients.schwab_client import (
    SchwabClient,
    _option_expiry_iso_from_occ_symbol,
)


def test_occ_symbol_fallback_yyymmdd() -> None:
    assert _option_expiry_iso_from_occ_symbol("SOUN  260717C00009000") == "2026-07-17"
    assert _option_expiry_iso_from_occ_symbol("") == ""


@pytest.mark.asyncio
async def test_get_options_positions_uses_option_expiration_date(monkeypatch) -> None:
    """Schwab Trader returns expiry under optionExpirationDate (not expirationDate)."""
    six_instruments = [
        {
            "underlyingSymbol": "RDDT",
            "symbol": "RDDT  250815C00145000",
            "optionExpirationDate": "2025-08-15",
        },
        {
            "underlyingSymbol": "DE",
            "symbol": "DE    250815C00580000",
            "optionExpirationDate": "2025-08-16",
        },
        {
            "underlyingSymbol": "MSTR",
            "symbol": "MSTR  250815C00250000",
            "optionExpirationDate": "2025-08-17",
        },
        {
            "underlyingSymbol": "SOFI",
            "symbol": "SOFI  250815C00020000",
            "optionExpirationDate": "2025-08-18",
        },
        {
            "underlyingSymbol": "SOUN",
            "symbol": "SOUN  250815C00009000",
            "optionExpirationDate": "2025-08-19",
        },
        {
            "underlyingSymbol": "WMT",
            "symbol": "WMT   250815C00130000",
            "optionExpirationDate": "2025-08-20",
        },
    ]
    raw_positions = [
        {
            "longQuantity": 1,
            "shortQuantity": 0,
            "instrument": {
                "assetType": "OPTION",
                "underlyingSymbol": row["underlyingSymbol"],
                "symbol": row["symbol"],
                "strikePrice": 100.0,
                "putCall": "CALL",
                "optionExpirationDate": row["optionExpirationDate"],
            },
        }
        for row in six_instruments
    ]

    client = SchwabClient()
    client.connected = True
    client._access_token = "t"

    async def _hash(_n: str) -> str:
        return "h1"

    async def _fetch(_h: str) -> list:
        return raw_positions

    monkeypatch.setattr(client, "_resolve_account_hash", _hash)
    monkeypatch.setattr(client, "_fetch_positions_raw", _fetch)

    out = await client.get_options_positions("123")
    assert len(out) == 6
    for i, row in enumerate(out):
        want = six_instruments[i]["optionExpirationDate"]
        assert str(row["expiration"]).startswith(want[:10])
        assert row["symbol"] == six_instruments[i]["underlyingSymbol"]


@pytest.mark.asyncio
async def test_get_options_positions_occ_when_no_date_keys(monkeypatch) -> None:
    """If expiration keys are missing, parse YYMMDD from OCC symbol (indices 6–11)."""
    raw = [
        {
            "longQuantity": 1,
            "shortQuantity": 0,
            "instrument": {
                "assetType": "OPTION",
                "underlyingSymbol": "SOUN",
                "symbol": "SOUN  260717C00009000",
                "strikePrice": 9.0,
                "putCall": "CALL",
            },
        }
    ]
    client = SchwabClient()
    client.connected = True
    client._access_token = "t"

    async def _hash(_n: str) -> str:
        return "h1"

    async def _fetch(_h: str) -> list:
        return raw

    monkeypatch.setattr(client, "_resolve_account_hash", _hash)
    monkeypatch.setattr(client, "_fetch_positions_raw", _fetch)

    out = await client.get_options_positions("123")
    assert len(out) == 1
    assert out[0]["expiration"] == "2026-07-17"
    assert out[0]["symbol"] == "SOUN"
