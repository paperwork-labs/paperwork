"""Tests for WS-50 anomaly detection service.

Coverage
--------
- Bootstrap (insufficient history → no alerts)
- Z-score computation with synthetic time series
- Severity threshold boundaries (medium at |z|>=2.5, high at |z|>=3.5)
- Auto-resolve when metric returns to baseline
- Atomic write: .tmp file removed, no corruption on simulated mid-write failure
"""

from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from app.schemas.anomaly_alerts import AnomalyAlert, AnomalyAlertsFile, Direction, Severity
from app.services import anomaly_detection as svc

_HIGH = svc.HIGH_THRESHOLD


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_operating_score(data_dir: Path, history: list[dict[str, Any]]) -> None:
    payload = {
        "schema": "operating_score/v1",
        "description": "test",
        "current": history[-1] if history else None,
        "history": history,
    }
    (data_dir / "operating_score.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_pr_outcomes(data_dir: Path, outcomes: list[dict[str, Any]]) -> None:
    payload = {
        "schema": "pr_outcomes/v1",
        "description": "test",
        "outcomes": outcomes,
    }
    (data_dir / "pr_outcomes.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _pos_entry(total: float, computed_at: str | None = None) -> dict[str, Any]:
    return {
        "computed_at": computed_at or "2026-01-01T00:00:00Z",
        "total": total,
        "pillars": {},
        "gates": {"l4_pass": False, "l5_pass": False, "lowest_pillar": ""},
    }


def _pr_outcome(merged_at: str, reverted: bool = False) -> dict[str, Any]:
    return {
        "pr_number": 1,
        "merged_at": merged_at,
        "merged_by_agent": "test",
        "agent_model": "test",
        "subagent_type": "test",
        "workstream_ids": [],
        "workstream_types": [],
        "outcomes": {
            "h1": None,
            "h24": {"ci_pass": True, "deploy_success": True, "reverted": reverted},
            "d7": None,
            "d14": None,
            "d30": None,
        },
    }


def test_compute_z_score_insufficient_data() -> None:
    """Fewer than MIN_HISTORY_POINTS returns None."""
    assert svc._compute_z_score([50.0, 51.0]) is None


def test_compute_z_score_zero_stddev() -> None:
    """Constant series (stddev=0) returns None — cannot compute z."""
    assert svc._compute_z_score([10.0, 10.0, 10.0, 10.0]) is None


def test_compute_z_score_normal_deviation() -> None:
    baseline = [10.0, 11.0, 9.0, 10.5, 9.5, 10.0]
    current = 10.2
    series = [*baseline, current]
    result = svc._compute_z_score(series)
    assert result is not None
    mean, stddev, z = result
    expected_mean = statistics.mean(baseline)
    expected_std = statistics.stdev(baseline)
    expected_z = (current - expected_mean) / expected_std
    assert abs(mean - expected_mean) < 1e-9
    assert abs(stddev - expected_std) < 1e-9
    assert abs(z - expected_z) < 1e-9


def test_compute_z_score_large_negative_z() -> None:
    """A value far below baseline yields a large negative z."""
    baseline = [10.0, 10.1, 9.9, 10.0, 10.1, 9.9, 10.0, 10.1, 9.9]
    current = 2.0
    series = [*baseline, current]
    result = svc._compute_z_score(series)
    assert result is not None
    _, _, z = result
    assert z < -3.5


@pytest.mark.parametrize(
    "z,expected",
    [
        (0.0, None),
        (2.4, None),
        (-2.4, None),
        (2.5, Severity.medium),
        (-2.5, Severity.medium),
        (3.4, Severity.medium),
        (-3.4, Severity.medium),
        (3.5, Severity.high),
        (-3.5, Severity.high),
        (10.0, Severity.high),
    ],
)
def test_severity_thresholds(z: float, expected: Severity | None) -> None:
    assert svc._severity_for_z(z) == expected


def test_direction_below() -> None:
    assert svc._direction_for_z(-1.0) == Direction.below


def test_direction_above() -> None:
    assert svc._direction_for_z(1.0) == Direction.above


def test_bootstrap_no_alerts(tmp_path: Path) -> None:
    """With only 2 POS history entries (< MIN_HISTORY_POINTS=3), no alerts fire."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    alerts_path = tmp_path / "anomaly_alerts.json"

    _write_operating_score(data_dir, [_pos_entry(80.0), _pos_entry(79.0)])

    with (
        patch.object(svc, "_brain_data_dir", return_value=data_dir),
        patch.object(svc, "alerts_file_path", return_value=alerts_path),
    ):
        result = svc.compute_anomalies()

    assert result.alerts == []
    assert alerts_path.exists()


def test_anomaly_fires_on_pos_drop(tmp_path: Path) -> None:
    """A dramatic POS drop triggers a high-severity alert."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    alerts_path = tmp_path / "anomaly_alerts.json"

    history = [_pos_entry(85.0 + i * 0.1) for i in range(9)]
    history.append(_pos_entry(40.0))
    _write_operating_score(data_dir, history)

    with (
        patch.object(svc, "_brain_data_dir", return_value=data_dir),
        patch.object(svc, "alerts_file_path", return_value=alerts_path),
    ):
        result = svc.compute_anomalies()

    open_alerts = [a for a in result.alerts if a.resolved_at is None]
    assert len(open_alerts) >= 1
    pos_alert = next((a for a in open_alerts if a.metric == "pos.total"), None)
    assert pos_alert is not None
    assert pos_alert.severity == Severity.high
    assert pos_alert.direction == Direction.below
    assert pos_alert.z_score < -_HIGH


def test_anomaly_fires_medium_severity(tmp_path: Path) -> None:
    """A moderate deviation triggers a medium-severity alert (|z| in [2.5, 3.5))."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    alerts_path = tmp_path / "anomaly_alerts.json"

    baseline = [10.0, 11.0, 9.0, 10.5, 9.5, 10.2, 10.8, 9.8, 10.3]
    mean_b = statistics.mean(baseline)
    std_b = statistics.stdev(baseline)
    current = mean_b + (-2.7) * std_b
    history = [_pos_entry(v) for v in baseline] + [_pos_entry(current)]
    _write_operating_score(data_dir, history)

    with (
        patch.object(svc, "_brain_data_dir", return_value=data_dir),
        patch.object(svc, "alerts_file_path", return_value=alerts_path),
    ):
        result = svc.compute_anomalies()

    pos_alert = next(
        (a for a in result.alerts if a.metric == "pos.total" and a.resolved_at is None),
        None,
    )
    assert pos_alert is not None
    assert pos_alert.severity == Severity.medium
    assert pos_alert.direction == Direction.below


def test_no_duplicate_alert_on_second_run(tmp_path: Path) -> None:
    """Running compute_anomalies twice doesn't create a second open alert for the same metric."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    alerts_path = tmp_path / "anomaly_alerts.json"

    history = [_pos_entry(85.0 + i * 0.1) for i in range(9)]
    history.append(_pos_entry(40.0))
    _write_operating_score(data_dir, history)

    with (
        patch.object(svc, "_brain_data_dir", return_value=data_dir),
        patch.object(svc, "alerts_file_path", return_value=alerts_path),
    ):
        svc.compute_anomalies()
        result2 = svc.compute_anomalies()

    pos_open = [a for a in result2.alerts if a.metric == "pos.total" and a.resolved_at is None]
    assert len(pos_open) == 1


def test_auto_resolve_returns_metric_to_baseline(tmp_path: Path) -> None:
    """An alert is resolved when the metric returns within |z|<2 after 24h."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    alerts_path = tmp_path / "anomaly_alerts.json"

    old_time = _rfc3339(datetime.now(UTC) - timedelta(hours=25))
    existing_alert = AnomalyAlert(
        id="alert-2026-01-01T00:00:00Z-pos-total",
        metric="pos.total",
        value=40.0,
        baseline_mean=85.0,
        baseline_stddev=0.3,
        z_score=-150.0,
        direction=Direction.below,
        severity=Severity.high,
        detected_at=old_time,
        resolved_at=None,
        context="test",
    )
    existing_file = AnomalyAlertsFile(alerts=[existing_alert])
    alerts_path.write_text(
        json.dumps(existing_file.model_dump(mode="json", by_alias=True), indent=2),
        encoding="utf-8",
    )

    history = [_pos_entry(85.0 + i * 0.1) for i in range(9)]
    history.append(_pos_entry(85.0))
    _write_operating_score(data_dir, history)

    with (
        patch.object(svc, "_brain_data_dir", return_value=data_dir),
        patch.object(svc, "alerts_file_path", return_value=alerts_path),
    ):
        resolved_count = svc.auto_resolve_alerts()

    assert resolved_count == 1
    file_after = AnomalyAlertsFile.model_validate(
        json.loads(alerts_path.read_text(encoding="utf-8"))
    )
    assert file_after.alerts[0].resolved_at is not None


def test_auto_resolve_not_triggered_before_24h(tmp_path: Path) -> None:
    """Alert younger than RESOLVE_HOURS is NOT auto-resolved even if metric recovered."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    alerts_path = tmp_path / "anomaly_alerts.json"

    recent_time = _rfc3339(datetime.now(UTC) - timedelta(hours=5))
    existing_alert = AnomalyAlert(
        id="alert-recent",
        metric="pos.total",
        value=40.0,
        baseline_mean=85.0,
        baseline_stddev=0.3,
        z_score=-150.0,
        direction=Direction.below,
        severity=Severity.high,
        detected_at=recent_time,
        resolved_at=None,
        context="test",
    )
    existing_file = AnomalyAlertsFile(alerts=[existing_alert])
    alerts_path.write_text(
        json.dumps(existing_file.model_dump(mode="json", by_alias=True), indent=2),
        encoding="utf-8",
    )

    history = [_pos_entry(85.0 + i * 0.1) for i in range(9)]
    history.append(_pos_entry(85.0))
    _write_operating_score(data_dir, history)

    with (
        patch.object(svc, "_brain_data_dir", return_value=data_dir),
        patch.object(svc, "alerts_file_path", return_value=alerts_path),
    ):
        resolved_count = svc.auto_resolve_alerts()

    assert resolved_count == 0


def test_atomic_write_no_tmp_file_on_success(tmp_path: Path) -> None:
    """After a successful write, the .tmp file must not exist."""
    target = tmp_path / "anomaly_alerts.json"
    file = AnomalyAlertsFile(alerts=[])

    with patch.object(svc, "alerts_file_path", return_value=target):
        svc._write_alerts_file(file)

    assert target.exists()
    tmp = Path(str(target) + ".tmp")
    assert not tmp.exists()


def test_atomic_write_content_valid_json(tmp_path: Path) -> None:
    """Written file is parseable and matches the schema."""
    target = tmp_path / "anomaly_alerts.json"
    file = AnomalyAlertsFile(alerts=[])

    with patch.object(svc, "alerts_file_path", return_value=target):
        svc._write_alerts_file(file)

    raw = json.loads(target.read_text(encoding="utf-8"))
    assert raw["schema"] == "anomaly_alerts/v1"
    assert isinstance(raw["alerts"], list)


def test_atomic_write_mid_write_failure_leaves_original(tmp_path: Path) -> None:
    """If os.replace raises, the original file is not corrupted."""
    target = tmp_path / "anomaly_alerts.json"
    original_content = '{"schema": "anomaly_alerts/v1", "description": "original", "alerts": []}\n'
    target.write_text(original_content, encoding="utf-8")

    file = AnomalyAlertsFile(alerts=[])

    with (
        patch.object(svc, "alerts_file_path", return_value=target),
        patch("app.services.anomaly_detection.os.replace", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        svc._write_alerts_file(file)

    assert target.read_text(encoding="utf-8") == original_content
