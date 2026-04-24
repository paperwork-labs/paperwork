"""
Unit tests for :mod:`backend.services.agent.anomaly_explainer.anomaly_builder`.

These tests intentionally avoid the database fixture: the builder is a
pure function over composite-health dicts and must stay testable without
spinning up Postgres. Marked with ``pytest.mark.no_db`` at module level so
collection skips DB setup. The Celery wiring + persistence path is covered
separately in :mod:`backend.tests.test_explain_anomaly_task`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.services.agent.anomaly_explainer import (
    Anomaly,
    AnomalyCategory,
    AnomalySeverity,
)
from backend.services.agent.anomaly_explainer.anomaly_builder import (
    anomaly_from_dict,
    anomaly_to_dict,
    build_anomalies_from_health,
    build_anomaly_from_dimension,
    deterministic_id,
)

pytestmark = pytest.mark.no_db


def test_deterministic_id_is_stable_for_same_inputs():
    when = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    a = deterministic_id("coverage", "red", when=when)
    b = deterministic_id("coverage", "red", when=when)
    assert a == b
    # Two different statuses on the same day produce different ids.
    assert a != deterministic_id("coverage", "yellow", when=when)


def test_deterministic_id_carries_dimension_status_and_day():
    when = datetime(2026, 4, 18, 9, 30, tzinfo=timezone.utc)
    out = deterministic_id("stage_quality", "red", when=when)
    assert out.startswith("stage_quality:red:20260418:")
    assert len(out.split(":")[-1]) == 8  # 8-char sha256 prefix


def test_build_anomaly_from_dimension_returns_none_for_green():
    assert build_anomaly_from_dimension("coverage", {"status": "green"}) is None
    assert build_anomaly_from_dimension("coverage", {"status": "ok"}) is None


def test_build_anomaly_from_dimension_maps_status_to_severity():
    when = datetime(2026, 4, 18, tzinfo=timezone.utc)

    red = build_anomaly_from_dimension(
        "coverage", {"status": "red", "reason": "30% missing"}, detected_at=when
    )
    assert red is not None
    assert red.severity == AnomalySeverity.ERROR
    assert red.category == AnomalyCategory.COVERAGE_GAP

    yellow = build_anomaly_from_dimension(
        "stage_quality",
        {"status": "yellow", "monotonicity_violations": 12},
        detected_at=when,
    )
    assert yellow is not None
    assert yellow.severity == AnomalySeverity.WARNING
    assert yellow.category == AnomalyCategory.MONOTONICITY


def test_build_anomaly_from_dimension_unknown_dimension_falls_back_to_other():
    out = build_anomaly_from_dimension(
        "totally_new_dimension", {"status": "red", "reason": "something broke"}
    )
    assert out is not None
    assert out.category == AnomalyCategory.OTHER


def test_build_anomaly_facts_drop_unserializable_values():
    class _NotSerializable:
        def __repr__(self):
            return "<unserializable>"

    out = build_anomaly_from_dimension(
        "regime",
        {
            "status": "yellow",
            "age_hours": 5.5,
            "reason": "stale",
            "queue_depth": 17,
            # ``status`` and ``reason`` carry meta; this should still serialize.
            "raw_handle": _NotSerializable(),
            # ``private_key`` is not in the keep_keys allowlist; must be dropped.
            "private_key": "must-not-leak",
        },
    )
    assert out is not None
    assert "raw_handle" not in out.facts
    assert "private_key" not in out.facts
    assert out.facts["age_hours"] == 5.5
    assert out.facts["queue_depth"] == 17
    assert out.facts["reason"] == "stale"


def test_build_anomalies_from_health_filters_green_and_advisory():
    health = {
        "dimensions": {
            "coverage": {"status": "green"},
            "stage_quality": {"status": "red", "reason": "high unknown"},
            "regime": {"status": "yellow", "age_hours": 30},
            "ibkr_gateway": {"status": "red", "reason": "down", "advisory": True},
        }
    }

    all_anoms = build_anomalies_from_health(health, include_advisory=True)
    assert {a.facts["dimension"] for a in all_anoms} == {
        "stage_quality",
        "regime",
        "ibkr_gateway",
    }

    market_only = build_anomalies_from_health(health, include_advisory=False)
    assert {a.facts["dimension"] for a in market_only} == {
        "stage_quality",
        "regime",
    }


def test_build_anomalies_handles_missing_or_malformed_dimensions():
    # Empty / missing keys must not raise.
    assert build_anomalies_from_health({}) == []
    assert build_anomalies_from_health({"dimensions": {}}) == []
    # Non-mapping dimension entry is skipped, not crashed on.
    out = build_anomalies_from_health(
        {"dimensions": {"weird": "not-a-dict", "coverage": {"status": "red"}}}
    )
    assert {a.facts["dimension"] for a in out} == {"coverage"}


def test_anomaly_to_dict_round_trips_through_anomaly_from_dict():
    original = Anomaly(
        id="coverage:red:20260418:abc12345",
        category=AnomalyCategory.COVERAGE_GAP,
        severity=AnomalySeverity.ERROR,
        title="Coverage dimension is RED",
        facts={"dimension": "coverage", "daily_pct": 60.0},
        raw_evidence="some/log/line",
        detected_at=datetime(2026, 4, 18, 14, 0, tzinfo=timezone.utc),
    )
    payload = anomaly_to_dict(original)
    rebuilt = anomaly_from_dict(payload)
    # We compare every field individually because dataclass equality on
    # ``Anomaly`` includes tzinfo identity, and astimezone returns a new
    # object; round-trip must preserve semantic equality.
    assert rebuilt.id == original.id
    assert rebuilt.category == original.category
    assert rebuilt.severity == original.severity
    assert rebuilt.title == original.title
    assert rebuilt.facts == original.facts
    assert rebuilt.raw_evidence == original.raw_evidence
    assert rebuilt.detected_at == original.detected_at


def test_anomaly_from_dict_tolerates_unknown_enum_values():
    out = anomaly_from_dict(
        {
            "id": "x:y:20260418:00000000",
            "category": "totally_unknown_category",
            "severity": "totally_unknown_severity",
            "title": "Whatever",
        }
    )
    assert out.category == AnomalyCategory.OTHER
    assert out.severity == AnomalySeverity.WARNING


def test_anomaly_from_dict_accepts_z_suffixed_iso_timestamp():
    out = anomaly_from_dict(
        {
            "id": "x",
            "category": "stale_snapshot",
            "severity": "warning",
            "title": "Whatever",
            "detected_at": "2026-04-18T10:00:00Z",
        }
    )
    assert out.detected_at == datetime(2026, 4, 18, 10, 0, tzinfo=timezone.utc)


def test_anomaly_from_dict_falls_back_to_deterministic_id_when_missing():
    out = anomaly_from_dict(
        {
            "category": "stale_snapshot",
            "severity": "warning",
            "title": "no id provided",
        }
    )
    assert out.id  # non-empty
    # Falls back to deterministic_id with category as the dimension.
    assert out.id.startswith("stale_snapshot:")
