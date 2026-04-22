"""Database tests for AutoOps explainer rate limits and daily cap."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.models.auto_ops_explanation import AutoOpsExplanation
from backend.services.agent.anomaly_explainer.explainer import explanation_to_dict
from backend.services.agent.anomaly_explainer.persistence import (
    DAILY_EXPLANATION_CAP_PER_KEY,
    explanation_count_today_for_key,
    recent_explanation_within,
)
from backend.services.agent.anomaly_explainer.schemas import (
    Explanation,
    RemediationStep,
    SCHEMA_VERSION,
)


def test_recent_explanation_within_uses_clamped_window(db_session) -> None:
    when = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    e = Explanation(
        schema_version=SCHEMA_VERSION,
        anomaly_id="cover:red:20260420:deadbeef",
        title="t",
        summary="s",
        root_cause_hypothesis="h",
        narrative="n",
        steps=[RemediationStep(order=1, description="d", requires_approval=False)],
        confidence=__import__("decimal").Decimal("0.5"),
        runbook_excerpts=[],
        generated_at=when,
        model="m",
        is_fallback=False,
    )
    row = AutoOpsExplanation(
        schema_version=e.schema_version,
        anomaly_id=e.anomaly_id,
        category="COVERAGE_GAP",
        severity="error",
        title=e.title,
        summary=e.summary,
        confidence=e.confidence,
        is_fallback=False,
        model=e.model,
        payload_json=explanation_to_dict(e),
        generated_at=when,
    )
    db_session.add(row)
    db_session.commit()
    found = recent_explanation_within(
        db_session,
        e.anomaly_id,
        window=timedelta(days=2),
        now=when + timedelta(hours=1),
    )
    assert found is not None
    found2 = recent_explanation_within(
        db_session,
        e.anomaly_id,
        window=timedelta(days=2),
        now=when + timedelta(hours=25),
    )
    assert found2 is None


def test_explanation_count_today_respects_cap_keys(db_session) -> None:
    when = datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc)
    ids = [
        "cover:yellow:20260420:aaaaaaaa",
        "cover:red:20260420:bbbbbbbb",
        "cover:red:20260420:cccccccc",
    ]
    for i, aid in enumerate(ids):
        e = Explanation(
            schema_version=SCHEMA_VERSION,
            anomaly_id=aid,
            title="t",
            summary="s",
            root_cause_hypothesis="h",
            narrative="n",
            steps=[RemediationStep(order=1, description="d", requires_approval=False)],
            confidence=__import__("decimal").Decimal("0.5"),
            runbook_excerpts=[],
            generated_at=when + timedelta(minutes=i),
            model="m",
            is_fallback=False,
        )
        db_session.add(
            AutoOpsExplanation(
                schema_version=e.schema_version,
                anomaly_id=aid,
                category="COVERAGE_GAP",
                severity="error",
                title=e.title,
                summary=e.summary,
                confidence=e.confidence,
                is_fallback=False,
                model=e.model,
                payload_json=explanation_to_dict(e),
                generated_at=when + timedelta(minutes=i),
            )
        )
    db_session.commit()
    n = explanation_count_today_for_key(
        db_session, "cover:critical:20260420:dddddddd", now=when + timedelta(hours=1)
    )
    assert n == DAILY_EXPLANATION_CAP_PER_KEY
