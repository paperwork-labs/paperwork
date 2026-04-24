import pandas as pd
import pytest

from app.services.market.market_data_service import provider_router, snapshot_builder


@pytest.mark.asyncio
async def test_manual_ma_stage_basic(monkeypatch):
    dates = pd.date_range(end=pd.Timestamp.today(), periods=220, freq="D")
    close = pd.Series(range(1, 221), index=dates, dtype=float)
    high = close + 1
    low = close - 1
    df = pd.DataFrame({"Open": close, "High": high, "Low": low, "Close": close, "Volume": 1000})
    df = df.iloc[::-1]

    async def _fake_hist(symbol, period="1y", interval="1d", **_kw):
        return df

    monkeypatch.setattr(provider_router, "get_historical_data", _fake_hist)

    snapshot = await snapshot_builder.build_indicator_snapshot("TEST")
    assert "sma_200" in snapshot and "ema_200" in snapshot
    assert snapshot.get("ma_bucket") in ("LEADING", "NEUTRAL", "UNKNOWN", "LAGGING")

    stage = await snapshot_builder.get_weinstein_stage("TEST")
    assert "stage" in stage
