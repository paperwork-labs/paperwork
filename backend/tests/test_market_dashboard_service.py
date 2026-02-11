from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.services.market import market_dashboard_service as mds_module
from backend.services.market.market_dashboard_service import MarketDashboardService, _SummaryRow

pytestmark = pytest.mark.no_db


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


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
    tracked, out = service._fetch_rows(_FakeDB(rows))

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
    monkeypatch.setattr(service, "_fetch_rows", lambda db: (["AAA", "BBB", "ZZZ"], rows))

    payload = service.build_dashboard(db=None)  # type: ignore[arg-type]

    assert payload["tracked_count"] == 3
    assert payload["leaders"][0]["symbol"] == "ZZZ"
    assert payload["leaders"][0]["momentum_score"] > payload["leaders"][1]["momentum_score"]
    # Pullback list is now ranked by momentum score, not source/alphabetical ordering.
    pullbacks = payload["setups"]["pullback_candidates"]
    assert [p["symbol"] for p in pullbacks] == ["BBB", "AAA"]
