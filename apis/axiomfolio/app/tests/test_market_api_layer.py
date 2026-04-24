"""Tests for API layer: /snapshots/table, /snapshots/aggregates, /quad, /regime."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.dependencies import get_market_data_viewer
from app.database import get_db
from app.models.market_data import MarketSnapshot, MarketQuad, MarketRegime
from app.models.user import UserRole


def _viewer_override():
    class _DummyUser:
        id = 1
        role = UserRole.OWNER
        is_active = True
        email = "test@example.com"

    return _DummyUser()


def _make_snapshot(**overrides) -> MarketSnapshot:
    """Build a MarketSnapshot ORM object with sensible defaults."""
    defaults = dict(
        symbol="AAPL",
        analysis_type="technical_snapshot",
        current_price=150.0,
        stage_label="2B",
        sector="Technology",
        scan_tier="Breakout Standard",
        action_label="BUY",
        regime_state="R1",
        rs_mansfield_pct=5.0,
        ext_pct=4.2,
        atrp_14=2.5,
        vol_ratio=1.8,
        ema10_dist_n=0.7,
        range_pos_52w=80.0,
        perf_1d=1.2,
        perf_5d=3.5,
        perf_20d=8.0,
        current_stage_days=12,
        pass_count=1,
        atre_promoted=False,
        action_override=None,
        forward_rr=2.5,
        sector_confirmation="SCAN",
        quad_quarterly="Q1",
        quad_monthly="Q1",
        quad_divergence_flag=False,
        quad_depth="Deep",
        analysis_timestamp=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    row = MarketSnapshot()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


# ---------- Snapshot /table tests ----------


class _FakeTableQuery:
    """Chainable fake query for /table endpoint."""

    def __init__(self, rows):
        self._rows = list(rows)

    def join(self, *_a, **_k):
        return self

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def offset(self, _n):
        return self

    def limit(self, _n):
        return self

    def count(self):
        return len(self._rows)

    def all(self):
        return self._rows

    # aggregates support
    def with_entities(self, *_a, **_k):
        return self

    def group_by(self, *_a, **_k):
        return self


class _FakeTableDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, model):
        return _FakeTableQuery(self._rows)


def test_snapshot_table_returns_stage_analysis_fields(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    row = _make_snapshot(symbol="NVDA", ext_pct=6.5, pass_count=2, scan_tier="Breakout Elite")
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["NVDA"])
    app.dependency_overrides[get_db] = lambda: _FakeTableDB([row])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots/table?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        r = data["rows"][0]
        assert r["symbol"] == "NVDA"
        assert r["ext_pct"] == 6.5
        assert r["pass_count"] == 2
        assert r["scan_tier"] == "Breakout Elite"
        assert r["action_label"] == "BUY"
        assert r["regime_state"] == "R1"
        assert r["quad_quarterly"] == "Q1"
        assert r["forward_rr"] == 2.5
        assert r["sector_confirmation"] == "SCAN"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_snapshot_table_accepts_new_sort_columns(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    row = _make_snapshot()
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAPL"])
    app.dependency_overrides[get_db] = lambda: _FakeTableDB([row])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        for sort_col in ["sector", "ext_pct", "atrp_14", "vol_ratio", "ema10_dist_n",
                         "range_pos_52w", "perf_1d", "perf_5d", "scan_tier",
                         "current_stage_days", "forward_rr", "action_label"]:
            resp = client.get(f"/api/v1/market-data/snapshots/table?sort_by={sort_col}&sort_dir=desc")
            assert resp.status_code == 200, f"sort_by={sort_col} failed: {resp.status_code}"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_snapshot_table_accepts_new_filters(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    row = _make_snapshot()
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAPL"])
    app.dependency_overrides[get_db] = lambda: _FakeTableDB([row])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/market-data/snapshots/table",
            params={
                "sectors": "Technology,Healthcare",
                "scan_tiers": "Breakout Elite",
                "regime_state": "R1",
                "rs_min": "-5",
                "rs_max": "20",
            },
        )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_snapshot_table_empty_universe(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: [])
    app.dependency_overrides[get_db] = lambda: _FakeTableDB([])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots/table")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rows"] == []
        assert data["total"] == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


# ---------- /snapshots/aggregates tests ----------


class _FakeAggQuery:
    """Chainable fake that returns pre-set results for each GROUP BY call."""

    def __init__(self, rows, agg_results):
        self._rows = list(rows)
        self._agg_results = agg_results
        self._entity_call = 0

    def join(self, *_a, **_k):
        return self

    def filter(self, *_a, **_k):
        return self

    def count(self):
        return len(self._rows)

    def with_entities(self, *_a, **_k):
        return _FakeAggGroupBy(self._agg_results[self._entity_call])

    def order_by(self, *_a, **_k):
        return self


class _FakeAggGroupBy:
    def __init__(self, results):
        self._results = results

    def group_by(self, *_a, **_k):
        return self

    def all(self):
        return self._results


class _FakeAggDB:
    def __init__(self, rows, agg_results):
        self._q = _FakeAggQuery(rows, agg_results)
        self._call_count = 0

    def query(self, model):
        q = _FakeAggCallTracker(self._q, self)
        return q


class _FakeAggCallTracker:
    def __init__(self, q, db):
        self._q = q
        self._db = db

    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def count(self):
        return self._q.count()

    def with_entities(self, *a, **k):
        idx = self._db._call_count
        self._db._call_count += 1
        return self._q._agg_results[idx] if idx < len(self._q._agg_results) else _FakeAggGroupBy([])

    def order_by(self, *a, **k):
        return self


class _FakeGroupByResult:
    def group_by(self, *a, **k):
        return self

    def __init__(self, results):
        self._results = results

    def all(self):
        return self._results


def test_snapshot_aggregates_returns_distributions(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    rows = [_make_snapshot(symbol="AAPL"), _make_snapshot(symbol="MSFT")]

    # sector_summary GROUP BY now returns 7 columns (since 85d2554):
    # (sector, count, avg_rs, avg_perf_1d, avg_perf_20d, stage2_count, stage4_count)
    agg_data = [
        _FakeGroupByResult([("2B", 2)]),
        _FakeGroupByResult([("Technology", 2, 5.0, 0.01, 0.05, 2, 0)]),
        _FakeGroupByResult([("Breakout Standard", 2)]),
        _FakeGroupByResult([("BUY", 2)]),
    ]

    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAPL", "MSFT"])

    db = _FakeAggDB(rows, agg_data)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots/aggregates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert "stage_distribution" in data
        assert "sector_summary" in data
        assert "scan_tier_distribution" in data
        assert "action_distribution" in data
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_snapshot_aggregates_empty_universe(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: [])
    app.dependency_overrides[get_db] = lambda: _FakeTableDB([])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots/aggregates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["stage_distribution"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


# ---------- /quad tests ----------


class _FakeExecResult:
    """Unified mock for db.execute() that supports both scalar_one_or_none and scalars().all()."""

    def __init__(self, *, single=None, rows=None):
        self._single = single
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._single

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSelectDB:
    """DB mock for select()-style endpoints (quad, regime)."""

    def __init__(self, *, single=None, history=None):
        self._single = single
        self._history = history or []

    def execute(self, stmt):
        return _FakeExecResult(single=self._single, rows=self._history)


def test_quad_current_returns_state():
    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    quad = MarketQuad()
    quad.as_of_date = datetime(2026, 4, 1)
    quad.quarterly_quad = "Q1"
    quad.monthly_quad = "Q2"
    quad.operative_quad = "Q2"
    quad.quarterly_depth = "Deep"
    quad.monthly_depth = "Shallow"
    quad.divergence_flag = True
    quad.divergence_months = 3
    quad.source = "hedgeye"

    app.dependency_overrides[get_db] = lambda: _FakeSelectDB(single=quad)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/quad/current")
        assert resp.status_code == 200
        data = resp.json()["quad"]
        assert data["quarterly_quad"] == "Q1"
        assert data["monthly_quad"] == "Q2"
        assert data["operative_quad"] == "Q2"
        assert data["divergence_flag"] is True
        assert data["divergence_months"] == 3
        assert data["source"] == "hedgeye"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_quad_current_returns_null_when_empty():
    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    app.dependency_overrides[get_db] = lambda: _FakeSelectDB(single=None)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/quad/current")
        assert resp.status_code == 200
        assert resp.json()["quad"] is None
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_quad_history_returns_rows():
    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    q1 = MarketQuad()
    q1.as_of_date = datetime(2026, 3, 15)
    q1.quarterly_quad = "Q1"
    q1.monthly_quad = "Q1"
    q1.operative_quad = "Q1"
    q1.quarterly_depth = "Deep"
    q1.monthly_depth = "Deep"
    q1.divergence_flag = False
    q1.divergence_months = 0

    app.dependency_overrides[get_db] = lambda: _FakeSelectDB(history=[q1])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/quad/history?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["history"]) == 1
        assert data["history"][0]["quarterly_quad"] == "Q1"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


# ---------- /regime enhancement tests ----------


def test_regime_current_includes_weights():
    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    from app.services.silver.regime import regime_engine

    regime = MarketRegime()
    regime.as_of_date = datetime(2026, 4, 1)
    regime.regime_state = "R1"
    regime.composite_score = 1.5
    regime.vix_spot = 14.0
    regime.vix3m_vix_ratio = 1.1
    regime.vvix_vix_ratio = 5.0
    regime.nh_nl = 200
    regime.pct_above_200d = 75.0
    regime.pct_above_50d = 65.0
    regime.score_vix = 1.0
    regime.score_vix3m_vix = 1.0
    regime.score_vvix_vix = 2.0
    regime.score_nh_nl = 1.0
    regime.score_above_200d = 1.0
    regime.score_above_50d = 2.0
    regime.weights_used = [1.0, 1.25, 0.75, 1.0, 1.0, 0.75]
    regime.cash_floor_pct = 10.0
    regime.max_equity_exposure_pct = 100.0
    regime.regime_multiplier = 1.0

    original_fn = regime_engine.get_current_regime

    def mock_get(db):
        return regime

    regime_engine.get_current_regime = mock_get
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/regime/current")
        assert resp.status_code == 200
        data = resp.json()["regime"]
        assert data["weights_used"] == [1.0, 1.25, 0.75, 1.0, 1.0, 0.75]
        assert data["regime_state"] == "R1"
        assert data["score_vix"] == 1.0
    finally:
        regime_engine.get_current_regime = original_fn
        app.dependency_overrides.pop(get_market_data_viewer, None)


# ---------- Deprecated GET /snapshots hard-cap test ----------


def test_deprecated_snapshots_has_200_cap(monkeypatch):
    """The old GET /snapshots endpoint is capped at 200 and returns deprecation headers."""
    from app.api.routes.market import snapshots as routes
    from app.models.market_tracked_plan import MarketTrackedPlan

    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    class _FakeSnapshotQuery:
        def join(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def limit(self, n):
            assert n <= 200, f"Limit should be capped at 200, got {n}"
            return self

        def all(self):
            return []

    class _FakePlanQuery:
        def filter(self, *_a, **_k):
            return self

        def all(self):
            return []

    class _FakeDB:
        def query(self, model):
            if model is MarketTrackedPlan:
                return _FakePlanQuery()
            return _FakeSnapshotQuery()

    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAPL"])
    app.dependency_overrides[get_db] = lambda: _FakeDB()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots")
        assert resp.status_code == 200
        assert resp.headers.get("Deprecation") == "true"
        assert "successor-version" in resp.headers.get("Link", "")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_deprecated_snapshots_rejects_over_200():
    """Attempting limit > 200 on the deprecated endpoint returns 422."""
    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots?limit=5000")
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_market_data_viewer, None)


# ---------- action_labels / preset / index_name filter tests ----------


def test_snapshot_table_accepts_action_labels_filter(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    row = _make_snapshot(symbol="AAPL", action_label="BUY")
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAPL"])
    app.dependency_overrides[get_db] = lambda: _FakeTableDB([row])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots/table?action_labels=BUY,WATCH")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_snapshot_table_accepts_preset_filter(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    row = _make_snapshot(symbol="NVDA", stage_label="2A", rs_mansfield_pct=8.0)
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["NVDA"])
    app.dependency_overrides[get_db] = lambda: _FakeTableDB([row])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        for preset_name in ["pullback_buy_zone", "ma_alignment", "large_cap_leaders", "squeeze_setup"]:
            resp = client.get(f"/api/v1/market-data/snapshots/table?preset={preset_name}")
            assert resp.status_code == 200, f"preset={preset_name} failed: {resp.status_code}"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_snapshot_table_ignores_unknown_preset(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    row = _make_snapshot()
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAPL"])
    app.dependency_overrides[get_db] = lambda: _FakeTableDB([row])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots/table?preset=nonexistent_preset")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_snapshot_table_accepts_index_name_filter(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    row = _make_snapshot(symbol="AAPL")
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAPL"])
    app.dependency_overrides[get_db] = lambda: _FakeTableDB([row])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots/table?index_name=SP500")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_snapshot_aggregates_accepts_action_labels(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    rows = [_make_snapshot(symbol="AAPL")]
    # sector tuple is 7 columns (sector, count, avg_rs, p1d, p20d, s2, s4)
    agg_data = [
        _FakeGroupByResult([("2B", 1)]),
        _FakeGroupByResult([("Technology", 1, 5.0, 0.01, 0.04, 1, 0)]),
        _FakeGroupByResult([("Breakout Standard", 1)]),
        _FakeGroupByResult([("BUY", 1)]),
    ]
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAPL"])
    db = _FakeAggDB(rows, agg_data)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots/aggregates?action_labels=BUY")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_snapshot_aggregates_accepts_preset_and_index(monkeypatch):
    from app.api.routes.market import snapshots as routes

    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    rows = [_make_snapshot(symbol="AAPL")]
    # sector tuple is 7 columns (sector, count, avg_rs, p1d, p20d, s2, s4)
    agg_data = [
        _FakeGroupByResult([("2B", 1)]),
        _FakeGroupByResult([("Technology", 1, 5.0, 0.01, 0.04, 1, 0)]),
        _FakeGroupByResult([("Breakout Standard", 1)]),
        _FakeGroupByResult([("BUY", 1)]),
    ]
    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAPL"])
    db = _FakeAggDB(rows, agg_data)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/market-data/snapshots/aggregates?preset=large_cap_leaders&index_name=SP500"
        )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_preset_filters_registry_has_expected_keys():
    from app.api.routes.market.snapshots import PRESET_FILTERS

    expected = {"pullback_buy_zone", "ma_alignment", "large_cap_leaders", "squeeze_setup"}
    assert set(PRESET_FILTERS.keys()) == expected
    for key, fn in PRESET_FILTERS.items():
        assert callable(fn), f"PRESET_FILTERS[{key!r}] is not callable"


# ---------- Intelligence offset pagination test ----------


def test_intelligence_briefs_accepts_offset():
    """GET /intelligence/briefs accepts offset query param for pagination."""
    from app.models.market_data import JobRun

    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    class _FakeBriefQuery:
        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def offset(self, n):
            assert n >= 0
            return self

        def limit(self, _n):
            return self

        def all(self):
            return []

    class _FakeBriefDB:
        def query(self, model):
            return _FakeBriefQuery()

    app.dependency_overrides[get_db] = lambda: _FakeBriefDB()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/intelligence/briefs?offset=20&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "briefs" in data
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_intelligence_briefs_rejects_negative_offset():
    """GET /intelligence/briefs rejects negative offset."""
    app.dependency_overrides[get_market_data_viewer] = _viewer_override
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/intelligence/briefs?offset=-1")
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_market_data_viewer, None)
