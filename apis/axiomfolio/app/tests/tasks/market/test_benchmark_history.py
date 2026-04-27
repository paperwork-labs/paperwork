"""Tests for ``backfill_spy_history`` (benchmark_price backfill to history)."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.models.market_data import MarketSnapshotHistory, PriceData
from app.services.silver.portfolio.analytics import BENCHMARK_ANALYSIS_TYPE
from app.tasks.market import benchmark_history as benchmark_history


def _today_naive() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=UTC)


def _unwrap_task(fn):
    return inspect.unwrap(fn)


def test_latest_history_ignores_technical_spy_without_benchmark_row(db_session):
    """A same-day ``technical_snapshot`` row must not make SPY look backfilled.

    The fast path keys only on ``BENCHMARK_ANALYSIS_TYPE`` (see
    :data:`BENCHMARK_ANALYSIS_TYPE`)."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    day = _today_naive() + timedelta(hours=12)
    db_session.add(
        MarketSnapshotHistory(
            symbol="SPY",
            analysis_type="technical_snapshot",
            as_of_date=day,
            current_price=400.0,
        )
    )
    db_session.commit()

    assert benchmark_history._latest_history_date(db_session, "SPY") is None


def test_backfill_spy_does_not_fastpath_on_technical_only_spy_row(db_session, monkeypatch):
    """Only ``benchmark_price`` coverage counts for the up-to-date short-circuit."""
    if db_session is None:
        pytest.skip("DB session unavailable")

    today = _today_naive()
    db_session.add(
        MarketSnapshotHistory(
            symbol="SPY",
            analysis_type="technical_snapshot",
            as_of_date=today + timedelta(hours=15, minutes=30),
            current_price=400.0,
        )
    )
    for d in range(0, 30):
        off = today - timedelta(days=d)
        day = datetime(off.year, off.month, off.day, tzinfo=UTC)
        db_session.add(
            PriceData(
                symbol="SPY",
                interval="1d",
                date=day,
                open_price=100,
                high_price=101,
                low_price=99,
                close_price=100.0,
                adjusted_close=100.0,
                volume=0,
                data_source="test",
                is_adjusted=True,
            )
        )
    db_session.commit()

    monkeypatch.setattr(benchmark_history, "SessionLocal", lambda: db_session)
    raw = _unwrap_task(benchmark_history.backfill_spy_history)
    out = raw(lookback_days=30)

    assert out["status"] != "skipped_fast_path"
    assert out["status"] in ("ok", "no_source_data")
    if out["status"] == "ok":
        assert out.get("written", 0) > 0


def test_latest_history_finds_benchmark_price_row(db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")

    day = datetime(2023, 6, 1, 0, 0, 0, tzinfo=UTC)
    db_session.add(
        MarketSnapshotHistory(
            symbol="SPY",
            analysis_type=BENCHMARK_ANALYSIS_TYPE,
            as_of_date=day,
            current_price=100.0,
        )
    )
    db_session.commit()
    assert benchmark_history._latest_history_date(db_session, "SPY") is not None
