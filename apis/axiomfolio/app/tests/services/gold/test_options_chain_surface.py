"""Tests for options chain gold surface (liquidity, IV, persistence)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.market.options_chain_snapshot import OptionsChainSnapshot
from app.services.gold import options_chain_surface as ocs
from app.services.gold.options_chain_surface import (
    OptionsChainSurface,
    compute_liquidity_score,
)


@pytest.mark.no_db
def test_liquidity_score_edge_cases():
    assert compute_liquidity_score(0, 0, Decimal("0.5")) is not None
    lo = compute_liquidity_score(0, 0, Decimal("1"))
    hi = compute_liquidity_score(1_000_000, 1_000_000, Decimal("0.001"))
    assert lo is not None and hi is not None
    assert float(lo) < float(hi)


@pytest.mark.no_db
def test_liquidity_score_matches_numeric_6_4():
    v = compute_liquidity_score(10, 20, Decimal("0.04"))
    assert v is not None
    assert v == v.quantize(Decimal("0.0001"))


@pytest.mark.no_db
def test_iv_percentile_insufficient_history_returns_none():
    cur = Decimal("0.3")
    p, r = ocs._iv_percentile_rank(cur, [])
    assert p is None and r is None


@pytest.mark.no_db
def test_mid_spread_crossed_market_returns_none():
    m, a, r = ocs._mid_spread(Decimal("1.5"), Decimal("1.0"))
    assert m is None and a is None and r is None


@pytest.mark.no_db
def test_iv_percentile_with_mock_history():
    hist = [Decimal(str(x)) for x in [0.2] * 29]
    cur = Decimal("0.25")
    p, r = ocs._iv_percentile_rank(cur, hist)
    assert p is not None and r is not None
    hist30 = hist + [Decimal("0.28")]
    p2, r2 = ocs._iv_percentile_rank(cur, hist30)
    assert p2 is not None and r2 is not None


def _sample_row(**kw):
    base = {
        "symbol": "TEST",
        "expiry": date(2026, 6, 19),
        "option_type": "CALL",
        "strike": Decimal("100"),
        "bid": Decimal("1.0"),
        "ask": Decimal("1.1"),
        "open_interest": 100,
        "volume": 50,
        "implied_vol": Decimal("0.25"),
    }
    base.update(kw)
    return base


def test_idempotency_two_runs_no_duplicate_rows(db_session):
    ts = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    rows = [
        _sample_row(
            strike=Decimal("100"),
        ),
        _sample_row(
            strike=Decimal("105"),
        ),
    ]
    s = OptionsChainSurface()
    s.compute("TEST", 1, session=db_session, rows=rows, snapshot_taken_at=ts)
    c1 = (
        db_session.query(OptionsChainSnapshot)
        .filter(
            OptionsChainSnapshot.symbol == "TEST",
            OptionsChainSnapshot.snapshot_taken_at == ts,
        )
        .count()
    )
    s.compute("TEST", 1, session=db_session, rows=rows, snapshot_taken_at=ts)
    c2 = (
        db_session.query(OptionsChainSnapshot)
        .filter(
            OptionsChainSnapshot.symbol == "TEST",
            OptionsChainSnapshot.snapshot_taken_at == ts,
        )
        .count()
    )
    assert c1 == 2
    assert c2 == 2


def test_prepass_uncomparable_strike_skipped_without_killing_batch(db_session):
    """Bad strike in strike-range pass must log, skip the row, finish batch."""
    ts = datetime(2026, 1, 17, 12, 0, tzinfo=UTC)
    rows: list[dict] = [
        _sample_row(strike=Decimal("100")),
        {
            "expiry": date(2026, 6, 19),
            "option_type": "CALL",
            "strike": object(),
            "bid": Decimal("1.0"),
            "ask": Decimal("1.1"),
            "open_interest": 1,
            "volume": 1,
            "implied_vol": Decimal("0.2"),
        },
        _sample_row(strike=Decimal("101")),
    ]
    s = OptionsChainSurface()
    r = s.compute("PREP", 1, session=db_session, rows=rows, snapshot_taken_at=ts)
    assert r.contracts_processed == 3
    assert r.contracts_skipped_malformed == 1
    assert r.contracts_persisted == 2
    assert r.contracts_errored == 0


def test_malformed_row_skipped_with_counter(db_session):
    ts = datetime(2026, 1, 16, 12, 0, tzinfo=UTC)
    bad = {
        "expiry": date(2026, 6, 19),
        "strike": Decimal("99"),
    }
    rows = [
        _sample_row(strike=Decimal("100")),
        bad,
        _sample_row(strike=Decimal("102")),
    ]
    s = OptionsChainSurface()
    r = s.compute("TERR", 1, session=db_session, rows=rows, snapshot_taken_at=ts)
    assert r.contracts_processed == 3
    assert r.contracts_skipped_malformed == 1
    assert r.contracts_errored == 0
    assert r.contracts_persisted + r.contracts_errored + r.contracts_skipped_malformed == (
        r.contracts_processed
    )


def test_iv_history_query_count_scales_with_buckets_not_contracts(
    db_session,
):
    """Batched IV history: DB round-trips O(buckets), not O(contracts)."""
    sym = "IVBAT"
    ex = date(2026, 6, 19)
    ts_compute = datetime(2026, 1, 20, 12, 0, tzinfo=UTC)
    # 35+ historical IV points in the first strike decile (see wide book-end below)
    for i in range(35):
        tsn = ts_compute - timedelta(days=i + 1)
        db_session.add(
            OptionsChainSnapshot(
                symbol=sym,
                expiry=ex,
                strike=Decimal("100"),
                option_type="CALL",
                bid=Decimal("1"),
                ask=Decimal("1.1"),
                implied_vol=Decimal("0.25") + Decimal(str(i % 3)) * Decimal("0.01"),
                snapshot_taken_at=tsn,
                source="yfinance",
            )
        )
    db_session.commit()

    rows: list[dict] = []
    for j in range(20):
        # Strikes 100..109.5 in [100, 110) => first decile for 100..200
        rows.append(
            _sample_row(
                strike=Decimal("100") + Decimal(str(j)) * Decimal("0.5"),
            )
        )
    for r in rows:
        r["symbol"] = sym
        r["expiry"] = ex
    # Wide s_max from this row so strikes 100..119 share decile 0 (100..200 scale)
    rows.append(
        {
            "expiry": ex,
            "option_type": "PUT",
            "strike": Decimal("200"),
            "bid": Decimal("0.1"),
            "ask": Decimal("0.2"),
            "open_interest": 0,
            "volume": 0,
            "implied_vol": None,
        }
    )
    s = OptionsChainSurface()
    r = s.compute(
        sym,
        1,
        session=db_session,
        rows=rows,
        snapshot_taken_at=ts_compute,
    )
    # One (exp, CALL, 0) bucket; not 20*2 N+1 IV queries
    assert r.iv_history_queries == 1
    assert r.contracts_processed == 21
    assert r.contracts_persisted == 21
