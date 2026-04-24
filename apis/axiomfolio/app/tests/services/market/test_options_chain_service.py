"""Tests for ``app.services.silver.market.options_chain_service``.

Covers the broker-agnostic fallback chain:

* IBKR gateway available + returns data -> return IBKR payload.
* IBKR unavailable, yfinance returns rows -> return yfinance payload.
* Every source fails / empty -> ``source == "none"`` with observability.
* ``probe_sources`` accurately reports availability + reasons.

These tests intentionally stub every external import (``ibkr_client``,
``fetch_yfinance_options_chain``) so they run in CI without network or a
live IB Gateway.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.silver.market import options_chain_service as svc

# Pure-unit suite: no DB, no network. Skips the heavy conftest DB fixture.
pytestmark = pytest.mark.no_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_without_ibkr():
    """SQLAlchemy session mock whose IBKR account lookup returns None."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def _db_with_ibkr():
    """SQLAlchemy session mock whose IBKR account lookup returns a row."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock()
    return db


# ---------------------------------------------------------------------------
# probe_sources
# ---------------------------------------------------------------------------


class TestProbeSources:
    def test_no_ibkr_account_flags_ibkr_unavailable(self):
        db = _db_without_ibkr()
        with patch.object(svc, "_yfinance_availability", return_value=(True, "ready")):
            sources = svc.probe_sources(db=db, user_id=1)
        ibkr = next(s for s in sources if s["name"] == "ibkr_gateway")
        assert ibkr["available"] is False
        assert ibkr["reason"] == "no_ibkr_account"
        assert ibkr["kind"] == "broker"

    def test_yfinance_marked_as_provider(self):
        db = _db_without_ibkr()
        with patch.object(svc, "_yfinance_availability", return_value=(True, "ready")):
            sources = svc.probe_sources(db=db, user_id=1)
        yf = next(s for s in sources if s["name"] == "yfinance")
        assert yf["available"] is True
        assert yf["kind"] == "provider"

    def test_yfinance_missing_import_is_reported(self):
        db = _db_without_ibkr()
        with patch.object(
            svc, "_yfinance_availability", return_value=(False, "yfinance_not_installed")
        ):
            sources = svc.probe_sources(db=db, user_id=1)
        yf = next(s for s in sources if s["name"] == "yfinance")
        assert yf["available"] is False
        assert yf["reason"] == "yfinance_not_installed"


# ---------------------------------------------------------------------------
# get_chain
# ---------------------------------------------------------------------------


class TestGetChain:
    @pytest.mark.asyncio
    async def test_empty_symbol_returns_none_source(self):
        db = _db_without_ibkr()
        result = await svc.get_chain("", user_id=1, db=db)
        assert result["source"] == "none"
        assert result["expirations"] == []
        assert result["chains"] == {}

    @pytest.mark.asyncio
    async def test_ibkr_success_short_circuits_yfinance(self):
        """IBKR available + returns data -> never calls yfinance."""
        db = _db_with_ibkr()
        fake_chain = {
            "expirations": ["2026-01-16"],
            "chains": {
                "2026-01-16": {
                    "calls": [{"strike": 100.0}],
                    "puts": [{"strike": 100.0}],
                }
            },
        }
        fake_client = MagicMock()

        async def _get_chain(_sym):
            return fake_chain

        fake_client.get_option_chain = _get_chain
        fake_client.is_connected.return_value = True

        # yfinance stub should NEVER be called if IBKR succeeds.
        yf_stub = MagicMock(name="fetch_yfinance_options_chain")

        with patch.dict(
            "sys.modules",
            {
                "app.services.clients.ibkr_client": MagicMock(
                    IBKR_AVAILABLE=True, ibkr_client=fake_client
                ),
                "app.services.silver.market.yfinance_options_chain": MagicMock(
                    fetch_yfinance_options_chain=yf_stub
                ),
            },
        ):
            result = await svc.get_chain("AAPL", user_id=1, db=db)

        assert result["source"] == "ibkr_gateway"
        assert result["symbol"] == "AAPL"
        assert result["expirations"] == ["2026-01-16"]
        yf_stub.assert_not_called()

    @pytest.mark.asyncio
    async def test_ibkr_unavailable_falls_back_to_yfinance(self):
        """No IBKR account / gateway off -> use yfinance."""
        db = _db_without_ibkr()
        yf_rows = [
            {
                "expiry": date(2026, 1, 16),
                "strike": 100.0,
                "option_type": "CALL",
                "bid": 1.1,
                "ask": 1.2,
                "implied_vol": 0.25,
                "volume": 100,
                "open_interest": 50,
            },
            {
                "expiry": date(2026, 1, 16),
                "strike": 95.0,
                "option_type": "PUT",
                "bid": 0.5,
                "ask": 0.6,
            },
        ]
        yf_stub = MagicMock(return_value=yf_rows)

        with patch.dict(
            "sys.modules",
            {
                "app.services.silver.market.yfinance_options_chain": MagicMock(
                    fetch_yfinance_options_chain=yf_stub
                ),
            },
        ):
            result = await svc.get_chain("AAPL", user_id=1, db=db)

        assert result["source"] == "yfinance"
        assert result["symbol"] == "AAPL"
        assert result["expirations"] == ["2026-01-16"]
        assert "2026-01-16" in result["chains"]
        bucket = result["chains"]["2026-01-16"]
        assert len(bucket["calls"]) == 1
        assert len(bucket["puts"]) == 1
        yf_stub.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_ibkr_returns_empty_falls_through_to_yfinance(self):
        """IBKR connected but chain is empty -> yfinance gets a shot."""
        db = _db_with_ibkr()

        async def _empty_chain(_sym):
            return {"expirations": [], "chains": {}}

        fake_client = MagicMock()
        fake_client.get_option_chain = _empty_chain
        fake_client.is_connected.return_value = True

        yf_stub = MagicMock(
            return_value=[
                {"expiry": date(2026, 2, 20), "strike": 10, "option_type": "CALL"}
            ]
        )

        with patch.dict(
            "sys.modules",
            {
                "app.services.clients.ibkr_client": MagicMock(
                    IBKR_AVAILABLE=True, ibkr_client=fake_client
                ),
                "app.services.silver.market.yfinance_options_chain": MagicMock(
                    fetch_yfinance_options_chain=yf_stub
                ),
            },
        ):
            result = await svc.get_chain("SOFI", user_id=1, db=db)

        assert result["source"] == "yfinance"
        assert result["expirations"] == ["2026-02-20"]

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_none_with_attempts(self):
        """Every source exhausted -> ``source='none'`` + trace in attempts."""
        db = _db_without_ibkr()
        with patch.object(
            svc, "_yfinance_availability", return_value=(False, "yfinance_not_installed")
        ):
            result = await svc.get_chain("XYZ", user_id=1, db=db)
        assert result["source"] == "none"
        names = [a["name"] for a in result["attempts"]]
        assert "ibkr_gateway" in names
        assert "yfinance" in names
        # No silent empty: the caller can distinguish "no data" from
        # "unexpected exception" via ``attempts[*].error`` and
        # ``attempts[*].available``.
        ibkr_attempt = next(a for a in result["attempts"] if a["name"] == "ibkr_gateway")
        yf_attempt = next(a for a in result["attempts"] if a["name"] == "yfinance")
        assert ibkr_attempt["available"] is False
        assert yf_attempt["available"] is False

    @pytest.mark.asyncio
    async def test_yfinance_raises_is_captured(self):
        """yfinance blowing up must not crash the route — caller sees 'none'."""
        db = _db_without_ibkr()
        yf_stub = MagicMock(side_effect=RuntimeError("yahoo down"))

        with patch.dict(
            "sys.modules",
            {
                "app.services.silver.market.yfinance_options_chain": MagicMock(
                    fetch_yfinance_options_chain=yf_stub
                ),
            },
        ):
            result = await svc.get_chain("AAPL", user_id=1, db=db)

        assert result["source"] == "none"
        yf_attempt = next(a for a in result["attempts"] if a["name"] == "yfinance")
        assert yf_attempt["succeeded"] is False
        assert "yahoo down" in (yf_attempt["error"] or "")


# ---------------------------------------------------------------------------
# _shape_yfinance_rows
# ---------------------------------------------------------------------------


class TestShapeYfinanceRows:
    def test_groups_by_expiration_and_type(self):
        rows = [
            {"expiry": date(2026, 1, 16), "strike": 100, "option_type": "CALL"},
            {"expiry": date(2026, 1, 16), "strike": 95, "option_type": "PUT"},
            {"expiry": date(2026, 3, 20), "strike": 100, "option_type": "CALL"},
        ]
        shaped = svc._shape_yfinance_rows(rows)
        assert shaped["expirations"] == ["2026-01-16", "2026-03-20"]
        assert len(shaped["chains"]["2026-01-16"]["calls"]) == 1
        assert len(shaped["chains"]["2026-01-16"]["puts"]) == 1
        assert len(shaped["chains"]["2026-03-20"]["calls"]) == 1

    def test_skips_rows_without_strike(self):
        rows = [
            {"expiry": date(2026, 1, 16), "strike": None, "option_type": "CALL"},
            {"expiry": date(2026, 1, 16), "strike": 100, "option_type": "CALL"},
        ]
        shaped = svc._shape_yfinance_rows(rows)
        assert len(shaped["chains"]["2026-01-16"]["calls"]) == 1

    def test_skips_rows_without_expiry(self):
        rows = [
            {"expiry": None, "strike": 100, "option_type": "CALL"},
            {"expiry": date(2026, 1, 16), "strike": 100, "option_type": "CALL"},
        ]
        shaped = svc._shape_yfinance_rows(rows)
        assert shaped["expirations"] == ["2026-01-16"]
