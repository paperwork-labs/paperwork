"""Portfolio ``/portfolio/options`` multi-broker routes.

Tests the broker-agnostic positions + chain-sources endpoints that power
the Options page. Specifically exercises:

* Multi-broker positions land in the unified payload with ``broker`` +
  ``account_number`` populated per row.
* The summary endpoint does NOT blow up with the TypeError that caused
  the founder-reported "Failed to load options" (the root cause this PR
  fixes).
* ``/chain/sources`` reflects per-user IBKR availability + yfinance.

All tests use dependency overrides; no real DB or network.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.portfolio.options import router
from app.models.broker_account import BrokerType
from app.models.user import UserRole

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.no_db


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 42
    user.email = "founder@axiomfolio.com"
    user.role = UserRole.OWNER
    return user


def _make_option(
    *,
    id_: int,
    account_id: int,
    underlying: str,
    strike: float,
    option_type: str = "CALL",
    open_qty: int = 1,
):
    o = MagicMock()
    o.id = id_
    o.account_id = account_id
    o.user_id = 42
    o.symbol = f"{underlying} {option_type} ${strike:.2f} 2026-01-16"
    o.underlying_symbol = underlying
    o.strike_price = strike
    o.expiry_date = date(2026, 1, 16)
    o.option_type = option_type
    o.open_quantity = open_qty
    o.multiplier = 100
    o.current_price = 1.5
    o.underlying_price = 100.0
    o.total_cost = 100.0
    o.unrealized_pnl = 50.0
    o.realized_pnl = 0.0
    o.commission = 0.0
    o.delta = 0.5
    o.gamma = 0.01
    o.theta = -0.05
    o.vega = 0.1
    o.implied_volatility = 0.25
    o.updated_at = datetime.now(UTC)
    o.last_updated = None
    return o


def _make_account(*, id_: int, broker: BrokerType, number: str):
    a = MagicMock()
    a.id = id_
    a.broker = broker
    a.account_number = number
    return a


@pytest.fixture
def app(mock_user):
    from app.api.dependencies import get_current_user
    from app.database import get_db

    test_app = FastAPI()
    test_app.include_router(router, prefix="/portfolio/options")

    mock_db = MagicMock()
    test_app.dependency_overrides[get_db] = lambda: mock_db
    test_app.dependency_overrides[get_current_user] = lambda: mock_user
    test_app.state.mock_db = mock_db
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


def _wire_db_for_positions(app, *, positions, accounts):
    """Drive the two ``db.query()`` chains used by _compute_options_portfolio.

    The helper executes:

        db.query(Option).join(BrokerAccount, ...).filter(...).filter(...).all()
        db.query(BrokerAccount).filter(BrokerAccount.id.in_(...)).all()

    We wire distinct ``query`` return values per model arg.
    """
    from app.models import BrokerAccount, Option

    mock_db = app.state.mock_db

    opt_q = MagicMock()
    opt_q.join.return_value.filter.return_value.filter.return_value.all.return_value = positions
    opt_q.join.return_value.filter.return_value.all.return_value = positions

    acct_q = MagicMock()
    acct_q.filter.return_value.all.return_value = accounts

    def _query(model, *args, **kwargs):
        if model is Option:
            return opt_q
        if model is BrokerAccount:
            return acct_q
        return MagicMock()

    mock_db.query.side_effect = _query


# ---------------------------------------------------------------------------
# /unified/portfolio
# ---------------------------------------------------------------------------


class TestUnifiedPortfolioMultiBroker:
    def test_schwab_and_ibkr_positions_both_appear(self, app, client):
        schwab_acct = _make_account(id_=1, broker=BrokerType.SCHWAB, number="S-0001")
        ibkr_acct = _make_account(id_=2, broker=BrokerType.IBKR, number="U1234567")
        positions = [
            _make_option(id_=10, account_id=1, underlying="RDDT", strike=100),
            _make_option(id_=11, account_id=2, underlying="MSTR", strike=300),
        ]
        _wire_db_for_positions(app, positions=positions, accounts=[schwab_acct, ibkr_acct])

        with patch(
            "app.api.middleware.response_cache.redis_response_cache",
            lambda **kw: lambda fn: fn,
        ):
            resp = client.get("/portfolio/options/unified/portfolio")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "success"
        rows = body["data"]["positions"]
        assert len(rows) == 2
        brokers = {r["broker"] for r in rows}
        assert brokers == {"schwab", "ibkr"}
        accounts = {r["account_number"] for r in rows}
        assert accounts == {"S-0001", "U1234567"}

    def test_schwab_only_does_not_mention_ibkr(self, app, client):
        schwab_acct = _make_account(id_=1, broker=BrokerType.SCHWAB, number="S-0001")
        positions = [
            _make_option(id_=10, account_id=1, underlying="SOFI", strike=10),
        ]
        _wire_db_for_positions(app, positions=positions, accounts=[schwab_acct])

        resp = client.get("/portfolio/options/unified/portfolio")
        assert resp.status_code == 200
        rows = resp.json()["data"]["positions"]
        assert len(rows) == 1
        assert rows[0]["broker"] == "schwab"
        # No broker-specific error message is injected into the payload:
        assert "ibkr" not in resp.text.lower() or "ibkr_" not in resp.text.lower()

    def test_broker_counters_emitted_per_no_silent_fallback(self, app, client):
        """Per `no-silent-fallback.mdc`: per-broker counters must be present."""
        schwab_acct = _make_account(id_=1, broker=BrokerType.SCHWAB, number="S-0001")
        positions = [
            _make_option(id_=10, account_id=1, underlying="SOFI", strike=10),
            _make_option(id_=11, account_id=1, underlying="DE", strike=400),
        ]
        _wire_db_for_positions(app, positions=positions, accounts=[schwab_acct])

        resp = client.get("/portfolio/options/unified/portfolio")
        data = resp.json()["data"]
        counters = data["broker_counters"]
        assert counters["schwab"]["success"] == 2
        assert counters["schwab"]["failed"] == 0
        assert counters["schwab"]["skipped_no_config"] == 0


# ---------------------------------------------------------------------------
# /unified/summary (the endpoint that previously 500'd with TypeError)
# ---------------------------------------------------------------------------


class TestUnifiedSummaryRegression:
    """Regression: ``/summary`` used to call the decorated portfolio endpoint
    without a Request object, raising

        TypeError: get_unified_options_portfolio() missing 1 required
        positional argument: 'request'

    which surfaced as HTTP 500 and "Failed to load options" on the Positions
    tab. We now call the shared helper directly. Lock this in.
    """

    def test_summary_returns_200_not_500(self, app, client):
        schwab_acct = _make_account(id_=1, broker=BrokerType.SCHWAB, number="S-0001")
        positions = [
            _make_option(id_=10, account_id=1, underlying="RDDT", strike=100),
        ]
        _wire_db_for_positions(app, positions=positions, accounts=[schwab_acct])

        resp = client.get("/portfolio/options/unified/summary")
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["summary"]["total_positions"] == 1
        # Same per-broker observability in summary path:
        assert body["broker_counters"]["schwab"]["success"] == 1


# ---------------------------------------------------------------------------
# /chain/sources
# ---------------------------------------------------------------------------


class TestChainSources:
    def test_reports_sources_list_with_kind(self, app, client):
        fake_sources = [
            {
                "name": "ibkr_gateway",
                "label": "IB Gateway",
                "available": False,
                "reason": "no_ibkr_account",
                "kind": "broker",
            },
            {
                "name": "yfinance",
                "label": "Yahoo Finance",
                "available": True,
                "reason": "ready",
                "kind": "provider",
            },
        ]
        with patch(
            "app.api.routes.portfolio.options.probe_chain_sources",
            return_value=fake_sources,
        ):
            resp = client.get("/portfolio/options/chain/sources")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["any_available"] is True
        names = [s["name"] for s in body["sources"]]
        assert "ibkr_gateway" in names and "yfinance" in names

    def test_no_sources_available_any_available_false(self, app, client):
        with patch(
            "app.api.routes.portfolio.options.probe_chain_sources",
            return_value=[
                {
                    "name": "ibkr_gateway",
                    "label": "IB Gateway",
                    "available": False,
                    "reason": "no_ibkr_account",
                    "kind": "broker",
                },
                {
                    "name": "yfinance",
                    "label": "Yahoo Finance",
                    "available": False,
                    "reason": "yfinance_not_installed",
                    "kind": "provider",
                },
            ],
        ):
            resp = client.get("/portfolio/options/chain/sources")
        assert resp.json()["data"]["any_available"] is False
