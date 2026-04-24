"""Unit tests for ``app.services.silver.market.historical_iv_service``.

Covers the three moving parts of the G5 ingest:

1.  ``compute_hv`` -- population stdev of log returns, annualized by
    sqrt(252). The math is pinned against a hand-computed fixture so
    drift is loud.
2.  ``atm_iv_from_yahoo`` -- picks the correct strike (ATM), reuses
    ``_parse_iv``, returns ``None`` when no window bucket is in range.
3.  ``atm_iv_from_ibkr`` -- flattens the IBKR chain shape correctly.

``persist_iv_sample`` is exercised indirectly via the snapshot-task test.
The silent-zero rule for ``iv_hv_spread`` has a focused unit test here.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import pytest

from app.services.silver.market.historical_iv_service import (
    IVSample,
    _normalize_ibkr_chain,
    _pair_rows_by_expiry_strike,
    _pick_atm_mid_iv,
    _pick_iv_for_tenor,
    atm_iv_from_ibkr,
    atm_iv_from_yahoo,
    compute_hv,
    last_trading_day,
    persist_iv_sample,
)

pytestmark = pytest.mark.no_db


# ---------------------------------------------------------------------------
# HV math
# ---------------------------------------------------------------------------


class _FakeRow:
    def __init__(self, d: date, c: float) -> None:
        self.date = d
        self.close_price = c

    # SQLAlchemy rows act like 2-tuples when iterated via ``.all()`` with
    # multiple columns selected; the real code path in
    # ``compute_hv`` uses ``r[1]`` indexing.
    def __iter__(self):  # pragma: no cover
        yield self.date
        yield self.close_price

    def __getitem__(self, i: int):
        if i == 0:
            return self.date
        if i == 1:
            return self.close_price
        raise IndexError(i)


class _FakeQuery:
    """Minimal chainable stand-in for a SQLAlchemy query used by
    ``compute_hv``. Returns exactly the rows handed in, in newest-first
    order (matching ``.order_by(PriceData.date.desc()).limit(N).all()``).
    """

    def __init__(self, rows_desc: list[_FakeRow]) -> None:
        self._rows = list(rows_desc)
        self._limit: int | None = None

    def filter(self, *_args, **_kwargs) -> "_FakeQuery":
        return self

    def order_by(self, *_args, **_kwargs) -> "_FakeQuery":
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit = int(n)
        return self

    def all(self) -> list[_FakeRow]:
        if self._limit is None:
            return list(self._rows)
        return list(self._rows[: self._limit])


class _FakeSession:
    def __init__(self, rows_desc: list[_FakeRow]) -> None:
        self._rows = rows_desc

    def query(self, *_args, **_kwargs) -> _FakeQuery:
        return _FakeQuery(self._rows)


def _daily_closes(as_of: date, closes_desc: list[float]) -> list[_FakeRow]:
    """Build fake rows ordered newest-first (one per calendar day)."""
    rows: list[_FakeRow] = []
    d = as_of
    for i, c in enumerate(closes_desc):
        rows.append(_FakeRow(d - timedelta(days=i + 1), c))
    return rows


def test_compute_hv_matches_hand_computed_fixture() -> None:
    """Known fixture: 20 log returns of a ``*1.01`` then ``/1.01``
    alternating series -> log returns alternate +ln(1.01) and -ln(1.01).
    The population stdev of that sequence is exactly ln(1.01); the
    annualized HV is ln(1.01) * sqrt(252).
    """
    as_of = date(2026, 4, 22)
    # 21 closes -> 20 log returns.
    closes_chron: list[float] = [100.0]
    up = True
    for _ in range(20):
        closes_chron.append(closes_chron[-1] * (1.01 if up else 1 / 1.01))
        up = not up
    # Newest-first for the fake DB.
    closes_desc = list(reversed(closes_chron))
    rows = [
        _FakeRow(as_of - timedelta(days=i + 1), c)
        for i, c in enumerate(closes_desc)
    ]
    db = _FakeSession(rows)

    hv = compute_hv("TST", as_of, 20, db)  # type: ignore[arg-type]
    assert hv is not None
    expected = math.log(1.01) * math.sqrt(252)
    assert abs(hv - expected) < 1e-9, (
        f"HV math drift: expected {expected:.9f}, got {hv:.9f}"
    )


def test_compute_hv_returns_none_when_insufficient_bars() -> None:
    as_of = date(2026, 4, 22)
    # Only 10 bars -> <21 closes required for a 20-day return window.
    rows = _daily_closes(as_of, [100.0 + i for i in range(10)])
    db = _FakeSession(rows)
    assert compute_hv("TST", as_of, 20, db) is None  # type: ignore[arg-type]


def test_compute_hv_rejects_nonpositive_close() -> None:
    as_of = date(2026, 4, 22)
    closes_desc = [100.0] * 21
    closes_desc[5] = 0.0  # unusable
    rows = _daily_closes(as_of, closes_desc)
    db = _FakeSession(rows)
    assert compute_hv("TST", as_of, 20, db) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ATM picker
# ---------------------------------------------------------------------------


def _chain_row(expiry: date, otype: str, strike: float, iv: float) -> dict:
    return {
        "expiry": expiry,
        "option_type": otype,
        "strike": strike,
        "implied_vol": iv,
    }


def test_atm_picker_chooses_strike_nearest_spot() -> None:
    expiry = date(2026, 5, 15)
    rows = [
        _chain_row(expiry, "CALL", 95.0, 0.40),
        _chain_row(expiry, "PUT", 95.0, 0.42),
        _chain_row(expiry, "CALL", 100.0, 0.30),
        _chain_row(expiry, "PUT", 100.0, 0.32),
        _chain_row(expiry, "CALL", 105.0, 0.25),
        _chain_row(expiry, "PUT", 105.0, 0.27),
    ]
    paired = _pair_rows_by_expiry_strike(rows)
    mid = _pick_atm_mid_iv(paired, spot=101.0)
    # Spot 101 is closest to strike 100 -> mid of (0.30, 0.32)
    assert mid is not None
    assert abs(mid - 0.31) < 1e-9


def test_atm_picker_single_leg_returns_that_leg() -> None:
    expiry = date(2026, 5, 15)
    rows = [_chain_row(expiry, "CALL", 100.0, 0.35)]  # no put
    paired = _pair_rows_by_expiry_strike(rows)
    mid = _pick_atm_mid_iv(paired, spot=100.0)
    assert mid is not None
    assert abs(mid - 0.35) < 1e-9


def test_pick_iv_for_tenor_respects_dte_window() -> None:
    as_of = date(2026, 4, 22)
    # One expiry inside window, one outside.
    near = as_of + timedelta(days=30)
    far = as_of + timedelta(days=365)
    rows = [
        _chain_row(near, "CALL", 100.0, 0.30),
        _chain_row(near, "PUT", 100.0, 0.32),
        _chain_row(far, "CALL", 100.0, 0.60),
        _chain_row(far, "PUT", 100.0, 0.62),
    ]
    mid = _pick_iv_for_tenor(
        rows, as_of, spot=100.0, target_dte=30, dte_min=7, dte_max=45
    )
    assert mid is not None
    assert abs(mid - 0.31) < 1e-9  # near expiry, not far

    # With too-tight window we should get nothing.
    mid_none = _pick_iv_for_tenor(
        rows, as_of, spot=100.0, target_dte=30, dte_min=60, dte_max=90
    )
    # Far expiry is inside [60, 90]? (365 DTE is NOT), near (30) is NOT.
    # Expected None.
    assert mid_none is None


def test_pick_iv_for_tenor_returns_none_for_empty_chain() -> None:
    as_of = date(2026, 4, 22)
    assert (
        _pick_iv_for_tenor([], as_of, spot=100.0, target_dte=30, dte_min=7, dte_max=45)
        is None
    )


# ---------------------------------------------------------------------------
# Yahoo path (integration via injected fetcher)
# ---------------------------------------------------------------------------


def test_atm_iv_from_yahoo_uses_injected_fetcher_and_spot() -> None:
    as_of = date(2026, 4, 22)
    expiry = as_of + timedelta(days=28)

    def fake_fetcher(symbol: str, *, max_dte_days: int) -> list[dict]:
        assert symbol == "AAPL"
        return [
            {"expiry": expiry, "option_type": "CALL", "strike": 195.0, "implied_vol": 0.32},
            {"expiry": expiry, "option_type": "PUT", "strike": 195.0, "implied_vol": 0.30},
            {"expiry": expiry, "option_type": "CALL", "strike": 200.0, "implied_vol": 0.26},
            {"expiry": expiry, "option_type": "PUT", "strike": 200.0, "implied_vol": 0.28},
        ]

    sample = atm_iv_from_yahoo(
        "AAPL",
        as_of,
        chain_fetcher=fake_fetcher,
        spot_override=200.5,
        dte_min=7,
        dte_max=45,
    )
    assert sample is not None
    assert sample.source == "yahoo"
    assert sample.iv_30d is not None
    assert abs(sample.iv_30d - 0.27) < 1e-9  # mid of (0.26, 0.28)


def test_atm_iv_from_yahoo_returns_none_without_spot() -> None:
    as_of = date(2026, 4, 22)
    sample = atm_iv_from_yahoo(
        "AAPL",
        as_of,
        chain_fetcher=lambda s, *, max_dte_days: [],
        spot_override=None,  # no spot available
        dte_min=7,
        dte_max=45,
    )
    assert sample is None


# ---------------------------------------------------------------------------
# IBKR path
# ---------------------------------------------------------------------------


def test_normalize_ibkr_chain_flattens_correctly() -> None:
    chain = {
        "expirations": ["20260515"],
        "chains": {
            "20260515": {
                "calls": [
                    {"strike": 100.0, "iv": 0.30},
                    {"strike": 105.0, "iv": 0.28},
                ],
                "puts": [
                    {"strike": 100.0, "iv": 0.32},
                    {"strike": 105.0, "iv": 0.30},
                ],
            }
        },
    }
    rows = _normalize_ibkr_chain(chain)
    # 4 rows: 2 calls + 2 puts, all on the 2026-05-15 expiry.
    assert len(rows) == 4
    assert {r["option_type"] for r in rows} == {"CALL", "PUT"}
    assert all(r["expiry"] == date(2026, 5, 15) for r in rows)


def test_normalize_ibkr_chain_skips_bad_rows() -> None:
    chain = {
        "chains": {
            "bad-date": {"calls": [], "puts": []},
            "20260515": {
                "calls": [
                    {"strike": 100.0, "iv": None},  # dropped (no iv)
                    {"strike": 105.0, "iv": 0.28},
                ],
                "puts": [
                    {"strike": 100.0, "iv": 0.32},
                    {"strike": "NaN", "iv": 0.30},  # dropped (strike parse)
                ],
            },
        },
    }
    rows = _normalize_ibkr_chain(chain)
    assert len(rows) == 2  # one CALL + one PUT survive
    assert all(r["implied_vol"] is not None for r in rows)


def test_atm_iv_from_ibkr_picks_atm_mid() -> None:
    as_of = date(2026, 4, 22)
    expiry_str = (as_of + timedelta(days=30)).strftime("%Y%m%d")

    def fake_fetcher(symbol: str) -> dict:
        return {
            "expirations": [expiry_str],
            "chains": {
                expiry_str: {
                    "calls": [
                        {"strike": 95.0, "iv": 0.45},
                        {"strike": 100.0, "iv": 0.30},
                    ],
                    "puts": [
                        {"strike": 95.0, "iv": 0.47},
                        {"strike": 100.0, "iv": 0.32},
                    ],
                }
            },
        }

    sample = atm_iv_from_ibkr(
        "SPY",
        as_of,
        chain_fetcher=fake_fetcher,
        spot_override=100.5,
        dte_min=7,
        dte_max=45,
    )
    assert sample is not None
    assert sample.source == "ibkr"
    assert sample.iv_30d is not None
    assert abs(sample.iv_30d - 0.31) < 1e-9


def test_atm_iv_from_ibkr_empty_chain_returns_none() -> None:
    as_of = date(2026, 4, 22)
    sample = atm_iv_from_ibkr(
        "SPY",
        as_of,
        chain_fetcher=lambda _sym: {"expirations": [], "chains": {}},
        spot_override=100.0,
        dte_min=7,
        dte_max=45,
    )
    assert sample is None


# ---------------------------------------------------------------------------
# last_trading_day
# ---------------------------------------------------------------------------


def test_last_trading_day_skips_weekends() -> None:
    sat = date(2026, 4, 18)  # Saturday
    sun = date(2026, 4, 19)  # Sunday
    mon = date(2026, 4, 20)  # Monday
    fri = date(2026, 4, 17)  # Friday
    assert last_trading_day(sat) == fri
    assert last_trading_day(sun) == fri
    assert last_trading_day(mon) == mon


# ---------------------------------------------------------------------------
# persist_iv_sample -- silent-zero guard
# ---------------------------------------------------------------------------


class _RecordingSession:
    """Captures the row SQLAlchemy would add -- no real DB needed."""

    def __init__(self) -> None:
        self.added: list = []

    def query(self, *_args, **_kwargs) -> "_RecordingSession":
        return self

    def filter(self, *_args, **_kwargs) -> "_RecordingSession":
        return self

    def first(self):
        return None

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        pass


def test_persist_iv_sample_sets_spread_only_when_both_present() -> None:
    sample = IVSample(
        symbol="AAPL",
        date=date(2026, 4, 22),
        iv_30d=0.35,
        iv_60d=0.37,
        source="yahoo",
    )
    db = _RecordingSession()
    row = persist_iv_sample(sample, hv_20d=0.30, hv_60d=0.28, db=db)  # type: ignore[arg-type]
    assert row.iv_hv_spread is not None
    assert abs(row.iv_hv_spread - (0.35 - 0.30)) < 1e-9


def test_persist_iv_sample_spread_is_none_when_hv_missing() -> None:
    sample = IVSample(
        symbol="AAPL",
        date=date(2026, 4, 22),
        iv_30d=0.35,
        iv_60d=None,
        source="yahoo",
    )
    db = _RecordingSession()
    row = persist_iv_sample(sample, hv_20d=None, hv_60d=None, db=db)  # type: ignore[arg-type]
    # Null-safe spread is the whole point of G5's silent-zero fix.
    assert row.iv_hv_spread is None


def test_persist_iv_sample_spread_is_none_when_iv_missing() -> None:
    sample = IVSample(
        symbol="AAPL",
        date=date(2026, 4, 22),
        iv_30d=None,
        iv_60d=None,
        source="yahoo",
    )
    db = _RecordingSession()
    row = persist_iv_sample(sample, hv_20d=0.30, hv_60d=0.28, db=db)  # type: ignore[arg-type]
    assert row.iv_hv_spread is None
