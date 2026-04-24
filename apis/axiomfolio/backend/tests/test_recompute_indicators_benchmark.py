from datetime import datetime, timedelta, timezone

from backend.services.market.market_data_service import infra
from backend.tasks.market import indicators as market_indicators_tasks


def test_recompute_indicators_warns_when_benchmark_missing(db_session, monkeypatch):
    class DummyRedis:
        def get(self, _key):
            return None

        def set(self, *_args, **_kwargs):
            return True

        def delete(self, *_args, **_kwargs):
            return 1

    # Avoid Redis + background status updates during the test (task_run / _publish_status).
    monkeypatch.setattr(infra, "_redis_sync", DummyRedis())
    monkeypatch.setattr(market_indicators_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(market_indicators_tasks, "_set_task_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_indicators_tasks, "_get_tracked_symbols_safe", lambda _session: ["AAA"])

    async def _fake_fetch_daily_for_symbols(**_kwargs):
        return [{"symbol": "SPY", "df": None, "provider": "fmp"}]

    monkeypatch.setattr(
        market_indicators_tasks, "_fetch_daily_for_symbols", _fake_fetch_daily_for_symbols
    )
    monkeypatch.setattr(
        market_indicators_tasks,
        "_persist_daily_fetch_results",
        lambda **_kwargs: {"errors": 1, "processed_ok": 0, "bars_inserted_total": 0},
    )

    res = market_indicators_tasks.recompute_universe(batch_size=1)
    assert res["benchmark"]["ok"] is False
    assert res["benchmark"]["daily_bars"] < res["benchmark"]["required_bars"]
    assert res["benchmark"]["spy_session_lag_stale"] is True
    assert res["benchmark"]["spy_freshness_refresh_attempted"] is True
    assert res.get("warnings")


def _setup_recompute_monkeypatches(monkeypatch, db_session):
    """Common monkeypatches for recompute_universe tests."""

    class DummyRedis:
        def get(self, _key):
            return None

        def set(self, *_args, **_kwargs):
            return True

        def delete(self, *_args, **_kwargs):
            return 1

    monkeypatch.setattr(infra, "_redis_sync", DummyRedis())
    monkeypatch.setattr(market_indicators_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(market_indicators_tasks, "_set_task_status", lambda *a, **kw: None)
    monkeypatch.setattr(market_indicators_tasks, "_get_tracked_symbols_safe", lambda _s: ["TESTFRESH"])

    async def _fake_fetch(**_kw):
        return [{"symbol": "SPY", "df": None, "provider": "fmp"}]

    monkeypatch.setattr(market_indicators_tasks, "_fetch_daily_for_symbols", _fake_fetch)
    monkeypatch.setattr(
        market_indicators_tasks,
        "_persist_daily_fetch_results",
        lambda **_kw: {"errors": 0, "processed_ok": 0, "bars_inserted_total": 0},
    )


def test_recompute_force_bypasses_freshness_check(db_session, monkeypatch):
    """force=True processes all symbols; force=False skips fresh ones."""
    if db_session is None:
        return
    from backend.models import MarketSnapshot

    _setup_recompute_monkeypatches(monkeypatch, db_session)

    fresh_ts = datetime.now(timezone.utc) - timedelta(minutes=30)
    snap = MarketSnapshot(
        symbol="TESTFRESH",
        analysis_type="technical_snapshot",
        analysis_timestamp=fresh_ts,
        expiry_timestamp=fresh_ts + timedelta(hours=24),
    )
    db_session.add(snap)
    db_session.flush()

    res_default = market_indicators_tasks.recompute_universe(batch_size=1, force=False)
    assert res_default["skipped_fresh"] >= 1, "Expected TESTFRESH to be skipped as fresh"

    res_forced = market_indicators_tasks.recompute_universe(batch_size=1, force=True)
    assert res_forced["skipped_fresh"] == 0, "force=True should bypass freshness check"


def test_spy_daily_bars_stale_vs_ref_trading_day_window():
    ref = datetime(2026, 2, 2, tzinfo=timezone.utc).date()  # Monday
    recent_fri = datetime(2026, 1, 30, 12, 0, tzinfo=timezone.utc)
    assert market_indicators_tasks._spy_daily_bars_stale_vs_ref(recent_fri, ref) is False
    old_wed = datetime(2026, 1, 21, 12, 0, tzinfo=timezone.utc)
    assert market_indicators_tasks._spy_daily_bars_stale_vs_ref(old_wed, ref) is True
    assert market_indicators_tasks._spy_daily_bars_stale_vs_ref(None, ref) is True

