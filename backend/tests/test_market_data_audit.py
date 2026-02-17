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
    """Audit should be green when explicit fill_pct fields are present and above thresholds."""
    svc = _mock_service()
    svc._svc.redis_client.get.return_value = json.dumps({
        "tracked_total": 500,
        "latest_daily_fill_pct": 98.0,
        "latest_snapshot_history_fill_pct": 95.0,
        "missing_snapshot_history_sample": [],
    })
    dim = svc._build_audit_dimension()
    assert dim["status"] == "green"
    assert dim["daily_fill_pct"] == 98.0
    assert dim["snapshot_fill_pct"] == 95.0


def test_audit_green_from_count_fields():
    """Audit should compute fill % from symbol counts when pct fields are missing."""
    svc = _mock_service()
    svc._svc.redis_client.get.return_value = json.dumps({
        "tracked_total": 581,
        "latest_daily_symbol_count": 581,
        "latest_snapshot_history_symbol_count": 581,
        "missing_snapshot_history_sample": [],
    })
    dim = svc._build_audit_dimension()
    assert dim["status"] == "green"
    assert dim["daily_fill_pct"] == 100.0
    assert dim["snapshot_fill_pct"] == 100.0


def test_audit_red_when_no_cache():
    svc = _mock_service()
    svc._svc.redis_client.get.return_value = None
    dim = svc._build_audit_dimension()
    assert dim["status"] == "red"
    assert "error" in dim


def test_audit_red_when_counts_low():
    """Audit should be red when computed fill % is below thresholds."""
    svc = _mock_service()
    svc._svc.redis_client.get.return_value = json.dumps({
        "tracked_total": 100,
        "latest_daily_symbol_count": 50,
        "latest_snapshot_history_symbol_count": 40,
        "missing_snapshot_history_sample": ["AAPL", "MSFT"],
    })
    dim = svc._build_audit_dimension()
    assert dim["status"] == "red"
    assert dim["daily_fill_pct"] == 50.0
    assert dim["snapshot_fill_pct"] == 40.0
