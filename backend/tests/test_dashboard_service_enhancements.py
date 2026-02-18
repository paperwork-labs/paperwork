"""Tests for enhanced MarketDashboardService: sector_etf_table fields, entering_stage_3/4."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.services.market import market_dashboard_service as mds_module
from backend.services.market.constants import SECTOR_ETF_SYMBOLS_ORDER
from backend.services.market.market_dashboard_service import MarketDashboardService, _SummaryRow

pytestmark = pytest.mark.no_db


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def distinct(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *args, **kwargs):
        return _FakeQuery(self._rows)


def _mock_snapshot(symbol, stage="2A", prev="1", perf_1d=1.0, perf_5d=2.0, perf_20d=5.0, rs=3.0, **kw):
    defaults = dict(
        symbol=symbol,
        analysis_type="technical_snapshot",
        analysis_timestamp=datetime.utcnow(),
        stage_label=stage,
        previous_stage_label=prev,
        current_stage_days=5,
        current_price=100.0,
        perf_1d=perf_1d,
        perf_5d=perf_5d,
        perf_20d=perf_20d,
        rs_mansfield_pct=rs,
        atr_14=2.0,
        sma_21=98.0,
        sector="Technology",
        industry="Software",
        sma_50=95.0,
        sma_200=90.0,
        atrx_sma_21=1.0,
        atrx_sma_50=2.5,
        range_pos_52w=65.0,
        rsi=55.0,
        pe_ttm=25.0,
        eps_growth_yoy=15.0,
        revenue_growth_yoy=10.0,
        next_earnings=None,
        td_buy_setup=None,
        td_sell_setup=None,
        td_buy_countdown=None,
        td_sell_countdown=None,
        td_perfect_buy=None,
        td_perfect_sell=None,
        gaps_unfilled_up=0,
        gaps_unfilled_down=0,
        as_of_date=datetime.utcnow().date(),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_sector_etf_table_has_enhanced_fields(monkeypatch):
    """sector_etf_table entries should include change_5d, change_20d, rs_mansfield_pct."""
    class _FakeMDS:
        def __init__(self):
            self.redis_client = None

    class _FakeCoverage:
        def build_coverage_response(self, *a, **kw):
            return {"status": "ok", "daily": {"coverage": {"pct": 99}}, "m5": {"coverage": {"pct": 95}}}

    monkeypatch.setattr(mds_module, "MarketDataService", lambda: SimpleNamespace(
        redis_client=None,
        coverage=_FakeCoverage(),
    ))

    tracked = list(SECTOR_ETF_SYMBOLS_ORDER[:3]) + ["AAPL"]
    monkeypatch.setattr(mds_module, "tracked_symbols", lambda *a, **kw: tracked)

    etf_sym = SECTOR_ETF_SYMBOLS_ORDER[0]
    rows = [_mock_snapshot(etf_sym), _mock_snapshot("AAPL")]

    db = _FakeDB(rows)
    svc = MarketDashboardService()
    result = svc.build_dashboard(db)

    etf_table = result["sector_etf_table"]
    assert len(etf_table) > 0, "sector_etf_table should not be empty"

    first_with_data = next((e for e in etf_table if e.get("change_1d") is not None), None)
    assert first_with_data is not None, "Expected at least one ETF row with data"
    assert "change_5d" in first_with_data
    assert "change_20d" in first_with_data
    assert "rs_mansfield_pct" in first_with_data


def test_entering_stage_3_and_4_populated(monkeypatch):
    """entering_stage_3 and entering_stage_4 should be populated from snapshot data."""
    class _FakeCoverage:
        def build_coverage_response(self, *a, **kw):
            return {"status": "ok", "daily": {"coverage": {"pct": 99}}, "m5": {"coverage": {"pct": 95}}}

    monkeypatch.setattr(mds_module, "MarketDataService", lambda: SimpleNamespace(
        redis_client=None,
        coverage=_FakeCoverage(),
    ))
    monkeypatch.setattr(mds_module, "tracked_symbols", lambda *a, **kw: ["AAA", "BBB", "CCC"])

    rows = [
        _mock_snapshot("AAA", stage="Stage 3", prev="2A"),
        _mock_snapshot("BBB", stage="Stage 4", prev="3"),
        _mock_snapshot("CCC", stage="2A", prev="1"),
    ]
    db = _FakeDB(rows)
    svc = MarketDashboardService()
    result = svc.build_dashboard(db)

    assert len(result["entering_stage_3"]) >= 1
    assert result["entering_stage_3"][0]["symbol"] == "AAA"
    assert len(result["entering_stage_4"]) >= 1
    assert result["entering_stage_4"][0]["symbol"] == "BBB"
    assert len(result["entering_stage_2a"]) == 1
    assert result["entering_stage_2a"][0]["symbol"] == "CCC"


def _dashboard_helper(monkeypatch, rows, tracked=None):
    """DRY helper for tests that need a full build_dashboard call."""
    class _FakeCoverage:
        def build_coverage_response(self, *a, **kw):
            return {"status": "ok", "daily": {"coverage": {"pct": 99}}, "m5": {"coverage": {"pct": 95}}}

    monkeypatch.setattr(mds_module, "MarketDataService", lambda: SimpleNamespace(
        redis_client=None,
        coverage=_FakeCoverage(),
    ))
    syms = tracked or [r.symbol for r in rows]
    monkeypatch.setattr(mds_module, "tracked_symbols", lambda *a, **kw: syms)
    db = _FakeDB(rows)
    return MarketDashboardService().build_dashboard(db)


def test_range_histogram(monkeypatch):
    rows = [
        _mock_snapshot("A", range_pos_52w=5),
        _mock_snapshot("B", range_pos_52w=15),
        _mock_snapshot("C", range_pos_52w=85),
        _mock_snapshot("D", range_pos_52w=92),
    ]
    result = _dashboard_helper(monkeypatch, rows)
    hist = result["range_histogram"]
    assert len(hist) == 10
    assert hist[0]["count"] == 1  # 0-10% bin
    assert hist[1]["count"] == 1  # 10-20%
    assert hist[8]["count"] == 1  # 80-90%
    assert hist[9]["count"] == 1  # 90-100%


def test_rrg_sectors(monkeypatch):
    from backend.services.market.constants import SECTOR_ETF_SYMBOLS_ORDER
    sym = SECTOR_ETF_SYMBOLS_ORDER[0]
    rows = [_mock_snapshot(sym, rs=4.5, perf_5d=1.2)]
    result = _dashboard_helper(monkeypatch, rows, tracked=[sym])
    rrg = result["rrg_sectors"]
    assert len(rrg) >= 1
    entry = next(e for e in rrg if e["symbol"] == sym)
    assert entry["rs_ratio"] == 4.5
    assert entry["rs_momentum"] == 1.2


def test_rsi_divergences(monkeypatch):
    rows = [
        _mock_snapshot("BULL", perf_20d=-8.0, rsi=60),
        _mock_snapshot("BEAR", perf_20d=8.0, rsi=40),
        _mock_snapshot("NEUTRAL", perf_20d=2.0, rsi=55),
    ]
    result = _dashboard_helper(monkeypatch, rows)
    divs = result["rsi_divergences"]
    assert len(divs["bullish"]) == 1
    assert divs["bullish"][0]["symbol"] == "BULL"
    assert len(divs["bearish"]) == 1
    assert divs["bearish"][0]["symbol"] == "BEAR"


def test_td_signals(monkeypatch):
    rows = [
        _mock_snapshot("TD9", td_buy_setup=9),
        _mock_snapshot("TD13", td_sell_countdown=13),
        _mock_snapshot("NONE", td_buy_setup=3),
    ]
    result = _dashboard_helper(monkeypatch, rows)
    signals = result["td_signals"]
    syms = [s["symbol"] for s in signals]
    assert "TD9" in syms
    assert "TD13" in syms
    assert "NONE" not in syms


def test_gap_leaders(monkeypatch):
    rows = [
        _mock_snapshot("GAPPY", gaps_unfilled_up=5, gaps_unfilled_down=3),
        _mock_snapshot("FLAT", gaps_unfilled_up=0, gaps_unfilled_down=0),
    ]
    result = _dashboard_helper(monkeypatch, rows)
    gaps = result["gap_leaders"]
    assert len(gaps) == 1
    assert gaps[0]["symbol"] == "GAPPY"
    assert gaps[0]["total_gaps"] == 8


def test_fundamental_leaders(monkeypatch):
    rows = [
        _mock_snapshot("STRONG", eps_growth_yoy=50.0, rs=8.0),
        _mock_snapshot("WEAK", eps_growth_yoy=-5.0, rs=-2.0),
    ]
    result = _dashboard_helper(monkeypatch, rows)
    leaders = result["fundamental_leaders"]
    assert len(leaders) >= 1
    assert leaders[0]["symbol"] == "STRONG"


def test_upcoming_earnings(monkeypatch):
    from datetime import timedelta
    near = datetime.utcnow() + timedelta(days=3)
    far = datetime.utcnow() + timedelta(days=30)
    rows = [
        _mock_snapshot("SOON", next_earnings=near),
        _mock_snapshot("LATER", next_earnings=far),
        _mock_snapshot("NONE"),
    ]
    result = _dashboard_helper(monkeypatch, rows)
    upcoming = result["upcoming_earnings"]
    syms = [u["symbol"] for u in upcoming]
    assert "SOON" in syms
    assert "LATER" not in syms
