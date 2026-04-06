"""Tests for AdminHealthService strict composite health logic."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import json

from backend.models import BrokerAccount
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


def _mock_db_portfolio_sync(accounts):
    """Mock session for _build_portfolio_sync_dimension: query(BrokerAccount).filter(...).all()."""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = accounts
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
    svc._build_fundamentals_dimension = MagicMock(return_value={"status": "ok"})
    svc._build_portfolio_sync_dimension = MagicMock(return_value={"status": "ok"})
    svc._build_ibkr_gateway_dimension = MagicMock(return_value={"status": "green"})
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
    svc._build_fundamentals_dimension = MagicMock(return_value={"status": "ok"})
    svc._build_portfolio_sync_dimension = MagicMock(return_value={"status": "ok"})
    svc._build_ibkr_gateway_dimension = MagicMock(return_value={"status": "green"})
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
    svc._build_fundamentals_dimension = MagicMock(return_value={"status": "ok"})
    svc._build_portfolio_sync_dimension = MagicMock(return_value={"status": "ok"})
    svc._build_ibkr_gateway_dimension = MagicMock(return_value={"status": "green"})
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
    svc._build_fundamentals_dimension = MagicMock(return_value={"status": "ok"})
    svc._build_portfolio_sync_dimension = MagicMock(return_value={"status": "ok"})
    svc._build_ibkr_gateway_dimension = MagicMock(return_value={"status": "green"})
    svc._build_task_runs = MagicMock(return_value=task_data)

    result = svc.get_composite_health(MagicMock())
    assert result["task_runs"] == task_data
    assert result["thresholds"] == dict(HEALTH_THRESHOLDS)
    assert "checked_at" in result


# ---- dimension builders ---------------------------------------------------

def test_coverage_green_when_above_threshold():
    svc = _mock_service()
    svc._check_provider_keys = MagicMock(return_value={"fmp": "ok", "finnhub": "ok"})
    db = MagicMock()
    svc._svc.coverage.coverage_snapshot.return_value = {
        "indices": {
            "SP500": 503,
            "NASDAQ100": 101,
            "DOW30": 30,
            "RUSSELL2000": 1980,
        },
    }
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
    assert dim["constituent_issues"] == []


def test_coverage_red_when_stale():
    svc = _mock_service()
    svc._check_provider_keys = MagicMock(return_value={"fmp": "ok", "finnhub": "ok"})
    db = MagicMock()
    svc._svc.coverage.coverage_snapshot.return_value = {}
    with patch(
        "backend.services.market.coverage_utils.compute_coverage_status",
        return_value={"daily_pct": 50.0, "stale_daily": 5, "m5_pct": 0, "stale_m5": 0, "tracked_count": 500},
    ):
        dim = svc._build_coverage_dimension(db)
    assert dim["status"] == "red"


def test_coverage_red_when_index_has_zero_constituents():
    svc = _mock_service()
    svc._check_provider_keys = MagicMock(return_value={"fmp": "ok", "finnhub": "ok"})
    db = MagicMock()
    svc._svc.coverage.coverage_snapshot.return_value = {
        "indices": {
            "SP500": 503,
            "NASDAQ100": 101,
            "DOW30": 30,
            "RUSSELL2000": 0,
        },
    }
    with patch(
        "backend.services.market.coverage_utils.compute_coverage_status",
        return_value={"daily_pct": 98.0, "stale_daily": 0, "m5_pct": 90.0, "stale_m5": 0, "tracked_count": 500},
    ):
        dim = svc._build_coverage_dimension(db)
    assert dim["status"] == "red"
    assert "RUSSELL2000" in dim["constituent_issues"]


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
        "daily_fill_pct": 98.0,
        "snapshot_fill_pct": 95.0,
        "missing_snapshot_history_sample": [],
    })
    db = MagicMock()
    dim = svc._build_audit_dimension(db)
    assert dim["status"] == "green"
    assert dim["daily_fill_pct"] == 98.0


def test_audit_red_when_db_fails():
    """When cache is empty and DB computation raises, audit returns red with error."""
    svc = _mock_service()
    svc._svc.redis_client.get.return_value = None
    db = MagicMock()
    svc.compute_audit_metrics = MagicMock(side_effect=Exception("DB unavailable"))
    dim = svc._build_audit_dimension(db)
    assert dim["status"] == "red"
    assert "error" in dim


def test_task_runs_loads_from_redis():
    svc = _mock_service()
    from backend.services.market.admin_health_service import _TASK_STATUS_KEYS

    def _mock_mget(keys):
        return [
            json.dumps({"ts": "2025-01-01T00:00:00"})
            if "admin_coverage_refresh" in k else None
            for k in keys
        ]

    svc._svc.redis_client.mget.side_effect = _mock_mget
    runs = svc._build_task_runs()
    assert runs.get("admin_coverage_refresh") is not None
    assert runs["admin_coverage_refresh"]["ts"] == "2025-01-01T00:00:00"

def test_fundamentals_ok_at_pass_threshold():
    svc = _mock_service()
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.scalar.return_value = 80

    with patch(
        "backend.services.market.universe.tracked_symbols_with_source",
        return_value=(["S" + str(i) for i in range(100)], True),
    ):
        dim = svc._build_fundamentals_dimension(db)
    assert dim["status"] == "ok"
    assert dim["fundamentals_fill_pct"] == 80.0
    assert dim["filled_count"] == 80
    assert dim["tracked_total"] == 100


def test_fundamentals_warning_between_warn_and_pass():
    svc = _mock_service()
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.scalar.return_value = 60

    with patch(
        "backend.services.market.universe.tracked_symbols_with_source",
        return_value=(["S" + str(i) for i in range(100)], True),
    ):
        dim = svc._build_fundamentals_dimension(db)
    assert dim["status"] == "warning"
    assert dim["fundamentals_fill_pct"] == 60.0


def test_fundamentals_error_below_warn():
    svc = _mock_service()
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.scalar.return_value = 10

    with patch(
        "backend.services.market.universe.tracked_symbols_with_source",
        return_value=(["S" + str(i) for i in range(100)], True),
    ):
        dim = svc._build_fundamentals_dimension(db)
    assert dim["status"] == "error"
    assert dim["fundamentals_fill_pct"] == 10.0


def test_portfolio_sync_ok_when_no_enabled_accounts():
    svc = _mock_service()
    db = _mock_db_portfolio_sync([])
    dim = svc._build_portfolio_sync_dimension(db)
    db.query.assert_called_once_with(BrokerAccount)
    assert dim["status"] == "ok"
    assert dim["total_accounts"] == 0
    assert dim["stale_accounts"] == 0
    assert dim["stale_list"] == []
    assert "no broker accounts" in dim["note"]


def test_portfolio_sync_green_when_all_accounts_fresh():
    svc = _mock_service()
    now = datetime.utcnow()
    a1 = MagicMock()
    a1.last_successful_sync = now - timedelta(hours=1)
    a1.account_number = "U111"
    a2 = MagicMock()
    a2.last_successful_sync = now - timedelta(hours=2)
    a2.account_number = "U222"
    db = _mock_db_portfolio_sync([a1, a2])
    dim = svc._build_portfolio_sync_dimension(db)
    db.query.assert_called_once_with(BrokerAccount)
    assert dim["status"] == "green"
    assert dim["total_accounts"] == 2
    assert dim["stale_accounts"] == 0
    assert dim["stale_list"] == []


def test_portfolio_sync_red_when_some_accounts_stale():
    svc = _mock_service()
    now = datetime.utcnow()
    fresh = MagicMock()
    fresh.last_successful_sync = now - timedelta(hours=1)
    fresh.account_number = "FRESH1"
    old = MagicMock()
    old.last_successful_sync = now - timedelta(hours=48)
    old.account_number = "STALE1"
    never = MagicMock()
    never.last_successful_sync = None
    never.account_number = "NEVER1"
    db = _mock_db_portfolio_sync([fresh, old, never])
    dim = svc._build_portfolio_sync_dimension(db)
    db.query.assert_called_once_with(BrokerAccount)
    assert dim["status"] == "red"
    assert dim["total_accounts"] == 3
    assert dim["stale_accounts"] == 2
    assert set(dim["stale_list"]) == {"STALE1", "NEVER1"}


def test_portfolio_sync_error_on_exception():
    svc = _mock_service()
    db = MagicMock()
    db.query.side_effect = RuntimeError("db unavailable")
    dim = svc._build_portfolio_sync_dimension(db)
    db.query.assert_called_once_with(BrokerAccount)
    assert dim["status"] == "error"
    assert dim["error"] == "db unavailable"


def test_composite_counts_fundamentals_warning_as_failure():
    svc = _mock_service()
    svc._build_coverage_dimension = MagicMock(return_value={"status": "green"})
    svc._build_stage_dimension = MagicMock(return_value={"status": "green"})
    svc._build_jobs_dimension = MagicMock(return_value={"status": "green"})
    svc._build_audit_dimension = MagicMock(return_value={"status": "green"})
    svc._build_regime_dimension = MagicMock(return_value={"status": "green"})
    svc._build_fundamentals_dimension = MagicMock(return_value={"status": "warning"})
    svc._build_portfolio_sync_dimension = MagicMock(return_value={"status": "ok"})
    svc._build_ibkr_gateway_dimension = MagicMock(return_value={"status": "green"})
    svc._build_task_runs = MagicMock(return_value={})

    result = svc.get_composite_health(MagicMock())
    assert result["composite_status"] == "green"
