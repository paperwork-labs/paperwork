"""Tests for AdminHealthService strict composite health logic."""

from unittest.mock import MagicMock, patch
import json

from backend.services.market.admin_health_service import (
    AdminHealthService,
    HEALTH_THRESHOLDS,
    _dim_status,
)


def _mock_service():
    """Return an AdminHealthService whose internal dependencies are mocked."""
    with patch(
        "backend.services.market.admin_health_service.AdminHealthService.__init__",
        lambda self: None,
    ):
        svc = AdminHealthService()
    svc._svc = MagicMock()
    return svc


def _make_db():
    """Return a mock DB session with chainable query support."""
    db = MagicMock()
    q = db.query.return_value.filter.return_value
    q.count.return_value = 0
    q.filter.return_value = q
    q.order_by.return_value.first.return_value = None
    return db


# ---- dim_status -----------------------------------------------------------

def test_dim_status_green():
    assert _dim_status(True) == "green"


def test_dim_status_red():
    assert _dim_status(False) == "red"


# ---- composite logic ------------------------------------------------------

def test_all_green():
    svc = _mock_service()
    svc._build_coverage_dimension = MagicMock(return_value={"status": "green"})
    svc._build_stage_dimension = MagicMock(return_value={"status": "green"})
    svc._build_jobs_dimension = MagicMock(return_value={"status": "green"})
    svc._build_audit_dimension = MagicMock(return_value={"status": "green"})
    svc._build_regime_dimension = MagicMock(return_value={"status": "green"})
    svc._build_task_runs = MagicMock(return_value={})

    result = svc.get_composite_health(MagicMock())
    assert result["composite_status"] == "green"
    assert "All health" in result["composite_reason"]
    assert "dimensions" in result
    assert "thresholds" in result


def test_single_failure_is_yellow():
    svc = _mock_service()
    svc._build_coverage_dimension = MagicMock(return_value={"status": "green"})
    svc._build_stage_dimension = MagicMock(return_value={"status": "green"})
    svc._build_jobs_dimension = MagicMock(return_value={"status": "red"})
    svc._build_audit_dimension = MagicMock(return_value={"status": "green"})
    svc._build_regime_dimension = MagicMock(return_value={"status": "green"})
    svc._build_task_runs = MagicMock(return_value={})

    result = svc.get_composite_health(MagicMock())
    assert result["composite_status"] == "yellow"
    assert "jobs" in result["composite_reason"]


def test_multiple_failures_is_red():
    svc = _mock_service()
    svc._build_coverage_dimension = MagicMock(return_value={"status": "red"})
    svc._build_stage_dimension = MagicMock(return_value={"status": "green"})
    svc._build_jobs_dimension = MagicMock(return_value={"status": "red"})
    svc._build_audit_dimension = MagicMock(return_value={"status": "green"})
    svc._build_regime_dimension = MagicMock(return_value={"status": "green"})
    svc._build_task_runs = MagicMock(return_value={})

    result = svc.get_composite_health(MagicMock())
    assert result["composite_status"] == "red"
    assert "coverage" in result["composite_reason"]
    assert "jobs" in result["composite_reason"]


def test_response_includes_task_runs_and_thresholds():
    svc = _mock_service()
    task_data = {"admin_coverage_refresh": {"ts": "2025-01-01T00:00:00"}}
    svc._build_coverage_dimension = MagicMock(return_value={"status": "green"})
    svc._build_stage_dimension = MagicMock(return_value={"status": "green"})
    svc._build_jobs_dimension = MagicMock(return_value={"status": "green"})
    svc._build_audit_dimension = MagicMock(return_value={"status": "green"})
    svc._build_regime_dimension = MagicMock(return_value={"status": "green"})
    svc._build_task_runs = MagicMock(return_value=task_data)

    result = svc.get_composite_health(MagicMock())
    assert result["task_runs"] == task_data
    assert result["thresholds"] == dict(HEALTH_THRESHOLDS)
    assert "checked_at" in result


# ---- dimension builders ---------------------------------------------------

def test_coverage_green_when_above_threshold():
    svc = _mock_service()
    db = MagicMock()
    svc._svc.coverage.coverage_snapshot.return_value = {}
    with patch(
        "backend.services.market.coverage_utils.compute_coverage_status",
        return_value={
            "daily_pct": 98.0,
            "stale_daily": 0,
            "m5_pct": 90.0,
            "stale_m5": 2,
            "tracked_count": 500,
            "daily_expected_date": "2025-01-10",
            "summary": "Good",
        },
    ):
        dim = svc._build_coverage_dimension(db)
    assert dim["status"] == "green"
    assert dim["daily_pct"] == 98.0


def test_coverage_red_when_stale():
    svc = _mock_service()
    db = MagicMock()
    svc._svc.coverage.coverage_snapshot.return_value = {}
    with patch(
        "backend.services.market.coverage_utils.compute_coverage_status",
        return_value={"daily_pct": 50.0, "stale_daily": 5, "m5_pct": 0, "stale_m5": 0, "tracked_count": 500},
    ):
        dim = svc._build_coverage_dimension(db)
    assert dim["status"] == "red"


def test_stage_green():
    svc = _mock_service()
    db = MagicMock()
    svc._svc.stage_quality_summary.return_value = {
        "unknown_rate": 0.1,
        "invalid_stage_count": 0,
        "monotonicity_issues": 0,
        "stale_stage_count": 0,
        "total_symbols": 500,
        "stage_counts": {"2A": 100, "4": 50},
    }
    dim = svc._build_stage_dimension(db)
    assert dim["status"] == "green"
    assert dim["unknown_rate"] == 0.1


def test_stage_red_when_high_unknown():
    svc = _mock_service()
    db = MagicMock()
    svc._svc.stage_quality_summary.return_value = {
        "unknown_rate": 0.5,
        "invalid_stage_count": 0,
        "monotonicity_issues": 0,
        "stale_stage_count": 0,
        "total_symbols": 500,
        "stage_counts": {},
    }
    dim = svc._build_stage_dimension(db)
    assert dim["status"] == "red"


def test_audit_green():
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


def test_audit_red_when_no_cache():
    svc = _mock_service()
    svc._svc.redis_client.get.return_value = None
    dim = svc._build_audit_dimension()
    assert dim["status"] == "red"
    assert "error" in dim


def test_task_runs_loads_from_redis():
    svc = _mock_service()
    svc._svc.redis_client.get.side_effect = lambda k: (
        json.dumps({"ts": "2025-01-01T00:00:00"}) if "admin_coverage_refresh" in k else None
    )
    runs = svc._build_task_runs()
    assert runs.get("admin_coverage_refresh") is not None
    assert runs["admin_coverage_refresh"]["ts"] == "2025-01-01T00:00:00"
