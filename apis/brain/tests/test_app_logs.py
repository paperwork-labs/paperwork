"""Tests for WS-69 PR M: Brain-owned log ingestion, storage, and anomaly detection."""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import app.services.app_logs as app_logs_svc
from app.schemas.app_log import AppLogIngestRequest, AppLogsFile

_ENV = "BRAIN_APP_LOGS_JSON"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def logs_path(tmp_path: Path) -> Path:
    p = tmp_path / "app_logs.json"
    p.write_text(
        json.dumps(
            {
                "schema": "app_logs/v1",
                "description": "test",
                "logs": [],
                "last_pulled_at": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    prev = os.environ.get(_ENV)
    os.environ[_ENV] = str(p)
    yield p
    if prev is None:
        os.environ.pop(_ENV, None)
    else:
        os.environ[_ENV] = prev


def _req(
    app: str = "studio",
    service: str = "vercel-prod",
    severity: str = "info",
    message: str = "test log",
    metadata: dict | None = None,
    at: datetime | None = None,
) -> AppLogIngestRequest:
    return AppLogIngestRequest(
        app=app,  # type: ignore[arg-type]
        service=service,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        metadata=metadata or {},
        at=at,
    )


# ---------------------------------------------------------------------------
# Ingest tests
# ---------------------------------------------------------------------------


def test_ingest_creates_entry(logs_path: Path) -> None:
    req = _req(message="hello world")
    log = app_logs_svc.ingest_log(req)
    assert log.id
    assert log.app == "studio"
    assert log.source == "push"
    assert log.message == "hello world"

    # verify persisted
    raw = json.loads(logs_path.read_text())
    assert len(raw["logs"]) == 1
    assert raw["logs"][0]["id"] == log.id


def test_ingest_assigns_utc_now_when_at_is_none(logs_path: Path) -> None:
    before = datetime.now(UTC)
    log = app_logs_svc.ingest_log(_req())
    after = datetime.now(UTC)
    assert before <= log.at <= after


def test_ingest_uses_provided_at(logs_path: Path) -> None:
    at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    log = app_logs_svc.ingest_log(_req(at=at))
    assert log.at == at


def test_ingest_caps_at_max_entries(logs_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_logs_svc, "MAX_LOG_ENTRIES", 5)
    for i in range(7):
        app_logs_svc.ingest_log(_req(message=f"msg {i}"))
    raw = json.loads(logs_path.read_text())
    assert len(raw["logs"]) == 5
    # last 5 should survive
    messages = [lg["message"] for lg in raw["logs"]]
    assert "msg 2" in messages
    assert "msg 6" in messages
    assert "msg 0" not in messages


# ---------------------------------------------------------------------------
# List / search tests
# ---------------------------------------------------------------------------


def test_list_returns_newest_first(logs_path: Path) -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(3):
        app_logs_svc.ingest_log(_req(message=f"msg {i}", at=t0 + timedelta(hours=i)))
    page = app_logs_svc.list_logs()
    assert page.logs[0].message == "msg 2"
    assert page.logs[-1].message == "msg 0"


def test_list_filter_by_app(logs_path: Path) -> None:
    app_logs_svc.ingest_log(_req(app="studio", message="s1"))
    app_logs_svc.ingest_log(_req(app="brain", message="b1"))
    page = app_logs_svc.list_logs(app="brain")
    assert len(page.logs) == 1
    assert page.logs[0].message == "b1"


def test_list_filter_by_severity(logs_path: Path) -> None:
    app_logs_svc.ingest_log(_req(severity="info", message="i1"))
    app_logs_svc.ingest_log(_req(severity="error", message="e1"))
    page = app_logs_svc.list_logs(severity="error")
    assert len(page.logs) == 1
    assert page.logs[0].message == "e1"


def test_list_full_text_search(logs_path: Path) -> None:
    app_logs_svc.ingest_log(_req(message="database connection refused"))
    app_logs_svc.ingest_log(_req(message="request handled successfully"))
    page = app_logs_svc.list_logs(search="database")
    assert len(page.logs) == 1
    assert "database" in page.logs[0].message


def test_list_search_in_metadata(logs_path: Path) -> None:
    app_logs_svc.ingest_log(_req(message="generic error", metadata={"route": "/api/v1/payments"}))
    app_logs_svc.ingest_log(_req(message="other error", metadata={"route": "/health"}))
    page = app_logs_svc.list_logs(search="payments")
    assert len(page.logs) == 1


def test_list_since_filter(logs_path: Path) -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    app_logs_svc.ingest_log(_req(message="old", at=t0))
    app_logs_svc.ingest_log(_req(message="new", at=t0 + timedelta(hours=2)))
    page = app_logs_svc.list_logs(since=t0 + timedelta(hours=1))
    assert len(page.logs) == 1
    assert page.logs[0].message == "new"


def test_list_cursor_pagination(logs_path: Path) -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        app_logs_svc.ingest_log(_req(message=f"msg {i}", at=t0 + timedelta(hours=i)))
    page1 = app_logs_svc.list_logs(limit=2)
    assert len(page1.logs) == 2
    assert page1.next_cursor is not None

    page2 = app_logs_svc.list_logs(limit=2, cursor=page1.next_cursor)
    assert len(page2.logs) == 2
    # no overlap
    ids1 = {lg.id for lg in page1.logs}
    ids2 = {lg.id for lg in page2.logs}
    assert ids1.isdisjoint(ids2)


def test_list_empty_file_returns_empty_page(logs_path: Path) -> None:
    page = app_logs_svc.list_logs()
    assert page.logs == []
    assert page.total_matched == 0
    assert page.next_cursor is None


def test_list_missing_file_returns_empty_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "nonexistent.json"
    monkeypatch.setenv(_ENV, str(p))
    page = app_logs_svc.list_logs()
    assert page.logs == []


# ---------------------------------------------------------------------------
# Anomaly detection tests
# ---------------------------------------------------------------------------


def test_detect_anomalies_empty_batch(logs_path: Path) -> None:
    assert app_logs_svc.detect_anomalies([]) == []


def test_detect_anomalies_critical_fires(logs_path: Path) -> None:
    t0 = datetime.now(UTC)
    app_logs_svc.ingest_log(_req(severity="info", at=t0))
    # inject a critical log directly for testing
    from app.schemas.app_log import AppLog

    logs = [
        AppLog(
            id="crit-1",
            app="studio",
            service="vercel-prod",
            severity="critical",
            message="CRITICAL: disk full",
            metadata={},
            at=t0,
            source="pull",
        )
    ]
    anomalies = app_logs_svc.detect_anomalies(logs)
    kinds = [a.kind for a in anomalies]
    assert "critical_severity" in kinds


def test_detect_anomalies_error_spike(logs_path: Path) -> None:
    """Error spike: batch error rate >> historical baseline."""
    from app.schemas.app_log import AppLog

    t0 = datetime.now(UTC) - timedelta(hours=2)
    # Pre-populate with mostly info logs (low baseline)
    for i in range(20):
        app_logs_svc.ingest_log(_req(severity="info", message=f"ok {i}", at=t0))
    app_logs_svc.ingest_log(_req(severity="error", message="one error", at=t0))

    # Batch: all errors — 10x spike
    batch = [
        AppLog(
            id=f"err-{i}",
            app="studio",
            service="vercel-prod",
            severity="error",
            message=f"ERROR 500 internal {i}",
            metadata={},
            at=datetime.now(UTC),
            source="pull",
        )
        for i in range(10)
    ]
    anomalies = app_logs_svc.detect_anomalies(batch)
    kinds = [a.kind for a in anomalies]
    assert "error_rate_spike" in kinds


def test_detect_anomalies_no_spike_when_below_threshold(logs_path: Path) -> None:
    from app.schemas.app_log import AppLog

    # only 1 error, below MIN_ERRORS_FOR_SPIKE=3
    batch = [
        AppLog(
            id="e1",
            app="studio",
            service="vercel-prod",
            severity="error",
            message="single error",
            metadata={},
            at=datetime.now(UTC),
            source="pull",
        )
    ]
    anomalies = app_logs_svc.detect_anomalies(batch)
    kinds = [a.kind for a in anomalies]
    assert "error_rate_spike" not in kinds


# ---------------------------------------------------------------------------
# Pull failure handling tests
# ---------------------------------------------------------------------------


def test_pull_vercel_logs_missing_token_self_ingests_error(
    logs_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VERCEL_API_TOKEN", raising=False)
    count = app_logs_svc.pull_vercel_logs(
        team_id="", project_ids=["proj-1"], since=datetime.now(UTC)
    )
    assert count == 0
    # Error should be recorded in the log file
    page = app_logs_svc.list_logs(severity="error")
    assert any("VERCEL_API_TOKEN" in lg.message for lg in page.logs)


def test_pull_render_logs_missing_key_self_ingests_error(
    logs_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    count = app_logs_svc.pull_render_logs(service_ids=["svc-1"], since=datetime.now(UTC))
    assert count == 0
    page = app_logs_svc.list_logs(severity="error")
    assert any("RENDER_API_KEY" in lg.message for lg in page.logs)


def test_pull_vercel_logs_http_error_self_ingests(
    logs_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VERCEL_API_TOKEN", "tok-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        count = app_logs_svc.pull_vercel_logs(
            team_id="", project_ids=["proj-1"], since=datetime.now(UTC)
        )
    assert count == 0
    page = app_logs_svc.list_logs(severity="error")
    assert any("401" in lg.message for lg in page.logs)


def test_pull_render_logs_http_error_self_ingests(
    logs_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RENDER_API_KEY", "rnd-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        count = app_logs_svc.pull_render_logs(service_ids=["svc-1"], since=datetime.now(UTC))
    assert count == 0
    page = app_logs_svc.list_logs(severity="error")
    assert any("503" in lg.message for lg in page.logs)


# ---------------------------------------------------------------------------
# File-locking concurrency test
# ---------------------------------------------------------------------------


def test_concurrent_ingest_no_data_loss(logs_path: Path) -> None:
    """Multiple threads ingesting simultaneously should not lose entries."""
    n_threads = 8
    n_per_thread = 10
    errors: list[Exception] = []

    def _worker() -> None:
        try:
            for i in range(n_per_thread):
                app_logs_svc.ingest_log(
                    _req(message=f"concurrent {threading.current_thread().name} {i}")
                )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent ingest raised: {errors}"
    page = app_logs_svc.list_logs(limit=500)
    assert page.total_matched == n_threads * n_per_thread


# ---------------------------------------------------------------------------
# Schema validation test
# ---------------------------------------------------------------------------


def test_app_logs_file_schema_roundtrip(logs_path: Path) -> None:
    app_logs_svc.ingest_log(_req(message="schema test"))
    raw = json.loads(logs_path.read_text())
    parsed = AppLogsFile.model_validate(raw)
    assert parsed.log_schema == "app_logs/v1"
    assert len(parsed.logs) == 1


def test_get_last_pulled_at_returns_empty_initially(logs_path: Path) -> None:
    result = app_logs_svc.get_last_pulled_at()
    assert result == {}
