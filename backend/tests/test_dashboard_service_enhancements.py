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


def _mock_snapshot(symbol, stage="2A", prev="1", perf_1d=1.0, perf_5d=2.0, perf_20d=5.0, rs=3.0):
    return SimpleNamespace(
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
    )


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
