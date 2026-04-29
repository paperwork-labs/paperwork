"""Anomaly detection service — z-score-based metric monitoring (WS-50, Phase D).

Ingests recent metrics (DORA via pr_outcomes.json, POS pillar values,
Brain freshness, PR outcome dispersion) and emits anomaly alerts when a
metric deviates significantly from its rolling 7-day baseline.

medallion: ops

Thresholds
----------
|z| < 2.5   → no alert (or low, ignored)
|z| >= 2.5  → medium severity
|z| >= 3.5  → high severity

Minimum history: MIN_HISTORY_POINTS samples required before any alerts fire.
Auto-resolve: if a metric's |z| < 2.0 and has been below that for RESOLVE_HOURS
hours, set resolved_at on open alerts for that metric.
"""

from __future__ import annotations

import json
import logging
import math
import os
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.anomaly_alerts import AnomalyAlert, AnomalyAlertsFile, Direction, Severity

logger = logging.getLogger(__name__)

_ENV_ALERTS_JSON = "BRAIN_ANOMALY_ALERTS_JSON"
_TMP_SUFFIX = ".tmp"

MIN_HISTORY_POINTS = 3
MEDIUM_THRESHOLD = 2.5
HIGH_THRESHOLD = 3.5
RESOLVE_ABS_Z = 2.0
RESOLVE_HOURS = 24


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _brain_data_dir() -> Path:
    env = os.environ.get("BRAIN_DATA_DIR", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent / "data"


def alerts_file_path() -> Path:
    env = os.environ.get(_ENV_ALERTS_JSON, "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "anomaly_alerts.json"


# ---------------------------------------------------------------------------
# Atomic I/O
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + _TMP_SUFFIX)
    raw = json.dumps(data, indent=2, sort_keys=True) + "\n"
    tmp.write_text(raw, encoding="utf-8")
    os.replace(tmp, path)


def read_alerts_file() -> AnomalyAlertsFile:
    """Read ``anomaly_alerts.json``; return empty file if missing or corrupt."""
    path = alerts_file_path()
    if not path.is_file():
        return AnomalyAlertsFile()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return AnomalyAlertsFile()
        return AnomalyAlertsFile.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("anomaly_detection: could not read %s — %s; returning empty", path, exc)
        return AnomalyAlertsFile()


def _write_alerts_file(file: AnomalyAlertsFile) -> None:
    path = alerts_file_path()
    _atomic_write_json(path, file.model_dump(mode="json", by_alias=True))


# ---------------------------------------------------------------------------
# Metric gathering
# ---------------------------------------------------------------------------


def _read_json_file(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _gather_pos_series(data_dir: Path) -> dict[str, list[float]]:
    """Return time-ordered series per POS metric from operating_score.json history."""
    raw = _read_json_file(data_dir / "operating_score.json")
    if not isinstance(raw, dict):
        return {}
    history: list[Any] = raw.get("history") or []
    series: dict[str, list[float]] = {}
    for entry in history:
        if not isinstance(entry, dict):
            continue
        total = entry.get("total")
        if isinstance(total, (int, float)):
            series.setdefault("pos.total", []).append(float(total))
        pillars = entry.get("pillars") or {}
        if isinstance(pillars, dict):
            for pid, pdata in pillars.items():
                if isinstance(pdata, dict):
                    score = pdata.get("score")
                    if isinstance(score, (int, float)):
                        series.setdefault(f"pos.{pid}", []).append(float(score))
    return series


def _gather_pr_outcome_series(data_dir: Path) -> dict[str, list[float]]:
    """Return PR-outcome-derived metric series (weekly merge count, revert rate)."""
    raw = _read_json_file(data_dir / "pr_outcomes.json")
    if not isinstance(raw, dict):
        return {}
    outcomes: list[Any] = raw.get("outcomes") or []
    if not outcomes:
        return {}

    # Bucket merges by ISO week → weekly merge count
    weekly_merges: dict[str, int] = {}
    weekly_reverts: dict[str, int] = {}
    for row in outcomes:
        if not isinstance(row, dict):
            continue
        merged_at_raw = row.get("merged_at")
        if not isinstance(merged_at_raw, str):
            continue
        try:
            s = merged_at_raw.strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            merged_dt = datetime.fromisoformat(s)
        except ValueError:
            continue
        week_key = merged_dt.strftime("%G-W%V")
        weekly_merges[week_key] = weekly_merges.get(week_key, 0) + 1
        h24_block = (row.get("outcomes") or {}).get("h24") or {}
        if isinstance(h24_block, dict) and h24_block.get("reverted"):
            weekly_reverts[week_key] = weekly_reverts.get(week_key, 0) + 1

    if not weekly_merges:
        return {}

    sorted_weeks = sorted(weekly_merges)
    merge_counts = [float(weekly_merges[w]) for w in sorted_weeks]
    revert_rates = [
        (weekly_reverts.get(w, 0) / max(weekly_merges[w], 1)) * 100.0 for w in sorted_weeks
    ]
    return {
        "pr_outcomes.weekly_merge_count": merge_counts,
        "pr_outcomes.weekly_revert_rate_pct": revert_rates,
    }


def _gather_dora_series(data_dir: Path) -> dict[str, list[float]]:
    """Return DORA metric series from dora_metrics.json if present."""
    raw = _read_json_file(data_dir / "dora_metrics.json")
    if not isinstance(raw, dict):
        return {}
    series: dict[str, list[float]] = {}
    runs: list[Any] = raw.get("runs") or []
    for run in runs:
        if not isinstance(run, dict):
            continue
        df = run.get("deploy_frequency_per_week")
        if isinstance(df, (int, float)) and not math.isnan(df):
            series.setdefault("dora.deploy_frequency_per_week", []).append(float(df))
        cfr = run.get("change_failure_rate_pct")
        if isinstance(cfr, (int, float)) and not math.isnan(cfr):
            series.setdefault("dora.change_failure_rate_pct", []).append(float(cfr))
        mttr = run.get("mttr_hours")
        if isinstance(mttr, (int, float)) and not math.isnan(mttr):
            series.setdefault("dora.mttr_hours", []).append(float(mttr))
    return series


def _gather_all_series(data_dir: Path) -> dict[str, list[float]]:
    all_series: dict[str, list[float]] = {}
    for getter in (_gather_pos_series, _gather_pr_outcome_series, _gather_dora_series):
        try:
            all_series.update(getter(data_dir))
        except Exception:
            logger.exception("anomaly_detection: metric gatherer %s failed", getter.__name__)
    return all_series


# ---------------------------------------------------------------------------
# Z-score computation
# ---------------------------------------------------------------------------


def _compute_z_score(series: list[float]) -> tuple[float, float, float] | None:
    """Compute (mean, stddev, z_score) for the *last* value using the prior values.

    Returns ``None`` if there are fewer than ``MIN_HISTORY_POINTS`` total values
    (including the current observation) or if stddev is zero.

    The rolling baseline uses all observations *except* the latest.
    """
    if len(series) < MIN_HISTORY_POINTS:
        return None
    baseline = series[:-1]
    current = series[-1]
    mean = statistics.mean(baseline)
    if len(baseline) < 2:
        return None
    stddev = statistics.stdev(baseline)
    if stddev == 0.0:
        return None
    z = (current - mean) / stddev
    return mean, stddev, z


def _severity_for_z(z: float) -> Severity | None:
    abs_z = abs(z)
    if abs_z >= HIGH_THRESHOLD:
        return Severity.high
    if abs_z >= MEDIUM_THRESHOLD:
        return Severity.medium
    return None


def _direction_for_z(z: float) -> Direction:
    return Direction.below if z < 0 else Direction.above


def _now_utc_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _alert_id(metric: str, now_str: str) -> str:
    slug = metric.replace(".", "-").replace("_", "-")
    return f"alert-{now_str}-{slug}"


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def compute_anomalies() -> AnomalyAlertsFile:
    """Gather metrics, compute z-scores, update alert file atomically.

    Returns the updated ``AnomalyAlertsFile``.
    """
    data_dir = _brain_data_dir()
    all_series = _gather_all_series(data_dir)

    existing = read_alerts_file()
    # Index open alerts by metric so we can skip re-creating identical ones
    open_by_metric: dict[str, AnomalyAlert] = {
        a.metric: a for a in existing.alerts if a.resolved_at is None
    }

    now_str = _now_utc_str()
    new_alerts: list[AnomalyAlert] = list(existing.alerts)

    for metric, series in all_series.items():
        result = _compute_z_score(series)
        if result is None:
            continue
        mean, stddev, z_score = result
        severity = _severity_for_z(z_score)
        if severity is None:
            continue
        current_value = series[-1]
        direction = _direction_for_z(z_score)

        if metric in open_by_metric:
            # Already have an open alert for this metric — skip duplicate
            continue

        alert = AnomalyAlert(
            id=_alert_id(metric, now_str),
            metric=metric,
            value=round(current_value, 6),
            baseline_mean=round(mean, 6),
            baseline_stddev=round(stddev, 6),
            z_score=round(z_score, 4),
            direction=direction,
            severity=severity,
            detected_at=now_str,
            resolved_at=None,
            context=(
                f"{metric} {'dropped' if direction == Direction.below else 'spiked'} "
                f"to {current_value:.4g} (baseline mean {mean:.4g} ± {stddev:.4g}, "
                f"z={z_score:.2f})"
            ),
        )
        new_alerts.append(alert)
        logger.info(
            "anomaly_detection: new alert metric=%s severity=%s z=%.2f",
            metric,
            severity.value,
            z_score,
        )

    updated = AnomalyAlertsFile(alerts=new_alerts)
    _write_alerts_file(updated)
    return updated


def auto_resolve_alerts() -> int:
    """Resolve open alerts whose metric has returned to |z| < ``RESOLVE_ABS_Z``.

    An alert is marked resolved only if the current z-score is below the
    threshold AND the alert has been open for at least ``RESOLVE_HOURS`` hours
    (giving the metric time to stabilise).

    Returns the number of alerts newly resolved.
    """
    data_dir = _brain_data_dir()
    all_series = _gather_all_series(data_dir)
    existing = read_alerts_file()
    now = datetime.now(UTC)
    now_str = _now_utc_str()

    resolved_count = 0
    updated_alerts: list[AnomalyAlert] = []

    for alert in existing.alerts:
        if alert.resolved_at is not None:
            updated_alerts.append(alert)
            continue

        series = all_series.get(alert.metric)
        if not series:
            updated_alerts.append(alert)
            continue

        result = _compute_z_score(series)
        if result is None:
            updated_alerts.append(alert)
            continue

        _, _, z_score = result

        # Check age of alert
        try:
            detected_dt = alert.detected_at_dt
        except ValueError:
            updated_alerts.append(alert)
            continue

        age_hours = (now - detected_dt).total_seconds() / 3600.0
        if abs(z_score) < RESOLVE_ABS_Z and age_hours >= RESOLVE_HOURS:
            resolved_alert = alert.model_copy(update={"resolved_at": now_str})
            updated_alerts.append(resolved_alert)
            resolved_count += 1
            logger.info(
                "anomaly_detection: resolved alert %s (z=%.2f after %.1fh)",
                alert.id,
                z_score,
                age_hours,
            )
        else:
            updated_alerts.append(alert)

    if resolved_count > 0:
        updated = AnomalyAlertsFile(alerts=updated_alerts)
        _write_alerts_file(updated)

    return resolved_count
