from backend.services.market.market_data_service import market_data_service
from backend.tasks.market import indicators as market_indicators_tasks


def test_recompute_indicators_warns_when_benchmark_missing(db_session, monkeypatch):
    class DummyRedis:
        def get(self, _key):
            return None

    # Avoid Redis + background status updates during the test.
    market_data_service._redis_sync = DummyRedis()
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
    assert res.get("warnings")

