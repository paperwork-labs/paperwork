"""Tests for WS-69 PR M: Brain-owned application log ingestion and anomaly detection.

Coverage
--------
- ingest_logs: dedup by id
- query_logs: filter by app, service, severity_min, since/until, search
- cap enforcement: eviction of oldest when over 10,000
- evaluate_log_anomalies: fires once per breach window (idempotency)
- pull_vercel_logs / pull_render_logs: missing token → empty result + warning, no crash
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from app.schemas.app_logs import AppLogEntry, AppLogsFile
from app.services import app_logs as svc

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _make_entry(
    *,
    app: str = "studio",
    service: str = "studio-web",
    severity: str = "info",
    message: str = "test message",
    occurred_offset_s: float = 0.0,
    entry_id: str | None = None,
) -> AppLogEntry:
    now = _now()
    return AppLogEntry(
        id=entry_id or str(uuid.uuid4()),
        app=app,
        service=service,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        attrs={},
        source="push",
        occurred_at=now - timedelta(seconds=occurred_offset_s),
        ingested_at=now,
    )


def _write_store(data_dir: Path, entries: list[AppLogEntry]) -> None:
    store = AppLogsFile(logs=entries)
    path = data_dir / "app_logs.json"
    raw = store.model_dump(mode="json", by_alias=True)
    path.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BRAIN_APP_LOGS_JSON", str(tmp_path / "app_logs.json"))


# ---------------------------------------------------------------------------
# ingest_logs — dedup
# ---------------------------------------------------------------------------


def test_ingest_logs_adds_new_entries() -> None:
    entries = [_make_entry() for _ in range(5)]
    added = svc.ingest_logs(entries)
    assert added == 5


def test_ingest_logs_deduplicates_by_id() -> None:
    entry = _make_entry(entry_id="fixed-id-1")
    svc.ingest_logs([entry])
    added = svc.ingest_logs([entry])  # exact same id
    assert added == 0


def test_ingest_logs_partial_dedup() -> None:
    e1 = _make_entry(entry_id="id-a")
    e2 = _make_entry(entry_id="id-b")
    svc.ingest_logs([e1])
    # e1 already ingested; e2 is new
    added = svc.ingest_logs([e1, e2])
    assert added == 1


def test_ingest_logs_empty_list() -> None:
    assert svc.ingest_logs([]) == 0


# ---------------------------------------------------------------------------
# query_logs — filters
# ---------------------------------------------------------------------------


def test_query_logs_filter_by_app(tmp_path: Path) -> None:
    entries = [
        _make_entry(app="studio", service="web"),
        _make_entry(app="brain", service="api"),
        _make_entry(app="studio", service="web"),
    ]
    svc.ingest_logs(entries)

    result = svc.query_logs(app="studio")
    assert result["total_matched"] == 2
    for log in result["logs"]:
        assert log["app"] == "studio"


def test_query_logs_filter_by_service(tmp_path: Path) -> None:
    entries = [
        _make_entry(app="brain", service="api-svc"),
        _make_entry(app="brain", service="scheduler-svc"),
    ]
    svc.ingest_logs(entries)

    result = svc.query_logs(service="api-svc")
    assert result["total_matched"] == 1
    assert result["logs"][0]["service"] == "api-svc"


def test_query_logs_filter_by_severity_min() -> None:
    entries = [
        _make_entry(severity="debug", message="debug msg"),
        _make_entry(severity="info", message="info msg"),
        _make_entry(severity="warn", message="warn msg"),
        _make_entry(severity="error", message="error msg"),
        _make_entry(severity="critical", message="critical msg"),
    ]
    svc.ingest_logs(entries)

    result = svc.query_logs(severity_min="error")
    assert result["total_matched"] == 2
    for log in result["logs"]:
        assert log["severity"] in ("error", "critical")


def test_query_logs_filter_by_since_until() -> None:
    now = _now()
    old = _make_entry(occurred_offset_s=7200)  # 2h ago
    recent = _make_entry(occurred_offset_s=600)  # 10min ago
    svc.ingest_logs([old, recent])

    result = svc.query_logs(since=now - timedelta(hours=1))
    assert result["total_matched"] == 1


def test_query_logs_search_message() -> None:
    entries = [
        _make_entry(message="database connection timeout"),
        _make_entry(message="user login succeeded"),
    ]
    svc.ingest_logs(entries)

    result = svc.query_logs(search="timeout")
    assert result["total_matched"] == 1
    assert "timeout" in result["logs"][0]["message"]


def test_query_logs_pagination_cursor() -> None:
    entries = [_make_entry(occurred_offset_s=float(i)) for i in range(10)]
    svc.ingest_logs(entries)

    page1 = svc.query_logs(limit=6)
    assert len(page1["logs"]) == 6
    assert page1["next_cursor"] is not None

    page2 = svc.query_logs(limit=6, cursor=page1["next_cursor"])
    assert len(page2["logs"]) == 4


# ---------------------------------------------------------------------------
# Cap enforcement — eviction of oldest
# ---------------------------------------------------------------------------


def test_cap_enforcement_evicts_oldest(tmp_path: Path) -> None:
    now = _now()
    # Create LOG_CAP + 50 entries with distinct timestamps
    entries = [
        AppLogEntry(
            id=str(uuid.uuid4()),
            app="studio",
            service="web",
            severity="info",
            message=f"msg {i}",
            attrs={},
            source="push",
            occurred_at=now - timedelta(seconds=svc.LOG_CAP + 50 - i),
            ingested_at=now,
        )
        for i in range(svc.LOG_CAP + 50)
    ]

    svc.ingest_logs(entries)

    result = svc.query_logs(limit=1)
    # After cap enforcement, total should equal LOG_CAP
    assert result["total_matched"] == svc.LOG_CAP

    # The oldest entries should have been evicted — most recent should be preserved
    result_full = svc.query_logs(limit=svc.LOG_CAP)
    messages = {log["message"] for log in result_full["logs"]}
    # Entry 0 is oldest and should have been evicted; entry LOG_CAP+49 (newest) should survive
    assert f"msg {svc.LOG_CAP + 49}" in messages
    assert "msg 0" not in messages


# ---------------------------------------------------------------------------
# evaluate_log_anomalies — idempotency
# ---------------------------------------------------------------------------


def test_anomaly_fires_once_per_breach_window(tmp_path: Path) -> None:
    """Anomaly should fire once on spike; second call in same cooldown window should skip."""
    now = _now()
    # Build a baseline: lots of clean (info) traffic over 24 h, then a spike of errors
    baseline_entries: list[AppLogEntry] = []
    for h in range(1, 24):  # baseline hours
        for _ in range(20):
            baseline_entries.append(
                AppLogEntry(
                    id=str(uuid.uuid4()),
                    app="studio",
                    service="web",
                    severity="info",
                    message="ok",
                    attrs={},
                    source="push",
                    occurred_at=now - timedelta(hours=h, seconds=30),
                    ingested_at=now,
                )
            )
    svc.ingest_logs(baseline_entries)

    # Add a massive error spike in the current window
    spike_entries: list[AppLogEntry] = [
        AppLogEntry(
            id=str(uuid.uuid4()),
            app="studio",
            service="web",
            severity="error",
            message="500 Internal Server Error",
            attrs={},
            source="push",
            occurred_at=now - timedelta(minutes=30),
            ingested_at=now,
        )
        for _ in range(50)
    ]
    svc.ingest_logs(spike_entries)

    fired_calls: list[str] = []

    def fake_fire(**kwargs: Any) -> None:
        fired_calls.append(kwargs["app"])

    with patch.object(svc, "_fire_log_anomaly_alert", side_effect=fake_fire):
        count1 = svc.evaluate_log_anomalies()
        count2 = svc.evaluate_log_anomalies()  # should be idempotent

    assert count1 == 1, "Should fire once on first evaluation"
    assert count2 == 0, "Should not re-fire within cooldown window"
    assert len(fired_calls) == 1


def test_anomaly_no_fire_without_sufficient_history(tmp_path: Path) -> None:
    """Fewer than 3 baseline buckets → no anomaly fired."""
    svc.ingest_logs([_make_entry(severity="error") for _ in range(20)])
    fired_calls: list[str] = []

    def fake_fire(**kwargs: Any) -> None:
        fired_calls.append(kwargs["app"])

    with patch.object(svc, "_fire_log_anomaly_alert", side_effect=fake_fire):
        svc.evaluate_log_anomalies()

    assert len(fired_calls) == 0


# ---------------------------------------------------------------------------
# Missing API tokens → empty list + warning, no crash
# ---------------------------------------------------------------------------


def test_pull_vercel_logs_no_token_returns_empty(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("app.config.settings.VERCEL_API_TOKEN", "")
    with caplog.at_level(logging.WARNING):
        result = svc.pull_vercel_logs()
    assert result == []
    assert any("VERCEL_API_TOKEN" in r.message for r in caplog.records)


def test_pull_render_logs_no_token_returns_empty(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("app.config.settings.RENDER_API_KEY", "")
    with caplog.at_level(logging.WARNING):
        result = svc.pull_render_logs()
    assert result == []
    assert any("RENDER_API_KEY" in r.message for r in caplog.records)


def test_pull_vercel_logs_auth_failure_returns_empty(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("app.config.settings.VERCEL_API_TOKEN", "invalid-token")

    class _FakeResp:
        status_code = 401

        def raise_for_status(self) -> None:
            pass

    class _FakeClient:
        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def get(self, *_: object, **__: object) -> _FakeResp:
            return _FakeResp()

    with patch("httpx.Client", return_value=_FakeClient()), caplog.at_level(logging.WARNING):
        result = svc.pull_vercel_logs()
    assert result == []
    assert any(
        "401" in r.message or "auth_failure" in r.message or "Unauthorized" in r.message
        for r in caplog.records
    )


def test_pull_render_logs_auth_failure_returns_empty(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("app.config.settings.RENDER_API_KEY", "invalid-key")

    class _FakeResp:
        status_code = 401

        def raise_for_status(self) -> None:
            pass

    class _FakeClient:
        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def get(self, *_: object, **__: object) -> _FakeResp:
            return _FakeResp()

    with patch("httpx.Client", return_value=_FakeClient()), caplog.at_level(logging.WARNING):
        result = svc.pull_render_logs()
    assert result == []
    assert any(
        "401" in r.message or "auth_failure" in r.message or "Unauthorized" in r.message
        for r in caplog.records
    )
