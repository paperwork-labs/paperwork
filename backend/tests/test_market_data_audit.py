"""Tests for the audit dimension in the consolidated /admin/health endpoint."""

import json
from unittest.mock import MagicMock, patch

from backend.services.market.admin_health_service import AdminHealthService


def _mock_service():
    """Return an AdminHealthService whose internal dependencies are mocked."""
    with patch(
        "backend.services.market.admin_health_service.AdminHealthService.__init__",
        lambda self: None,
    ):
        svc = AdminHealthService()
    svc._svc = MagicMock()
    return svc


def test_audit_green_from_pct_fields():
    """Audit should be green when cache has fill_pct fields above thresholds."""
    svc = _mock_service()
    db = MagicMock()
    svc._svc.redis_client.get.return_value = json.dumps({
        "tracked_total": 500,
        "daily_fill_pct": 98.0,
        "snapshot_fill_pct": 95.0,
        "missing_snapshot_history_sample": [],
    })
    dim = svc._build_audit_dimension(db)
    assert dim["status"] == "green"
    assert dim["daily_fill_pct"] == 98.0
    assert dim["snapshot_fill_pct"] == 95.0


def test_audit_green_from_count_fields():
    """Audit cache produced by compute_audit_metrics always includes pct fields."""
    svc = _mock_service()
    db = MagicMock()
    svc._svc.redis_client.get.return_value = json.dumps({
        "tracked_total": 581,
        "daily_fill_pct": 100.0,
        "snapshot_fill_pct": 100.0,
        "missing_snapshot_history_sample": [],
    })
    dim = svc._build_audit_dimension(db)
    assert dim["status"] == "green"
    assert dim["daily_fill_pct"] == 100.0
    assert dim["snapshot_fill_pct"] == 100.0


def test_audit_red_when_db_fails():
    """On cache miss, compute_audit_metrics is called; if it raises, dimension is red with error."""
    svc = _mock_service()
    db = MagicMock()
    svc._svc.redis_client.get.return_value = None
    svc.compute_audit_metrics = MagicMock(side_effect=Exception("DB unavailable"))
    dim = svc._build_audit_dimension(db)
    assert dim["status"] == "red"
    assert "error" in dim


def test_audit_red_when_fill_pct_low():
    """Audit should be red when fill percentages are below thresholds."""
    svc = _mock_service()
    db = MagicMock()
    svc._svc.redis_client.get.return_value = json.dumps({
        "tracked_total": 100,
        "daily_fill_pct": 50.0,
        "snapshot_fill_pct": 40.0,
        "missing_snapshot_history_sample": ["AAPL", "MSFT"],
    })
    dim = svc._build_audit_dimension(db)
    assert dim["status"] == "red"
    assert dim["daily_fill_pct"] == 50.0
    assert dim["snapshot_fill_pct"] == 40.0
