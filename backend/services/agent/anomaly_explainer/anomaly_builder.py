"""
Build :class:`Anomaly` objects from operational signals.

The composite-health JSON returned by
:meth:`backend.services.market.admin_health_service.AdminHealthService.get_composite_health`
is the canonical source of "what's currently broken" in the platform.
This module turns each non-green dimension into a typed :class:`Anomaly`
that :class:`AnomalyExplainer` can ground an explanation on.

Keeping this conversion in its own module (rather than inside the
explainer or the Celery task) makes it trivially testable, lets us add
new producers (broker sync alerts, regime drift, RiskGate rejections,
...) without touching the explainer, and keeps the Celery task body
small enough to read at a glance.

Design choices
--------------

* :func:`deterministic_id` makes the anomaly id a function of dimension
  + status + UTC date so a flapping dimension produces a small history
  rather than an unbounded fan-out. Operators can grep for one id across
  retries, and the persistence layer uses ``(anomaly_id, generated_at)``
  as its sort key.
* Dimension names from ``AdminHealthService`` are mapped to
  :class:`AnomalyCategory` via :data:`_DIMENSION_TO_CATEGORY`. Unknown
  dimensions fall back to :attr:`AnomalyCategory.OTHER` rather than
  raising -- new dimensions appearing in prod must never crash AutoOps.
* Severity mapping mirrors the dashboard:
  ``red -> ERROR``, ``yellow|warning -> WARNING``, ``critical -> CRITICAL``.
  ``green|ok`` rows never produce an anomaly (we filter them out).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .schemas import Anomaly, AnomalyCategory, AnomalySeverity

_DIMENSION_TO_CATEGORY: Mapping[str, AnomalyCategory] = {
    "coverage": AnomalyCategory.COVERAGE_GAP,
    "stage_quality": AnomalyCategory.MONOTONICITY,
    "jobs": AnomalyCategory.PIPELINE_FAILURE,
    "audit": AnomalyCategory.STALE_SNAPSHOT,
    "regime": AnomalyCategory.REGIME_MISALIGNMENT,
    "fundamentals": AnomalyCategory.COVERAGE_GAP,
    "data_accuracy": AnomalyCategory.INDICATOR_OUTLIER,
    "portfolio_sync": AnomalyCategory.BROKER_SYNC,
    "ibkr_gateway": AnomalyCategory.BROKER_SYNC,
}

_GREEN_STATES = {"green", "ok"}


def _coerce_severity(status: str) -> AnomalySeverity:
    """Map composite-health status strings onto the explainer severity enum.

    ``critical`` is rare today but reserved for future dimension producers
    (kill switch, broker auth lockout, ...). Unknown values default to
    ``WARNING`` so we never lose a signal due to an enum mismatch.
    """
    normalized = (status or "").strip().lower()
    if normalized == "critical":
        return AnomalySeverity.CRITICAL
    if normalized == "red":
        return AnomalySeverity.ERROR
    if normalized in {"yellow", "warning"}:
        return AnomalySeverity.WARNING
    return AnomalySeverity.WARNING


def _category_for_dimension(name: str) -> AnomalyCategory:
    return _DIMENSION_TO_CATEGORY.get(name, AnomalyCategory.OTHER)


def deterministic_id(
    dimension: str,
    status: str,
    *,
    when: Optional[datetime] = None,
) -> str:
    """Stable id for a (dimension, status, UTC-day) triple.

    Format: ``{dimension}:{status}:{YYYYMMDD}:{8-char-hash}``. The hash
    is over the same triple so the id is reproducible from inputs alone
    (handy in tests and grep-driven debugging) while still being safe to
    use as a primary key column value.
    """
    when = when or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)
    day = when.strftime("%Y%m%d")
    raw = f"{dimension}|{status}|{day}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:8]
    return f"{dimension}:{status}:{day}:{digest}"


def _title_for_dimension(dimension: str, status: str, dim_data: Mapping[str, Any]) -> str:
    reason = dim_data.get("reason") or dim_data.get("composite_reason") or ""
    suffix = f" -- {reason}" if reason else ""
    pretty = dimension.replace("_", " ").title()
    return f"{pretty} dimension is {status.upper()}{suffix}"[:200]


def _flatten_facts(dim_data: Mapping[str, Any]) -> Dict[str, Any]:
    """Pick a JSON-serializable subset of dim_data so the LLM prompt stays bounded.

    Drops any value that's not directly serializable (datetime is
    iso-converted; lists/dicts pass through; everything else is stringified).
    Keeps the keys that operators actually triage on: status, reason,
    counters, age, percentages.
    """
    keep_keys = {
        "status",
        "reason",
        "category",
        "advisory",
        "counters",
        "age_hours",
        "age_minutes",
        "daily_pct",
        "snapshot_fill_pct",
        "stale_count",
        "monotonicity_issues",
        "monotonicity_violations",
        "unknown_pct",
        "fail_count",
        "skip_count",
        "warn_count",
        "queue_depth",
    }
    out: Dict[str, Any] = {}
    for key, value in dim_data.items():
        if key not in keep_keys:
            continue
        if isinstance(value, datetime):
            out[key] = value.astimezone(timezone.utc).isoformat()
        elif isinstance(value, (str, int, float, bool, list, dict)) or value is None:
            out[key] = value
        else:
            out[key] = str(value)
    return out


def build_anomaly_from_dimension(
    dimension: str,
    dim_data: Mapping[str, Any],
    *,
    detected_at: Optional[datetime] = None,
) -> Optional[Anomaly]:
    """Return an :class:`Anomaly` for one composite-health dimension, or None if green.

    Treats ``advisory: True`` (broker dimensions in ``market_only_mode``)
    as worth still surfacing -- operators want the explanation even when
    the failure isn't pulled into the composite score.
    """
    status = (dim_data.get("status") or "").strip().lower()
    if status in _GREEN_STATES:
        return None
    severity = _coerce_severity(status)
    category = _category_for_dimension(dimension)
    detected_at = detected_at or datetime.now(timezone.utc)
    return Anomaly(
        id=deterministic_id(dimension, status, when=detected_at),
        category=category,
        severity=severity,
        title=_title_for_dimension(dimension, status, dim_data),
        facts={
            "dimension": dimension,
            **_flatten_facts(dim_data),
        },
        raw_evidence="",
        detected_at=detected_at,
    )


def build_anomalies_from_health(
    health: Mapping[str, Any],
    *,
    detected_at: Optional[datetime] = None,
    include_advisory: bool = True,
) -> List[Anomaly]:
    """Convert a full composite-health payload into a list of anomalies.

    ``include_advisory=False`` drops broker-only dimensions when the
    instance is in market-only mode, matching the rule-based remediator's
    skip behavior.
    """
    dimensions = health.get("dimensions") or {}
    detected_at = detected_at or datetime.now(timezone.utc)
    out: List[Anomaly] = []
    for name, data in dimensions.items():
        if not isinstance(data, Mapping):
            continue
        if not include_advisory and data.get("advisory"):
            continue
        anomaly = build_anomaly_from_dimension(name, data, detected_at=detected_at)
        if anomaly is not None:
            out.append(anomaly)
    return out


def anomaly_from_dict(payload: Mapping[str, Any]) -> Anomaly:
    """Reconstruct an :class:`Anomaly` from a JSON-serializable dict.

    Used by Celery tasks that receive an anomaly over the wire (Redis
    broker, REST submission). Tolerates missing optional fields and
    coerces enum strings to their typed values.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("anomaly_from_dict requires a mapping payload")
    try:
        category = AnomalyCategory(payload.get("category", AnomalyCategory.OTHER.value))
    except ValueError:
        category = AnomalyCategory.OTHER
    try:
        severity = AnomalySeverity(payload.get("severity", AnomalySeverity.WARNING.value))
    except ValueError:
        severity = AnomalySeverity.WARNING
    detected_at_raw = payload.get("detected_at")
    detected_at: Optional[datetime] = None
    if isinstance(detected_at_raw, datetime):
        detected_at = detected_at_raw
    elif isinstance(detected_at_raw, str) and detected_at_raw:
        try:
            detected_at = datetime.fromisoformat(detected_at_raw.replace("Z", "+00:00"))
        except ValueError:
            detected_at = None
    facts = payload.get("facts") or {}
    if not isinstance(facts, Mapping):
        facts = {}
    return Anomaly(
        id=str(payload.get("id") or "").strip() or deterministic_id(
            str(payload.get("category", "other")), "unknown"
        ),
        category=category,
        severity=severity,
        title=str(payload.get("title") or "Untitled anomaly")[:200],
        facts=dict(facts),
        raw_evidence=str(payload.get("raw_evidence") or "")[:8000],
        detected_at=detected_at,
    )


def anomaly_to_dict(anomaly: Anomaly) -> Dict[str, Any]:
    """JSON-friendly representation suitable for Celery payloads / API responses."""
    detected_at = anomaly.detected_at
    if detected_at is not None:
        if detected_at.tzinfo is None:
            detected_at = detected_at.replace(tzinfo=timezone.utc)
        detected_iso: Optional[str] = detected_at.astimezone(timezone.utc).isoformat()
    else:
        detected_iso = None
    return {
        "id": anomaly.id,
        "category": anomaly.category.value,
        "severity": anomaly.severity.value,
        "title": anomaly.title,
        "facts": dict(anomaly.facts),
        "raw_evidence": anomaly.raw_evidence,
        "detected_at": detected_iso,
    }


__all__ = [
    "anomaly_from_dict",
    "anomaly_to_dict",
    "build_anomalies_from_health",
    "build_anomaly_from_dimension",
    "deterministic_id",
]


def _iter_dimensions(health: Mapping[str, Any]) -> Iterable[str]:
    """Helper preserved for callers that want to iterate dimension names."""
    return list((health.get("dimensions") or {}).keys())
