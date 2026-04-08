"""Tests for backend.tasks.market.bulk_eod — bulk EOD daily fill via FMP."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.tasks.market.bulk_eod import (
    _validate_and_build_rows,
    _persist_bulk_rows,
    _fetch_bulk_eod_for_date,
    _find_missing_dates,
    _last_n_trading_dates,
)


# ---------------------------------------------------------------------------
# Sample FMP bulk EOD response
# ---------------------------------------------------------------------------
SAMPLE_BULK_RESPONSE = [
    {
        "symbol": "AAPL",
        "date": "2025-04-04",
        "open": 220.0,
        "high": 225.0,
        "low": 219.0,
        "close": 224.5,
        "adjClose": 224.5,
        "volume": 45000000,
        "unadjustedVolume": 45000000,
        "change": 4.5,
        "changePercent": 2.04,
        "vwap": 222.83,
        "label": "April 04, 25",
        "changeOverTime": 0.0204,
    },
    {
        "symbol": "MSFT",
        "date": "2025-04-04",
        "open": 400.0,
        "high": 405.0,
        "low": 398.0,
        "close": 403.0,
        "adjClose": 403.0,
        "volume": 25000000,
    },
    {
        "symbol": "GOOG",
        "date": "2025-04-04",
        "open": 150.0,
        "high": 152.0,
        "low": 149.0,
        "close": 151.0,
        "adjClose": 151.0,
        "volume": 15000000,
    },
    {
        "symbol": "TSLA",
        "date": "2025-04-04",
        "open": 250.0,
        "high": 255.0,
        "low": 248.0,
        "close": 253.0,
        "adjClose": 253.0,
        "volume": 30000000,
    },
]


# ---------------------------------------------------------------------------
# _validate_and_build_rows
# ---------------------------------------------------------------------------
class TestValidateAndBuildRows:

    def test_filters_to_tracked_universe(self):
        tracked = {"AAPL", "MSFT"}
        rows = _validate_and_build_rows(SAMPLE_BULK_RESPONSE, tracked)
        symbols = {r["symbol"] for r in rows}
        assert symbols == {"AAPL", "MSFT"}
        assert len(rows) == 2

    def test_all_fields_populated(self):
        tracked = {"AAPL"}
        rows = _validate_and_build_rows(SAMPLE_BULK_RESPONSE, tracked)
        assert len(rows) == 1
        row = rows[0]
        assert row["symbol"] == "AAPL"
        assert row["open_price"] == 220.0
        assert row["high_price"] == 225.0
        assert row["low_price"] == 219.0
        assert row["close_price"] == 224.5
        assert row["adjusted_close"] == 224.5
        assert row["volume"] == 45000000
        assert row["interval"] == "1d"
        assert row["data_source"] == "fmp_bulk_eod"
        assert row["is_adjusted"] is True
        assert row["is_synthetic_ohlc"] is False
        assert isinstance(row["date"], datetime)

    def test_skips_zero_close(self):
        bars = [{"symbol": "FAIL", "date": "2025-04-04", "close": 0, "adjClose": 0}]
        rows = _validate_and_build_rows(bars, {"FAIL"})
        assert len(rows) == 0

    def test_skips_negative_close(self):
        bars = [{"symbol": "FAIL", "date": "2025-04-04", "close": -5.0, "adjClose": -5.0}]
        rows = _validate_and_build_rows(bars, {"FAIL"})
        assert len(rows) == 0

    def test_skips_nan_close(self):
        bars = [{"symbol": "FAIL", "date": "2025-04-04", "close": float("nan")}]
        rows = _validate_and_build_rows(bars, {"FAIL"})
        assert len(rows) == 0

    def test_skips_none_close(self):
        bars = [{"symbol": "FAIL", "date": "2025-04-04", "close": None, "adjClose": None}]
        rows = _validate_and_build_rows(bars, {"FAIL"})
        assert len(rows) == 0

    def test_skips_missing_date(self):
        bars = [{"symbol": "AAPL", "close": 100.0}]
        rows = _validate_and_build_rows(bars, {"AAPL"})
        assert len(rows) == 0

    def test_coalesces_missing_ohlv(self):
        bars = [{"symbol": "AAPL", "date": "2025-04-04", "close": 100.0}]
        rows = _validate_and_build_rows(bars, {"AAPL"})
        assert len(rows) == 1
        row = rows[0]
        assert row["open_price"] == 100.0
        assert row["high_price"] == 100.0
        assert row["low_price"] == 100.0
        assert row["volume"] == 0
        assert row["is_synthetic_ohlc"] is True

    def test_swaps_high_low_when_inverted(self):
        bars = [{
            "symbol": "AAPL",
            "date": "2025-04-04",
            "open": 100.0,
            "high": 90.0,
            "low": 110.0,
            "close": 100.0,
        }]
        rows = _validate_and_build_rows(bars, {"AAPL"})
        assert rows[0]["high_price"] == 110.0
        assert rows[0]["low_price"] == 90.0

    def test_symbol_case_insensitive_matching(self):
        bars = [{"symbol": "aapl", "date": "2025-04-04", "close": 100.0}]
        rows = _validate_and_build_rows(bars, {"AAPL"})
        assert len(rows) == 1
        assert rows[0]["symbol"] == "AAPL"

    def test_empty_input(self):
        rows = _validate_and_build_rows([], {"AAPL"})
        assert rows == []

    def test_empty_tracked_set(self):
        rows = _validate_and_build_rows(SAMPLE_BULK_RESPONSE, set())
        assert rows == []

    def test_uses_adjclose_when_close_missing(self):
        bars = [{"symbol": "AAPL", "date": "2025-04-04", "close": None, "adjClose": 150.0}]
        rows = _validate_and_build_rows(bars, {"AAPL"})
        assert len(rows) == 1
        assert rows[0]["close_price"] == 150.0


# ---------------------------------------------------------------------------
# _fetch_bulk_eod_for_date
# ---------------------------------------------------------------------------
class TestFetchBulkEod:

    @patch("backend.tasks.market.bulk_eod.requests.get")
    @patch("backend.tasks.market.bulk_eod.provider_rate_limiter")
    @patch("backend.tasks.market.bulk_eod.infra")
    @patch("backend.tasks.market.bulk_eod.settings")
    def test_returns_parsed_json(self, mock_settings, mock_infra, mock_rl, mock_get):
        mock_settings.FMP_API_KEY = "test-key"
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_BULK_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = _fetch_bulk_eod_for_date("2025-04-04")
        assert len(result) == 4
        mock_get.assert_called_once()
        mock_rl.acquire_sync.assert_called_once_with("fmp")
        mock_infra._record_provider_call_sync.assert_called_once_with("fmp", n=1)

    @patch("backend.tasks.market.bulk_eod.requests.get")
    @patch("backend.tasks.market.bulk_eod.provider_rate_limiter")
    @patch("backend.tasks.market.bulk_eod.settings")
    def test_raises_on_error_response(self, mock_settings, mock_rl, mock_get):
        mock_settings.FMP_API_KEY = "test-key"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"Error Message": "Invalid API KEY"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with pytest.raises(RuntimeError, match="Invalid API KEY"):
            _fetch_bulk_eod_for_date("2025-04-04")

    @patch("backend.tasks.market.bulk_eod.settings")
    def test_raises_when_no_api_key(self, mock_settings):
        mock_settings.FMP_API_KEY = ""
        with pytest.raises(RuntimeError, match="FMP_API_KEY not configured"):
            _fetch_bulk_eod_for_date("2025-04-04")


# ---------------------------------------------------------------------------
# _persist_bulk_rows
# ---------------------------------------------------------------------------
class TestPersistBulkRows:

    def test_persist_empty_returns_zero(self, db_session):
        if db_session is None:
            pytest.skip("DB session unavailable")
        result = _persist_bulk_rows(db_session, [])
        assert result == 0

    def test_persist_inserts_rows(self, db_session):
        if db_session is None:
            pytest.skip("DB session unavailable")
        from backend.models.market_data import PriceData

        db_session.query(PriceData).filter(
            PriceData.symbol == "BULKTEST",
            PriceData.interval == "1d",
        ).delete()
        db_session.commit()

        rows = [{
            "symbol": "BULKTEST",
            "date": datetime(2025, 4, 4),
            "open_price": 100.0,
            "high_price": 105.0,
            "low_price": 99.0,
            "close_price": 103.0,
            "adjusted_close": 103.0,
            "volume": 1000000,
            "interval": "1d",
            "data_source": "fmp_bulk_eod",
            "is_adjusted": True,
            "is_synthetic_ohlc": False,
        }]
        count = _persist_bulk_rows(db_session, rows)
        assert count == 1

        persisted = (
            db_session.query(PriceData)
            .filter(PriceData.symbol == "BULKTEST", PriceData.interval == "1d")
            .first()
        )
        assert persisted is not None
        assert persisted.close_price == 103.0
        assert persisted.data_source == "fmp_bulk_eod"

    def test_upsert_updates_existing(self, db_session):
        if db_session is None:
            pytest.skip("DB session unavailable")
        from backend.models.market_data import PriceData

        db_session.query(PriceData).filter(
            PriceData.symbol == "UPSERT",
            PriceData.interval == "1d",
        ).delete()
        db_session.commit()

        row_base = {
            "symbol": "UPSERT",
            "date": datetime(2025, 4, 4),
            "open_price": 100.0,
            "high_price": 105.0,
            "low_price": 99.0,
            "close_price": 103.0,
            "adjusted_close": 103.0,
            "volume": 1000000,
            "interval": "1d",
            "data_source": "fmp_bulk_eod",
            "is_adjusted": True,
            "is_synthetic_ohlc": False,
        }
        _persist_bulk_rows(db_session, [row_base])

        updated_row = {**row_base, "close_price": 110.0, "adjusted_close": 110.0}
        _persist_bulk_rows(db_session, [updated_row])

        persisted = (
            db_session.query(PriceData)
            .filter(PriceData.symbol == "UPSERT", PriceData.interval == "1d")
            .first()
        )
        assert persisted.close_price == 110.0


# ---------------------------------------------------------------------------
# _last_n_trading_dates
# ---------------------------------------------------------------------------
class TestLastNTradingDates:

    def test_returns_list_of_date_strings(self):
        dates = _last_n_trading_dates(3)
        assert isinstance(dates, list)
        assert len(dates) <= 3
        for d in dates:
            pd.Timestamp(d)

    def test_dates_are_in_past(self):
        dates = _last_n_trading_dates(3)
        today = pd.Timestamp.now(tz="UTC").normalize()
        for d in dates:
            assert pd.Timestamp(d, tz="UTC") <= today


# ---------------------------------------------------------------------------
# Integration: validate + persist pipeline
# ---------------------------------------------------------------------------
class TestBulkEodPipeline:

    def test_end_to_end_filter_and_persist(self, db_session):
        if db_session is None:
            pytest.skip("DB session unavailable")
        from backend.models.market_data import PriceData

        for sym in ["AAPL", "MSFT"]:
            db_session.query(PriceData).filter(
                PriceData.symbol == sym,
                PriceData.interval == "1d",
                PriceData.data_source == "fmp_bulk_eod",
            ).delete()
        db_session.commit()

        tracked = {"AAPL", "MSFT"}
        rows = _validate_and_build_rows(SAMPLE_BULK_RESPONSE, tracked)
        assert len(rows) == 2

        count = _persist_bulk_rows(db_session, rows)
        assert count == 2

        for sym in ["AAPL", "MSFT"]:
            bar = (
                db_session.query(PriceData)
                .filter(
                    PriceData.symbol == sym,
                    PriceData.interval == "1d",
                    PriceData.data_source == "fmp_bulk_eod",
                )
                .first()
            )
            assert bar is not None
