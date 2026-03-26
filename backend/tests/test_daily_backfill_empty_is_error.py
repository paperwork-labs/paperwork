import pytest


def test_backfill_last_bars_counts_empty_as_error(db_session, monkeypatch):
    """
    Regression: transient provider failures can return df=None/empty and were previously counted as skipped_empty with errors=0.
    We now count these as errors and surface samples.
    """
    # backfill_last_bars lives in backend.tasks.market.backfill (not only the facade).
    monkeypatch.setattr("backend.tasks.market.backfill.SessionLocal", lambda: db_session)
    monkeypatch.setattr("backend.tasks.market.backfill._set_task_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "backend.tasks.market.backfill._get_tracked_universe_from_db",
        lambda _session: {"AAA", "BBB"},
    )

    # Avoid real DB writes for price bars
    from backend.services.market.market_data_service import market_data_service

    monkeypatch.setattr(market_data_service, "persist_price_bars", lambda *args, **kwargs: 1)

    async def fake_get_historical_data(symbol: str, *args, **kwargs):
        # AAA succeeds, BBB looks like an "empty response"
        provider = "fmp"
        if symbol.upper() == "AAA":
            import pandas as pd

            df = pd.DataFrame(
                [{"Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 0}],
                index=[pd.Timestamp("2026-01-09")],
            ).sort_index(ascending=False)
            return (df, provider)
        return (None, provider)

    monkeypatch.setattr(
        market_data_service.providers,
        "get_historical_data",
        fake_get_historical_data,
    )

    from backend.tasks.market.backfill import daily_bars

    res = daily_bars()
    assert res["tracked_total"] == 2
    assert res["updated_total"] == 1
    assert res["skipped_empty"] == 1
    assert res["errors"] >= 1
    assert any(s.get("symbol") == "BBB" for s in res.get("error_samples", []))


def test_record_daily_history_defaults_to_tracked_universe(db_session, monkeypatch):
    from datetime import datetime, timezone

    from backend.models.market_data import MarketSnapshot, MarketSnapshotHistory

    monkeypatch.setattr("backend.tasks.market.history.SessionLocal", lambda: db_session)
    monkeypatch.setattr("backend.tasks.market.history._set_task_status", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.tasks.market.history._get_tracked_symbols_safe", lambda _session: ["AAA"])

    # Ensure we have a snapshot row for the symbol
    snap = MarketSnapshot(
        symbol="AAA",
        analysis_type="technical_snapshot",
        analysis_timestamp=datetime.now(timezone.utc),
        as_of_timestamp=datetime(2026, 1, 9, tzinfo=timezone.utc),
        expiry_timestamp=datetime(2026, 1, 11, tzinfo=timezone.utc),
        raw_analysis={"current_price": 1.23, "rsi": 50, "atr_value": 1.0, "sma_50": 1.1, "macd": 0.1, "macd_signal": 0.2},
    )
    db_session.add(snap)
    db_session.commit()

    from backend.tasks.market.history import record_daily

    res = record_daily()
    assert res["symbols"] == 1
    assert res["written"] == 1

    rows = db_session.query(MarketSnapshotHistory).filter(MarketSnapshotHistory.symbol == "AAA").all()
    assert len(rows) == 1


@pytest.mark.no_db
def test_fmp_error_dict_raises(monkeypatch):
    """Ensure FMP error payloads raise so retry/backoff can kick in."""
    from backend.services.market import market_data_service as mds_mod

    def fake_historical_price_full(*args, **kwargs):
        return {"Error Message": "Rate Limit Exceeded"}

    monkeypatch.setattr(mds_mod.fmpsdk, "historical_price_full", fake_historical_price_full)
    svc = mds_mod.MarketDataService()
    with pytest.raises(RuntimeError):
        svc._get_historical_fmp_sync("AAA", "1y", "1d")


