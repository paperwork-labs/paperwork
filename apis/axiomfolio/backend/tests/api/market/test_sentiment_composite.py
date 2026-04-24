"""Tests for GET /api/v1/market-data/sentiment/composite."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_market_data_viewer
from backend.api.main import app
from backend.api.routes.market import sentiment_composite as sc_mod
from backend.database import get_db
from backend.models.market_data import MarketRegime, MarketSnapshot
from backend.models.user import UserRole


def _viewer_override():
    class _DummyUser:
        id = 42
        role = UserRole.OWNER
        is_active = True
        email = "sentiment-test@example.com"

    return _DummyUser()


def _override_get_db(db_session):
    def _dep():
        yield db_session

    return _dep


def test_sentiment_composite_happy_path(db_session):
    """Regime row supplies VIX + regime; AAII/F&G remain null (stubs)."""
    if db_session is None:
        pytest.skip("database not configured")

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    app.dependency_overrides[get_db] = _override_get_db(db_session)

    row = MarketRegime(
        as_of_date=datetime(2026, 4, 20, tzinfo=timezone.utc),
        vix_spot=18.4,
        vix3m_vix_ratio=1.05,
        vvix_vix_ratio=5.0,
        nh_nl=100,
        pct_above_200d=55.0,
        pct_above_50d=60.0,
        score_vix=2.0,
        score_vix3m_vix=2.0,
        score_vvix_vix=2.0,
        score_nh_nl=2.0,
        score_above_200d=2.0,
        score_above_50d=2.0,
        composite_score=2.5,
        regime_state="R3",
        weights_used=[1.0, 1.25, 0.75, 1.0, 1.0, 0.75],
        cash_floor_pct=5.0,
        max_equity_exposure_pct=95.0,
        regime_multiplier=1.0,
    )
    db_session.add(row)
    db_session.commit()

    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/sentiment/composite")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["vix"] == 18.4
        assert data["aaii"] is None
        assert data["fear_greed"] is None
        assert data["regime"] == {"state": "R3", "score": 2.5}
        assert "asof" in data and data["asof"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_sentiment_composite_stub_only_empty_db():
    """No regime row: null fields, 200 — no silent zeros."""
    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/sentiment/composite")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["vix"] is None
        assert data["aaii"] is None
        assert data["fear_greed"] is None
        assert data["regime"] is None
        assert data.get("asof")
    finally:
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_sentiment_composite_error_path(monkeypatch: pytest.MonkeyPatch):
    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    def _boom(_db):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(sc_mod, "build_sentiment_composite_payload", _boom)

    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/sentiment/composite")
        assert resp.status_code == 500
        assert "detail" in resp.json()
    finally:
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_vix_falls_back_to_snapshot(db_session):
    """When regime has no VIX, ^VIX snapshot row supplies vix."""
    if db_session is None:
        pytest.skip("database not configured")

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    app.dependency_overrides[get_db] = _override_get_db(db_session)

    regime = MarketRegime(
        as_of_date=datetime(2026, 4, 19, tzinfo=timezone.utc),
        vix_spot=None,
        vix3m_vix_ratio=1.0,
        vvix_vix_ratio=5.0,
        nh_nl=0,
        pct_above_200d=50.0,
        pct_above_50d=50.0,
        score_vix=3.0,
        score_vix3m_vix=3.0,
        score_vvix_vix=3.0,
        score_nh_nl=3.0,
        score_above_200d=3.0,
        score_above_50d=3.0,
        composite_score=3.0,
        regime_state="R3",
        weights_used=None,
        cash_floor_pct=0.0,
        max_equity_exposure_pct=100.0,
        regime_multiplier=1.0,
    )
    snap = MarketSnapshot(
        symbol="^VIX",
        analysis_type="technical_snapshot",
        current_price=17.25,
        expiry_timestamp=datetime(2099, 1, 1, tzinfo=timezone.utc),
        as_of_timestamp=datetime(2026, 4, 19, 16, 0, tzinfo=timezone.utc),
    )
    db_session.add_all([regime, snap])
    db_session.commit()

    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/sentiment/composite")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["vix"] == 17.25
        assert data["regime"] is not None
        assert data["regime"]["state"] == "R3"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)
