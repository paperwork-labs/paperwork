"""Stage-quality determinism (Wave D / G8).

Reproduces the founder's "stage quality is always bad" symptom and asserts
the post-fix behavior: a symbol whose history has a valid stage label but
null ``current_stage_days`` (a common warmup / write-gap state) must not
be scored as ``critical``. Null ≠ bad — it's unknown (no-silent-fallback).

The pre-fix code path counted null ``current_stage_days`` as a drift
violation. With a small universe and a handful of such rows, drift_pct
instantly exceeded the 10% critical threshold, pinning the dimension red
forever. The fix separates null (reported as ``unknown_stage_days_count``)
from drift (actual counter corruption).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.market_data import MarketSnapshot, MarketSnapshotHistory
from app.services.silver.market.admin_health_service import AdminHealthService
from app.services.silver.market.market_data_service import stage_quality


def _recent_day(days_ago: int) -> date:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()


def test_valid_stage_with_null_current_days_is_not_critical(db_session):
    """Founder's scenario: symbol with current stage "2A" and an older
    snapshot row with stage "2A" (same), both with null current_stage_days.
    Pre-fix: drift_pct=100% → critical. Post-fix: unknown_stage_days_count=2,
    drift_pct=0 → healthy."""
    now = datetime.now(timezone.utc)
    db_session.add(
        MarketSnapshot(
            symbol="ZZDTRM",
            analysis_type="technical_snapshot",
            stage_label="2A",
            current_stage_days=None,
            previous_stage_label=None,
            previous_stage_days=None,
            as_of_timestamp=now,
            expiry_timestamp=now + timedelta(days=1),
            is_valid=True,
        )
    )
    for days_ago in (2, 1):
        db_session.add(
            MarketSnapshotHistory(
                symbol="ZZDTRM",
                analysis_type="technical_snapshot",
                as_of_date=_recent_day(days_ago),
                stage_label="2A",
                current_stage_days=None,
                previous_stage_label=None,
                previous_stage_days=None,
            )
        )
    db_session.commit()

    summary = stage_quality.stage_quality_summary(db_session, lookback_days=30)

    # Null current_stage_days is surfaced, not silently absorbed.
    assert summary["unknown_stage_days_count"] == 2
    # And it does NOT count as drift.
    assert summary["monotonicity_issues"] == 0
    assert summary["stage_history_rows_checked"] == 2

    # Admin health should therefore classify the dim as healthy/green —
    # matching the behaviour the founder expected (null ≠ critical).
    svc = AdminHealthService()
    dim = svc._build_stage_dimension(db_session)
    assert dim["status"] == "green", (
        f"expected green, got {dim['status']} with reason='{dim.get('reason')}'"
    )
    assert dim["unknown_stage_days_count"] == 2


def test_actual_counter_drift_still_flags_red(db_session):
    """Guardrail: post-fix, a real monotonicity violation (populated counter
    that fails to increment between consecutive trading days) must still
    flip the dim to red. We are loosening null handling only, not the
    actual drift check."""
    now = datetime.now(timezone.utc)
    db_session.add(
        MarketSnapshot(
            symbol="ZZDRIFT",
            analysis_type="technical_snapshot",
            stage_label="2A",
            current_stage_days=5,
            as_of_timestamp=now,
            expiry_timestamp=now + timedelta(days=1),
            is_valid=True,
        )
    )
    # Seed 30 consecutive trading rows all with current_stage_days=1 —
    # a real counter-freeze pathology, not just a warmup gap.
    for days_ago in range(30, 0, -1):
        db_session.add(
            MarketSnapshotHistory(
                symbol="ZZDRIFT",
                analysis_type="technical_snapshot",
                as_of_date=_recent_day(days_ago),
                stage_label="2A",
                current_stage_days=1,
            )
        )
    db_session.commit()

    summary = stage_quality.stage_quality_summary(db_session, lookback_days=60)
    assert summary["monotonicity_issues"] >= 10, (
        "real drift must still be counted"
    )


def test_empty_stage_label_is_unknown_not_invalid(db_session):
    """Null / empty stage_label on MarketSnapshot is "not yet computed",
    not "invalid". Previously it flipped invalid_stage_count > 0, which
    pinned the dim red (stage_invalid_max = 0)."""
    now = datetime.now(timezone.utc)
    db_session.add(
        MarketSnapshot(
            symbol="ZZEMP",
            analysis_type="technical_snapshot",
            stage_label=None,
            as_of_timestamp=now,
            expiry_timestamp=now + timedelta(days=1),
            is_valid=True,
        )
    )
    db_session.commit()

    summary = stage_quality.stage_quality_summary(db_session, lookback_days=30)
    assert summary["invalid_stage_count"] == 0
    assert summary["empty_label_count"] >= 1
    # Empty labels are folded into unknown_count (the honest interpretation).
    assert summary["unknown_count"] >= 1
