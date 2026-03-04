from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

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

    def __iter__(self):
        # Support iteration for db.query(IndexConstituent.symbol).filter().distinct()
        for r in self._rows:
            yield (getattr(r, "symbol", r),)


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *args, **kwargs):
        return _FakeQuery(self._rows)


def test_fetch_rows_dedupes_to_latest_snapshot_per_symbol(monkeypatch):
    class _FakeMDS:
        def __init__(self):
            self.redis_client = None

    monkeypatch.setattr(mds_module, "MarketDataService", _FakeMDS)
    monkeypatch.setattr(mds_module, "tracked_symbols", lambda *args, **kwargs: ["AAPL", "MSFT"])

    now = datetime.utcnow()
    rows = [
        SimpleNamespace(
            symbol="AAPL",
            analysis_type="technical_snapshot",
            analysis_timestamp=now,
            stage_label="2",
            previous_stage_label="1",
            current_price=200.0,
            perf_1d=3.0,
            perf_5d=4.0,
            perf_20d=10.0,
            rs_mansfield_pct=5.0,
            sector="Technology",
            industry="Consumer Electronics",
            sma_50=190.0,
            sma_200=170.0,
        ),
        SimpleNamespace(
            symbol="AAPL",
            analysis_type="technical_snapshot",
            analysis_timestamp=now - timedelta(days=1),
            stage_label="1",
            previous_stage_label=None,
            current_price=180.0,
            perf_1d=-1.0,
            perf_5d=-2.0,
            perf_20d=1.0,
            rs_mansfield_pct=0.5,
            sector="Technology",
            industry="Consumer Electronics",
            sma_50=185.0,
            sma_200=168.0,
        ),
        SimpleNamespace(
            symbol="MSFT",
            analysis_type="technical_snapshot",
            analysis_timestamp=now,
            stage_label="2B",
            previous_stage_label="2A",
            current_price=400.0,
            perf_1d=1.0,
            perf_5d=2.0,
            perf_20d=7.0,
            rs_mansfield_pct=3.0,
            sector="Technology",
            industry="Software",
            sma_50=390.0,
            sma_200=360.0,
        ),
    ]

    service = MarketDashboardService()
    tracked, out, _plan_map, _latest_ts = service._fetch_rows(_FakeDB(rows))

    assert tracked == ["AAPL", "MSFT"]
    assert len(out) == 2
    aapl = next((r for r in out if r.symbol == "AAPL"), None)
    assert aapl is not None
    assert aapl.current_price == 200.0
    assert aapl.perf_1d == 3.0


def test_build_dashboard_sorts_leaders_and_pullbacks_by_momentum_score(monkeypatch):
    class _Coverage:
        @staticmethod
        def build_coverage_response(*args, **kwargs):
            return {
                "status": "healthy",
                "daily": {"coverage": {"pct": 98.0, "stale_count": 2}},
                "m5": {"coverage": {"pct": 71.0, "stale_count": 5}},
            }

    class _FakeMDS:
        def __init__(self):
            self.redis_client = None
            self.coverage = _Coverage()

    monkeypatch.setattr(mds_module, "MarketDataService", _FakeMDS)

    rows = [
        _SummaryRow(
            symbol="AAA",
            stage_label="2",
            previous_stage_label="1",
            current_price=100.0,
            perf_1d=1.0,
            perf_5d=1.0,
            perf_20d=4.0,
            rs_mansfield_pct=1.0,
            sector="Tech",
            industry="Software",
            sma_50=95.0,
            sma_200=90.0,
        ),
        _SummaryRow(
            symbol="ZZZ",
            stage_label="2B",
            previous_stage_label="2A",
            current_price=50.0,
            perf_1d=2.0,
            perf_5d=8.0,
            perf_20d=15.0,
            rs_mansfield_pct=6.0,
            sector="Tech",
            industry="Hardware",
            sma_50=45.0,
            sma_200=40.0,
        ),
        _SummaryRow(
            symbol="BBB",
            stage_label="2A",
            previous_stage_label="1",
            current_price=120.0,
            perf_1d=1.2,
            perf_5d=-1.0,
            perf_20d=9.0,
            rs_mansfield_pct=4.0,
            sector="Tech",
            industry="Semis",
            sma_50=110.0,
            sma_200=100.0,
        ),
    ]

    service = MarketDashboardService()
    monkeypatch.setattr(service, "_fetch_rows", lambda db: (["AAA", "BBB", "ZZZ"], rows, {}, None))

    payload = service.build_dashboard(db=_FakeDB([]))

    assert payload["tracked_count"] == 3
    assert payload["leaders"][0]["symbol"] == "ZZZ"
    assert payload["leaders"][0]["momentum_score"] > payload["leaders"][1]["momentum_score"]
    # Pullback list is now ranked by momentum score, not source/alphabetical ordering.
    pullbacks = payload["setups"]["pullback_candidates"]
    assert [p["symbol"] for p in pullbacks] == ["BBB", "AAA"]


def test_build_dashboard_sector_etfs_use_configured_list_and_order(monkeypatch):
    class _Coverage:
        @staticmethod
        def build_coverage_response(*args, **kwargs):
            return {
                "status": "healthy",
                "daily": {"coverage": {"pct": 100.0, "stale_count": 0}},
                "m5": {"coverage": {"pct": 100.0, "stale_count": 0}},
            }

    class _FakeMDS:
        def __init__(self):
            self.redis_client = None
            self.coverage = _Coverage()

    monkeypatch.setattr(mds_module, "MarketDataService", _FakeMDS)

    rows = [
        _SummaryRow(symbol="XLE", stage_label="2A", current_stage_days=12, perf_1d=1.2, sector="Energy"),
        _SummaryRow(symbol="XLF", stage_label="3", current_stage_days=8, perf_1d=-0.4, sector="Financial Services"),
        _SummaryRow(symbol="SOXX", stage_label="2B", current_stage_days=5, perf_1d=2.3, sector="Technology"),
        _SummaryRow(symbol="XBI", stage_label="2C", current_stage_days=3, perf_1d=4.0, sector="Biotech"),
    ]

    service = MarketDashboardService()
    monkeypatch.setattr(service, "_fetch_rows", lambda db: ([r.symbol for r in rows], rows, {}, None))

    payload = service.build_dashboard(db=_FakeDB([]))
    table = payload["sector_etf_table"]

    assert [r["symbol"] for r in table] == SECTOR_ETF_SYMBOLS_ORDER
    assert all(r["symbol"] != "XBI" for r in table)

    by_symbol = {r["symbol"]: r for r in table}
    assert by_symbol["XLE"]["sector_name"] == "Energy"
    assert by_symbol["XLE"]["change_1d"] == 1.2
    assert by_symbol["SOX"]["change_1d"] == 2.3
    assert by_symbol["SOX"]["stage_label"] == "2B"


def test_build_dashboard_entering_stage_2a_is_not_truncated(monkeypatch):
    class _Coverage:
        @staticmethod
        def build_coverage_response(*args, **kwargs):
            return {
                "status": "healthy",
                "daily": {"coverage": {"pct": 100.0, "stale_count": 0}},
                "m5": {"coverage": {"pct": 100.0, "stale_count": 0}},
            }

    class _FakeMDS:
        def __init__(self):
            self.redis_client = None
            self.coverage = _Coverage()

    monkeypatch.setattr(mds_module, "MarketDataService", _FakeMDS)

    rows = [
        _SummaryRow(
            symbol=f"S{i:02d}",
            stage_label="2A",
            previous_stage_label="1",
            current_price=100.0 + i,
            perf_1d=0.1,
            perf_5d=0.2,
            perf_20d=0.3,
            rs_mansfield_pct=0.4,
            sector="Tech",
            industry="Software",
            sma_50=95.0,
            sma_200=90.0,
        )
        for i in range(30)
    ]

    service = MarketDashboardService()
    monkeypatch.setattr(service, "_fetch_rows", lambda db: ([r.symbol for r in rows], rows, {}, None))

    payload = service.build_dashboard(db=_FakeDB([]))
    entering = payload["entering_stage_2a"]

    assert len(entering) == 30
    assert entering[0]["symbol"] == "S00"
    assert entering[-1]["symbol"] == "S29"
