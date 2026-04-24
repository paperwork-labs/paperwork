"""Tests for the audit dimension in the consolidated /admin/health endpoint."""

import json
from unittest.mock import MagicMock

from app.services.silver.market.admin_health_service import AdminHealthService
import app.services.silver.market.admin_health_service as ahs_mod


def test_audit_green_from_pct_fields(monkeypatch):
    """Audit should be green when cache has fill_pct fields above thresholds."""
    redis_mock = MagicMock()
    redis_mock.get.return_value = json.dumps({
        "tracked_total": 500,
        "daily_fill_pct": 98.0,
        "snapshot_fill_pct": 95.0,
        "missing_snapshot_history_sample": [],
    })
    monkeypatch.setattr(ahs_mod.infra, "_redis_sync", redis_mock)
    svc = AdminHealthService()
    db = MagicMock()
    dim = svc._build_audit_dimension(db)
    assert dim["status"] == "green"
    assert dim["daily_fill_pct"] == 98.0
    assert dim["snapshot_fill_pct"] == 95.0


def test_audit_green_from_count_fields(monkeypatch):
    """Audit cache produced by compute_audit_metrics always includes pct fields."""
    redis_mock = MagicMock()
    redis_mock.get.return_value = json.dumps({
        "tracked_total": 581,
        "daily_fill_pct": 100.0,
        "snapshot_fill_pct": 100.0,
        "missing_snapshot_history_sample": [],
    })
    monkeypatch.setattr(ahs_mod.infra, "_redis_sync", redis_mock)
    svc = AdminHealthService()
    db = MagicMock()
    dim = svc._build_audit_dimension(db)
    assert dim["status"] == "green"
    assert dim["daily_fill_pct"] == 100.0
    assert dim["snapshot_fill_pct"] == 100.0


def test_audit_red_when_db_fails(monkeypatch):
    """On cache miss, compute_audit_metrics is called; if it raises, dimension is red with error."""
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    monkeypatch.setattr(ahs_mod.infra, "_redis_sync", redis_mock)
    svc = AdminHealthService()
    svc.compute_audit_metrics = MagicMock(side_effect=Exception("DB unavailable"))
    db = MagicMock()
    dim = svc._build_audit_dimension(db)
    assert dim["status"] == "red"
    assert "error" in dim


def test_audit_red_when_fill_pct_low(monkeypatch):
    """Audit should be red when fill percentages are below thresholds."""
    redis_mock = MagicMock()
    redis_mock.get.return_value = json.dumps({
        "tracked_total": 100,
        "daily_fill_pct": 50.0,
        "snapshot_fill_pct": 40.0,
        "missing_snapshot_history_sample": ["AAPL", "MSFT"],
    })
    monkeypatch.setattr(ahs_mod.infra, "_redis_sync", redis_mock)
    svc = AdminHealthService()
    db = MagicMock()
    dim = svc._build_audit_dimension(db)
    assert dim["status"] == "red"
    assert dim["daily_fill_pct"] == 50.0
    assert dim["snapshot_fill_pct"] == 40.0
