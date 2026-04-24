"""FastAPI integration tests for /api/v1/share/chart/* (requires TEST_DATABASE_URL)."""

from __future__ import annotations

import os

import pandas as pd
import pytest

if not os.getenv("TEST_DATABASE_URL"):
    pytest.skip("TEST_DATABASE_URL required for app import and TestClient", allow_module_level=True)

from fastapi.testclient import TestClient

from app.api.main import app
from app.services.share.chart_share_token import create_chart_share_token


def _sample_ohlcv_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=40, freq="D")
    df = pd.DataFrame(
        {
            "Open": range(100, 140),
            "High": range(101, 141),
            "Low": range(99, 139),
            "Close": range(100, 140),
            "Volume": [1_000_000] * 40,
        },
        index=idx,
    )
    return df.iloc[::-1]


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_get_og_png_returns_png(client, monkeypatch):
    from app.api.routes.share import chart_og as chart_og_mod

    async def fake_hist(*args, **kwargs):
        return _sample_ohlcv_df(), "yfinance"

    monkeypatch.setattr(chart_og_mod.provider_router, "get_historical_data", fake_hist)

    token = create_chart_share_token(user_id=1, symbol="TEST", period="1y", indicators=[])
    r = client.get(f"/api/v1/share/chart/{token}/og.png")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/png")
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_get_share_bars_ok(client, monkeypatch):
    from app.api.routes.share import chart_og as chart_og_mod

    async def fake_hist(*args, **kwargs):
        return _sample_ohlcv_df(), "db"

    monkeypatch.setattr(chart_og_mod.provider_router, "get_historical_data", fake_hist)

    token = create_chart_share_token(user_id=1, symbol="TEST", period="1y", indicators=["emas"])
    r = client.get(f"/api/v1/share/chart/{token}/bars")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "TEST"
    assert len(body["bars"]) > 0
    assert "emas" in body["indicators"]
