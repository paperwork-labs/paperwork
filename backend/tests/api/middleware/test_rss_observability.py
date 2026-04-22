"""Unit tests for per-request peak RSS (ru_maxrss) observability."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.rss_observability import RssObservabilityMiddleware
from backend.services.observability import rss_store


@pytest.fixture
def _rss_enabled(monkeypatch):
    monkeypatch.setattr("backend.config.settings.ENABLE_RSS_OBSERVABILITY", True, raising=False)


def test_middleware_invokes_rss_record_with_growing_maxrss(
    _rss_enabled,
    monkeypatch,
):
    """Middleware records delta when ru_maxrss increases between start and end of the request."""
    calls = [0]
    r = MagicMock()
    r.pipeline = MagicMock(return_value=MagicMock())  # not used: we patch record

    def fake_getrusage(_who: int) -> SimpleNamespace:
        if sys.platform == "darwin":
            c = calls[0]
            calls[0] += 1
            b = 10_000_000 + c * 100_000
            return SimpleNamespace(ru_maxrss=b)
        c = calls[0]
        calls[0] += 1
        return SimpleNamespace(ru_maxrss=1000 + c * 100)

    monkeypatch.setattr("backend.api.middleware.rss_observability.resource.getrusage", fake_getrusage)
    monkeypatch.setattr("backend.api.middleware.rss_observability._get_sync_redis", lambda: r)

    with patch("backend.api.middleware.rss_observability.record_request_rss_peak") as m_rec:
        app = FastAPI()
        app.add_middleware(RssObservabilityMiddleware)

        @app.get("/api/ping")
        def ping():
            return {"ok": True}

        c = TestClient(app)
        rj = c.get("/api/ping")
        assert rj.status_code == 200
        m_rec.assert_called_once()
        _cr, method, _path, s_b, e_b = m_rec.call_args[0]
        assert method == "GET"
        assert e_b >= s_b


def test_middleware_respects_feature_flag_off(monkeypatch):
    monkeypatch.setattr("backend.config.settings.ENABLE_RSS_OBSERVABILITY", False, raising=False)

    with patch("backend.api.middleware.rss_observability.record_request_rss_peak") as m_rec:
        app = FastAPI()
        app.add_middleware(RssObservabilityMiddleware)

        @app.get("/nope")
        def nope():
            return {"a": 1}

        c = TestClient(app)
        c.get("/nope")
        m_rec.assert_not_called()


def test_record_request_rss_peak_writes_to_redis():
    r = MagicMock()
    p = MagicMock()
    p.zadd = MagicMock(return_value=p)
    p.rpush = MagicMock(return_value=p)
    p.ltrim = MagicMock(return_value=p)
    p.incr = MagicMock(return_value=p)
    p.expire = MagicMock(return_value=p)
    p.execute = MagicMock(return_value=[1, 1, 1, 1, 1, 1, 1])
    r.pipeline = MagicMock(return_value=p)
    rss_store.record_request_rss_peak(r, "GET", "/api/a", 100_000, 150_000)
    r.pipeline.assert_called_once()
    p.execute.assert_called_once()


def test_middleware_fails_open_on_redis_write_error(
    _rss_enabled,
    monkeypatch,
):
    rss_store._RSS_DEGRADE["count"] = 0
    rss_store._RSS_DEGRADE["last_error"] = None
    p = MagicMock()
    p.zadd = MagicMock(return_value=p)
    p.rpush = MagicMock(return_value=p)
    p.ltrim = MagicMock(return_value=p)
    p.incr = MagicMock(return_value=p)
    p.expire = MagicMock(return_value=p)
    p.execute = MagicMock(side_effect=OSError("simulated connection failure"))
    r = MagicMock()
    r.pipeline = MagicMock(return_value=p)
    calls = [0]

    def fake_getrusage(_w: int) -> SimpleNamespace:
        if sys.platform == "darwin":
            b = 5_000_000 + calls[0] * 50_000
            calls[0] += 1
            return SimpleNamespace(ru_maxrss=b)
        c0 = 500 + (calls[0] * 50)
        calls[0] += 1
        return SimpleNamespace(ru_maxrss=c0)

    monkeypatch.setattr("backend.api.middleware.rss_observability.resource.getrusage", fake_getrusage)
    monkeypatch.setattr("backend.api.middleware.rss_observability._get_sync_redis", lambda: r)

    app = FastAPI()
    app.add_middleware(RssObservabilityMiddleware)

    @app.get("/boom")
    def boom():
        return {"ok": True}

    c = TestClient(app)
    resp = c.get("/boom")
    assert resp.status_code == 200
    snap = rss_store.rss_redis_degradation_snapshot()
    assert snap["count"] >= 1
    assert "simulated" in (snap.get("last_error") or "")


def test_maxrss_to_bytes():
    if sys.platform == "darwin":
        assert rss_store.maxrss_to_bytes(512) == 512
    else:
        assert rss_store.maxrss_to_bytes(512) == 512 * 1024
