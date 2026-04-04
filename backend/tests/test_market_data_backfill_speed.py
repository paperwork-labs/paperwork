import asyncio
import pandas as pd
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from backend.services.market.market_data_service import (
    MarketDataService,
    market_data_service,
    APIProvider,
    _cb_failures,
    _cb_open_until,
)


def _make_df(days: int = 5) -> pd.DataFrame:
    now = datetime.utcnow().replace(microsecond=0)
    dates = [now - timedelta(days=i) for i in range(days)][::-1]
    df = pd.DataFrame(
        [{"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1} for _ in dates],
        index=pd.DatetimeIndex(dates),
    )
    return df


@pytest.mark.asyncio
async def test_call_blocking_with_retries_backoff_on_429(monkeypatch):
    svc = MarketDataService()
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(float(delay))

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    class RateLimitExc(Exception):
        status_code = 429

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RateLimitExc("429")
        return "ok"

    out = await svc._call_blocking_with_retries(flaky, attempts=5, max_delay_seconds=1.0)
    assert out == "ok"
    assert calls["n"] == 2
    assert len(sleeps) == 1


class TestCircuitBreaker:
    """Tests for per-provider circuit breaker (module-level state)."""

    def setup_method(self):
        _cb_failures.clear()
        _cb_open_until.clear()

    def teardown_method(self):
        _cb_failures.clear()
        _cb_open_until.clear()

    def test_cb_closed_by_default(self):
        svc = MarketDataService()
        assert not svc._cb_is_open(APIProvider.FMP)

    def test_cb_opens_after_threshold(self):
        svc = MarketDataService()
        for _ in range(5):
            svc._cb_record_failure(APIProvider.FMP)
        assert svc._cb_is_open(APIProvider.FMP)

    def test_cb_stays_closed_below_threshold(self):
        svc = MarketDataService()
        for _ in range(4):
            svc._cb_record_failure(APIProvider.FMP)
        assert not svc._cb_is_open(APIProvider.FMP)

    def test_cb_resets_on_success(self):
        svc = MarketDataService()
        for _ in range(4):
            svc._cb_record_failure(APIProvider.FMP)
        svc._cb_record_success(APIProvider.FMP)
        assert not svc._cb_is_open(APIProvider.FMP)
        assert "fmp" not in _cb_failures

    def test_cb_expires_after_cooldown(self):
        svc = MarketDataService()
        for _ in range(5):
            svc._cb_record_failure(APIProvider.FMP)
        assert svc._cb_is_open(APIProvider.FMP)
        _cb_open_until["fmp"] = time.monotonic() - 1
        assert not svc._cb_is_open(APIProvider.FMP)

    def test_cb_shared_across_instances(self):
        svc1 = MarketDataService()
        svc2 = MarketDataService()
        for _ in range(5):
            svc1._cb_record_failure(APIProvider.FMP)
        assert svc2._cb_is_open(APIProvider.FMP)

    def test_cb_independent_per_provider(self):
        svc = MarketDataService()
        for _ in range(5):
            svc._cb_record_failure(APIProvider.FMP)
        assert svc._cb_is_open(APIProvider.FMP)
        assert not svc._cb_is_open(APIProvider.YFINANCE)


def test_persist_price_bars_bulk_upsert_still_delta_only(db_session):
    sym = "BULKTEST"
    df = _make_df(days=3)
    inserted_1 = market_data_service.persist_price_bars(
        db_session, sym, df.iloc[:1], interval="1d", data_source="unit_test", is_adjusted=True
    )
    assert inserted_1 == 1
    from backend.models import PriceData

    last_date = (
        db_session.query(PriceData.date)
        .filter(PriceData.symbol == sym, PriceData.interval == "1d")
        .order_by(PriceData.date.desc())
        .limit(1)
        .scalar()
    )
    assert last_date is not None
    inserted_2 = market_data_service.persist_price_bars(
        db_session, sym, df, interval="1d", data_source="unit_test", is_adjusted=True, delta_after=last_date
    )
    assert inserted_2 == 2


