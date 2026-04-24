"""Regression tests for MarketSnapshot completeness: regime, earnings calendar, volume avg, universe."""

from __future__ import annotations

import datetime as stdlib_datetime
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app.models.market_data import EarningsCalendarEvent, MarketRegime, MarketSnapshot
from app.services.silver.math.constants import CURATED_MARKET_SYMBOLS
from app.services.market.indicator_engine import compute_full_indicator_series, extract_latest_values
from app.services.market.market_data_service import price_bars, snapshot_builder
from app.services.market.snapshot_builder import next_earnings_utc_from_calendar


@pytest.fixture(autouse=True)
def _stub_fundamentals_provider(monkeypatch):
    monkeypatch.setattr(
        snapshot_builder._fundamentals,
        "get_fundamentals_info",
        lambda *a, **kw: {},
    )


def _make_ohlcv_df(dates: list[datetime], *, base: float = 100.0) -> pd.DataFrame:
    data = []
    for i, d in enumerate(dates):
        c = base + i * 0.01
        v = 1000 + i * 10
        data.append(
            {
                "Open": c,
                "High": c + 0.5,
                "Low": c - 0.5,
                "Close": c,
                "Volume": v,
            }
        )
    df = pd.DataFrame(data)
    df.index = pd.DatetimeIndex(dates)
    return df


def test_curated_universe_includes_retail_favorites():
    for sym in ("RDDT", "SOFI", "HOOD", "PLTR", "COIN", "MSTR", "TSLA"):
        assert sym in CURATED_MARKET_SYMBOLS


def test_next_earnings_utc_from_calendar_finds_earliest_future_row(db_session):
    now = datetime.now(timezone.utc)
    d0 = (now + timedelta(days=3)).date()
    d1 = (now + timedelta(days=30)).date()
    db_session.add(
        EarningsCalendarEvent(
            symbol="ZZTEST",
            report_date=d1,
            fiscal_period="Q1",
            source="unit_test",
        )
    )
    db_session.add(
        EarningsCalendarEvent(
            symbol="ZZTEST",
            report_date=d0,
            fiscal_period="Q1",
            source="unit_test",
        )
    )
    db_session.commit()

    ne = next_earnings_utc_from_calendar(db_session, "zztest")
    assert ne is not None
    assert ne.date() == d0


def test_next_earnings_utc_from_calendar_none_when_empty(db_session):
    assert next_earnings_utc_from_calendar(db_session, "NOCALX") is None


def test_next_earnings_utc_today_eod_stays_future_dated(db_session, monkeypatch):
    """Same-day report_date must not be UTC midnight (already in the past)."""
    fixed = stdlib_datetime.datetime(2024, 3, 10, 12, 0, 0, tzinfo=timezone.utc)

    class _FauxDateTime:
        @staticmethod
        def now(tz=None):
            if tz is timezone.utc:
                return fixed
            return stdlib_datetime.datetime.now(tz)

        @staticmethod
        def combine(d, t, tzinfo=None):
            return stdlib_datetime.datetime.combine(d, t, tzinfo=tzinfo)

    monkeypatch.setattr(
        "app.services.market.snapshot_builder.datetime",
        _FauxDateTime,
    )
    d_today = fixed.date()
    db_session.add(
        EarningsCalendarEvent(
            symbol="ZZSDAY",
            report_date=d_today,
            fiscal_period="Q1",
            source="unit_test",
        )
    )
    db_session.commit()
    ne = next_earnings_utc_from_calendar(db_session, "zzsday")
    assert ne is not None
    assert ne > fixed
    assert ne.hour == 23 and ne.minute == 59 and ne.second == 59


def test_next_earnings_utc_bmo_and_amc_hours(db_session):
    """time_of_day bmo / amc map to 13:30 and 21:00 UTC."""
    now = datetime.now(timezone.utc)
    d = (now + timedelta(days=14)).date()
    db_session.add(
        EarningsCalendarEvent(
            symbol="ZZBMO",
            report_date=d,
            fiscal_period="Q1",
            time_of_day="bmo",
            source="unit_test",
        )
    )
    db_session.add(
        EarningsCalendarEvent(
            symbol="ZZAMC",
            report_date=d,
            fiscal_period="Q1",
            time_of_day="amc",
            source="unit_test",
        )
    )
    db_session.commit()
    ne_b = next_earnings_utc_from_calendar(db_session, "zzbmo")
    ne_a = next_earnings_utc_from_calendar(db_session, "zzamc")
    assert ne_b is not None and ne_b.hour == 13 and ne_b.minute == 30
    assert ne_a is not None and ne_a.hour == 21 and ne_a.minute == 0


def test_recompute_earnings_metrics_counts_missing(db_session):
    sym = "EARNM"
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=130)
    dates = [start + timedelta(days=i) for i in range(120)]
    df = _make_ohlcv_df(dates)
    price_bars.persist_price_bars(
        db_session, sym, df, interval="1d", data_source="unit_test", is_adjusted=True
    )
    m: dict[str, int] = {}
    snap = snapshot_builder.compute_snapshot_from_db(
        db_session, sym, skip_fundamentals=True, recompute_metrics=m
    )
    assert snap is not None
    assert m.get("earnings_missing", 0) >= 1
    assert m.get("earnings_written", 0) == 0
    assert snap.get("next_earnings") is None


def test_recompute_earnings_metrics_counts_written(db_session):
    sym = "EARNW"
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=130)
    dates = [start + timedelta(days=i) for i in range(120)]
    df = _make_ohlcv_df(dates)
    price_bars.persist_price_bars(
        db_session, sym, df, interval="1d", data_source="unit_test", is_adjusted=True
    )
    rd = (datetime.now(timezone.utc) + timedelta(days=5)).date()
    db_session.add(
        EarningsCalendarEvent(
            symbol=sym,
            report_date=rd,
            fiscal_period="Q1",
            source="unit_test",
        )
    )
    db_session.commit()
    m: dict[str, int] = {}
    snap = snapshot_builder.compute_snapshot_from_db(
        db_session, sym, skip_fundamentals=True, recompute_metrics=m
    )
    assert snap is not None
    assert m.get("earnings_written", 0) == 1
    assert m.get("earnings_missing", 0) == 0
    assert m.get("earnings_lookup_errors", 0) == 0
    assert snap.get("next_earnings") is not None


def test_earnings_calendar_exception_preserves_next_earnings_and_increments_errors(
    db_session, monkeypatch
):
    """Transient calendar lookup must not clobber next_earnings from prior snapshot."""
    sym = "EARNPRES"
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=130)
    dates = [start + timedelta(days=i) for i in range(120)]
    df = _make_ohlcv_df(dates)
    price_bars.persist_price_bars(
        db_session, sym, df, interval="1d", data_source="unit_test", is_adjusted=True
    )
    # Aligned to MarketSnapshot.next_earnings (naive in DB) for equality.
    existing = datetime(2025, 6, 1, 15, 30, 0)
    ts = datetime.now(timezone.utc)
    db_session.add(
        MarketSnapshot(
            symbol=sym,
            analysis_type="technical_snapshot",
            analysis_timestamp=ts,
            expiry_timestamp=ts + timedelta(days=1),
            is_valid=True,
            next_earnings=existing,
        )
    )
    db_session.commit()

    def _raise(_db, _s):
        raise RuntimeError("transient calendar db")

    monkeypatch.setattr(
        "app.services.market.snapshot_builder.next_earnings_utc_from_calendar",
        _raise,
    )
    m: dict[str, int] = {}
    snap = snapshot_builder.compute_snapshot_from_db(
        db_session, sym, skip_fundamentals=True, recompute_metrics=m
    )
    assert snap is not None
    assert snap.get("next_earnings") == existing
    assert m.get("earnings_lookup_errors", 0) == 1
    assert m.get("earnings_missing", 0) == 0


def test_snapshot_from_dataframe_includes_volume_avg_20d():
    n = 260
    idx = pd.date_range("2024-01-02", periods=n, freq="B", tz="UTC")
    close = 100.0 + np.cumsum(np.random.default_rng(42).normal(0, 0.2, n))
    vol = 1_000_000 + np.random.default_rng(7).integers(0, 50_000, n)
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close + 0.1,
            "Low": close - 0.1,
            "Close": close,
            "Volume": vol,
        },
        index=idx,
    )
    out = snapshot_builder._snapshot_from_dataframe(df)
    assert out.get("volume_avg_20d") is not None
    assert float(out["volume_avg_20d"]) > 0
    assert out.get("vol_ratio") is not None


def test_compute_full_indicator_volume_avg_matches_rolling_volume_mean():
    """Guardrail: core indicator output must still expose 20d volume mean expected from OHLCV."""
    n = 60
    idx = pd.date_range("2023-01-02", periods=n, freq="B", tz="UTC")
    rng = np.random.default_rng(123)
    close = 50.0 + np.cumsum(rng.normal(0, 0.15, n))
    vol = 500_000.0 + rng.integers(0, 20_000, n).astype(float)
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.001,
            "Low": close * 0.999,
            "Close": close,
            "Volume": vol,
        },
        index=idx,
    )
    from app.services.silver.math.dataframe_utils import ensure_newest_first, ensure_oldest_first

    df_oldest = ensure_oldest_first(ensure_newest_first(df))
    series = compute_full_indicator_series(df_oldest)
    last = extract_latest_values(series)
    assert "volume_avg_20d" in last
    vavg = float(last["volume_avg_20d"])
    manual = float(df_oldest["Volume"].tail(20).mean())
    assert abs(vavg - manual) < 1e-6


def test_run_scan_overlay_writes_regime_state_from_market_regime(db_session, monkeypatch):
    from app.tasks.market import coverage

    _run = coverage._run_scan_overlay

    now = datetime.now(timezone.utc)
    db_session.add(
        MarketRegime(
            as_of_date=now,
            composite_score=2.5,
            regime_state="R4",
        )
    )
    ms = MarketSnapshot(
        symbol="REGR",
        analysis_type="technical_snapshot",
        expiry_timestamp=now + timedelta(days=1),
        is_valid=True,
        stage_label="2A",
        rs_mansfield_pct=55.0,
        ema10_dist_n=0.5,
        atrx_sma_150=0.1,
        range_pos_52w=50.0,
        ext_pct=2.0,
        atrp_14=2.0,
    )
    db_session.add(ms)
    db_session.commit()

    monkeypatch.setattr(coverage, "SessionLocal", lambda: db_session)
    res = _run()
    assert res.get("regime_state_written", 0) >= 1
    assert res.get("regime_state_missing", 0) == 0

    row = (
        db_session.query(MarketSnapshot)
        .filter(
            MarketSnapshot.symbol == "REGR",
            MarketSnapshot.analysis_type == "technical_snapshot",
        )
        .one()
    )
    assert row.regime_state == "R4"
