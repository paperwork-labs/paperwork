import pandas as pd
from datetime import datetime, timedelta, timezone

from backend.services.market.market_data_service import price_bars, quote, snapshot_builder
from backend.services.market import snapshot_builder as sb_module
from backend.models import PriceData, MarketSnapshot
from backend.models.market_data import MarketSnapshotHistory


def _make_df(dates: list[datetime], close: float = 100.0) -> pd.DataFrame:
    data = []
    for i, d in enumerate(dates):
        c = close + i
        data.append(
            {
                "Open": c,
                "High": c,
                "Low": c,
                "Close": c,
                "Volume": 1000 + i,
            }
        )
    df = pd.DataFrame(data)
    df.index = pd.DatetimeIndex(dates)
    return df


def test_persist_price_bars_delta_only(db_session):
    sym = "TEST"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    yesterday = now - timedelta(days=1)
    df = _make_df([yesterday, now], close=50.0)

    # First insert yesterday
    inserted_1 = price_bars.persist_price_bars(
        db_session, sym, df.iloc[:1], interval="1d", data_source="unit_test", is_adjusted=True
    )
    assert inserted_1 == 1
    # Delta insert should skip yesterday and insert only today
    last_date = (
        db_session.query(PriceData.date)
        .filter(PriceData.symbol == sym, PriceData.interval == "1d")
        .order_by(PriceData.date.desc())
        .limit(1)
        .scalar()
    )
    assert last_date is not None
    inserted_2 = price_bars.persist_price_bars(
        db_session,
        sym,
        df,
        interval="1d",
        data_source="unit_test",
        is_adjusted=True,
        delta_after=last_date,
    )
    assert inserted_2 == 1
    # Verify two rows exist
    count = db_session.query(PriceData).filter(PriceData.symbol == sym).count()
    assert count == 2


def test_compute_snapshot_from_db_uses_existing_fundamentals(db_session, monkeypatch):
    sym = "TESTF"
    monkeypatch.setattr(
        quote,
        "get_fundamentals_info",
        lambda *a, **kw: {},
    )
    # Seed 120 days of prices to enable indicator computation
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=130)
    dates = [start + timedelta(days=i) for i in range(120)]
    df = _make_df(dates, close=100.0)
    price_bars.persist_price_bars(
        db_session, sym, df, interval="1d", data_source="unit_test", is_adjusted=True
    )
    # Seed a previous snapshot with fundamentals
    prev = MarketSnapshot(
        symbol=sym,
        analysis_type="technical_snapshot",
        expiry_timestamp=datetime.now(timezone.utc) + timedelta(hours=12),
        sector="Technology",
        industry="Software",
        market_cap=123456789.0,
        raw_analysis={"sector": "Technology", "industry": "Software", "market_cap": 123456789.0},
    )
    db_session.add(prev)
    db_session.commit()

    snap = snapshot_builder.compute_snapshot_from_db(db_session, sym)
    assert snap
    assert snap.get("sector") == "Technology"
    assert snap.get("industry") == "Software"
    assert snap.get("market_cap") == 123456789.0


def test_compute_snapshot_from_db_populates_v2_indicators(db_session, monkeypatch):
    sym = "TESTV2"
    bm = "SPY"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(days=160)
    dates = [start + timedelta(days=i) for i in range(160)]

    # Create non-flat OHLC so ATR is non-zero.
    data = []
    for i, d in enumerate(dates):
        c = 100.0 + i * 0.1
        data.append({"Open": c, "High": c + 1.0, "Low": c - 1.0, "Close": c, "Volume": 1000 + i})
    df = pd.DataFrame(data)
    df.index = pd.DatetimeIndex(dates)
    df_newest_first = df.iloc[::-1].copy()

    price_bars.persist_price_bars(
        db_session, sym, df_newest_first, interval="1d", data_source="unit_test", is_adjusted=True
    )
    price_bars.persist_price_bars(
        db_session, bm, df_newest_first, interval="1d", data_source="unit_test", is_adjusted=True
    )

    monkeypatch.setattr(
        quote, "get_fundamentals_info",
        lambda *a, **kw: {"sector": "Test", "industry": "Test"},
    )

    snap = snapshot_builder.compute_snapshot_from_db(db_session, sym)
    assert snap
    # Canonical MAs
    assert isinstance(snap.get("sma_14"), float)
    assert isinstance(snap.get("sma_21"), float)
    assert isinstance(snap.get("sma_50"), float)
    # ATR windows
    assert isinstance(snap.get("atr_14"), float)
    assert snap.get("atr_14") > 0
    # Derived fields
    assert isinstance(snap.get("atrp_14"), float)
    assert 0.0 <= float(snap.get("range_pos_20d")) <= 100.0
    # Stage label should always be present (UNKNOWN at minimum)
    assert isinstance(snap.get("stage_label"), str)


def test_compute_snapshot_from_db_advances_stage_days_from_latest_history(db_session, monkeypatch):
    sym = "TESTSTAGE"
    bm = "SPY"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(days=120)
    dates = [start + timedelta(days=i) for i in range(120)]
    df = _make_df(dates, close=100.0)
    df_newest_first = df.iloc[::-1].copy()

    price_bars.persist_price_bars(
        db_session, sym, df_newest_first, interval="1d", data_source="unit_test", is_adjusted=True
    )
    price_bars.persist_price_bars(
        db_session, bm, df_newest_first, interval="1d", data_source="unit_test", is_adjusted=True
    )

    hist = MarketSnapshotHistory(
        symbol=sym,
        analysis_type="technical_snapshot",
        as_of_date=(now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
        stage_label="2A",
        current_stage_days=5,
        previous_stage_label="1",
        previous_stage_days=7,
    )
    db_session.add(hist)
    db_session.commit()

    monkeypatch.setattr(
        sb_module,
        "compute_weinstein_stage_from_daily",
        lambda *_args, **_kwargs: {"stage_label": "2A", "stage_slope_pct": 1.0, "stage_dist_pct": 2.0, "rs_mansfield_pct": 0.5},
    )

    snap = snapshot_builder.compute_snapshot_from_db(db_session, sym)
    assert snap.get("stage_label") == "2A"
    assert snap.get("current_stage_days") == 6
    assert snap.get("previous_stage_label") == "1"
    assert snap.get("previous_stage_days") == 7


def test_compute_snapshot_from_db_sets_previous_stage_on_transition(db_session, monkeypatch):
    sym = "TESTTRANS"
    bm = "SPY"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(days=120)
    dates = [start + timedelta(days=i) for i in range(120)]
    df = _make_df(dates, close=120.0)
    df_newest_first = df.iloc[::-1].copy()

    price_bars.persist_price_bars(
        db_session, sym, df_newest_first, interval="1d", data_source="unit_test", is_adjusted=True
    )
    price_bars.persist_price_bars(
        db_session, bm, df_newest_first, interval="1d", data_source="unit_test", is_adjusted=True
    )

    # History row must be BEFORE the snapshot's as-of date (price data max date).
    # The snapshot uses newest price bar date as snapshot_as_of_dt, and filters
    # history with `as_of_date < snapshot_as_of_dt` to avoid double-counting.
    # Using 2 days ago ensures the history row is included in the query.
    hist = MarketSnapshotHistory(
        symbol=sym,
        analysis_type="technical_snapshot",
        as_of_date=(now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0),
        stage_label="2A",
        current_stage_days=9,
        previous_stage_label="1",
        previous_stage_days=12,
    )
    db_session.add(hist)
    db_session.commit()

    monkeypatch.setattr(
        quote, "get_fundamentals_info",
        lambda *a, **kw: {"sector": "Test", "industry": "Test"},
    )
    monkeypatch.setattr(
        sb_module,
        "compute_weinstein_stage_from_daily",
        lambda *_args, **_kwargs: {"stage_label": "3", "stage_slope_pct": -1.0, "stage_dist_pct": -2.0, "rs_mansfield_pct": -0.5},
    )

    snap = snapshot_builder.compute_snapshot_from_db(db_session, sym)
    assert snap.get("stage_label") == "3"
    assert snap.get("current_stage_days") == 1
    assert snap.get("previous_stage_label") == "2A"
    assert snap.get("previous_stage_days") == 9


def test_compute_snapshot_from_db_derives_previous_stage_from_history_labels(db_session, monkeypatch):
    sym = "THISTRUN"
    bm = "SPY"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(days=140)
    dates = [start + timedelta(days=i) for i in range(140)]
    df = _make_df(dates, close=90.0)
    df_newest_first = df.iloc[::-1].copy()

    price_bars.persist_price_bars(
        db_session, sym, df_newest_first, interval="1d", data_source="unit_test", is_adjusted=True
    )
    price_bars.persist_price_bars(
        db_session, bm, df_newest_first, interval="1d", data_source="unit_test", is_adjusted=True
    )

    # History labels: 1,1,2A,2A (previous fields intentionally sparse/None)
    for i, lbl in enumerate(["1", "1", "2A", "2A"]):
        hist = MarketSnapshotHistory(
            symbol=sym,
            analysis_type="technical_snapshot",
            as_of_date=(now - timedelta(days=5 - i)).replace(hour=0, minute=0, second=0, microsecond=0),
            stage_label=lbl,
            current_stage_days=None,
            previous_stage_label=None,
            previous_stage_days=None,
        )
        db_session.add(hist)
    db_session.commit()

    monkeypatch.setattr(
        quote, "get_fundamentals_info",
        lambda *a, **kw: {"sector": "Test", "industry": "Test"},
    )
    monkeypatch.setattr(
        sb_module,
        "compute_weinstein_stage_from_daily",
        lambda *_args, **_kwargs: {"stage_label": "2A", "stage_slope_pct": 1.1, "stage_dist_pct": 0.9, "rs_mansfield_pct": 0.4},
    )

    snap = snapshot_builder.compute_snapshot_from_db(db_session, sym)
    assert snap.get("stage_label") == "2A"
    assert snap.get("current_stage_days") == 3
    assert snap.get("previous_stage_label") == "1"
    assert snap.get("previous_stage_days") == 2


def test_compute_snapshot_from_db_preserves_run_length_when_history_stage_is_unknown(
    db_session, monkeypatch
):
    sym = "TUNKNOWN"
    bm = "SPY"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(days=140)
    dates = [start + timedelta(days=i) for i in range(140)]
    df = _make_df(dates, close=95.0)
    df_newest_first = df.iloc[::-1].copy()

    price_bars.persist_price_bars(
        db_session, sym, df_newest_first, interval="1d", data_source="unit_test", is_adjusted=True
    )
    price_bars.persist_price_bars(
        db_session, bm, df_newest_first, interval="1d", data_source="unit_test", is_adjusted=True
    )

    hist = MarketSnapshotHistory(
        symbol=sym,
        analysis_type="technical_snapshot",
        as_of_date=(now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
        stage_label="UNKNOWN",
        current_stage_days=46,
        previous_stage_label="1",
        previous_stage_days=12,
    )
    db_session.add(hist)
    db_session.commit()

    monkeypatch.setattr(
        sb_module,
        "compute_weinstein_stage_from_daily",
        lambda *_args, **_kwargs: {
            "stage_label": "2A",
            "stage_slope_pct": 0.8,
            "stage_dist_pct": 1.2,
            "rs_mansfield_pct": 0.3,
        },
    )
    monkeypatch.setattr(
        quote,
        "get_fundamentals_info",
        lambda *a, **kw: {},
    )

    snap = snapshot_builder.compute_snapshot_from_db(db_session, sym)
    assert snap.get("stage_label") == "2A"
    assert snap.get("current_stage_days") == 47
    assert snap.get("previous_stage_label") == "1"
    assert snap.get("previous_stage_days") == 12


def test_derive_stage_run_fields_transition_from_unknown_history_uses_latest_row():
    class _Row:
        stage_label = "UNKNOWN"
        current_stage_days = 11
        previous_stage_label = "2A"
        previous_stage_days = 4

    out = snapshot_builder._derive_stage_run_fields(
        current_stage_label="2B",
        prior_stage_labels=["UNKNOWN", None, ""],
        latest_history_row=_Row(),
    )
    assert out["current_stage_days"] == 12
    assert out["previous_stage_label"] == "2A"
    assert out["previous_stage_days"] == 4


def test_derive_stage_run_fields_sparse_history_same_stage_advances_days():
    class _Row:
        stage_label = "2A"
        current_stage_days = 8
        previous_stage_label = "1"
        previous_stage_days = 3

    out = snapshot_builder._derive_stage_run_fields(
        current_stage_label="2A",
        prior_stage_labels=[],
        latest_history_row=_Row(),
    )
    assert out["current_stage_days"] == 9
    assert out["previous_stage_label"] == "1"
    assert out["previous_stage_days"] == 3


def test_derive_stage_run_fields_unknown_latest_with_known_priors_trusts_computed():
    """When latest history row is UNKNOWN but we have known prior labels,
    the elif branch should trust the computed run-length from the known
    sequence rather than inheriting fields from the UNKNOWN row."""

    class _Row:
        stage_label = "UNKNOWN"
        current_stage_days = 50
        previous_stage_label = "3"
        previous_stage_days = 20

    out = snapshot_builder._derive_stage_run_fields(
        current_stage_label="2A",
        prior_stage_labels=["1", "1", "1", "2A", "2A", "UNKNOWN"],
        latest_history_row=_Row(),
    )
    # The known prior sequence is [1, 1, 1, 2A, 2A] + current 2A.
    # compute_stage_run_lengths on [1, 1, 1, 2A, 2A, 2A] gives:
    #   current_stage_days=3, previous_stage_label="1", previous_stage_days=3
    # The elif branch should NOT overwrite with the UNKNOWN row's values.
    assert out["current_stage_days"] == 3
    assert out["previous_stage_label"] == "1"
    assert out["previous_stage_days"] == 3


def test_derive_stage_run_fields_unknown_latest_with_known_priors_new_stage():
    """When latest history is UNKNOWN, priors have known labels, and the
    current stage is different from the latest known prior, the computed
    run-length should reflect a stage transition."""

    class _Row:
        stage_label = "UNKNOWN"
        current_stage_days = 30
        previous_stage_label = "1"
        previous_stage_days = 10

    out = snapshot_builder._derive_stage_run_fields(
        current_stage_label="3",
        prior_stage_labels=["1", "2A", "2A", "UNKNOWN"],
        latest_history_row=_Row(),
    )
    # Known priors: [1, 2A, 2A] + current 3.
    # compute_stage_run_lengths on [1, 2A, 2A, 3]:
    #   current_stage_days=1, previous_stage_label="2A", previous_stage_days=2
    assert out["current_stage_days"] == 1
    assert out["previous_stage_label"] == "2A"
    assert out["previous_stage_days"] == 2

