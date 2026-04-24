

def test_backfill_symbols_passes_max_bars_to_provider(monkeypatch):
    """
    Regression test: backfill_symbols must NOT fetch full daily history and then tail(),
    because df.tail(270) on a newest-first frame selects the oldest bars.

    We enforce that tasks call get_historical_data(max_bars=270).
    """
    from app.services.market.market_data_service import provider_router
    from app.tasks.market.backfill import symbols

    calls = []

    async def _stub_get_historical_data(
        *, symbol, period, interval, max_bars=None, return_provider=False, **_kwargs
    ):
        calls.append(
            {
                "symbol": symbol,
                "period": period,
                "interval": interval,
                "max_bars": max_bars,
                "return_provider": return_provider,
            }
        )
        # Return empty df so persistence is skipped; we only care about args.
        return (None, "fmp") if return_provider else None

    monkeypatch.setattr(
        provider_router,
        "get_historical_data",
        _stub_get_historical_data,
    )

    # Run with a few symbols; function is sync wrapper around event loop.
    res = symbols(["AAA", "BBB", "CCC"])
    assert res["status"] == "ok"
    assert len(calls) == 3
    assert all(c["interval"] == "1d" for c in calls)
    assert all(c["period"] == "1y" for c in calls)
    assert all(c["return_provider"] is True for c in calls)
    assert all(c["max_bars"] == 270 for c in calls)
