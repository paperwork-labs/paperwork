"""Integration tests for ``CorporateActionFetcher``.

The fetcher's only correctness contract is:

1. Translate FMP payloads into ``CorporateAction`` rows correctly.
2. Be idempotent on ``(symbol, action_type, ex_date)``.
3. Isolate per-symbol HTTP failures (one bad response must not abort
   the whole sweep).

We stub the HTTP layer with a callable so no network is touched.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock

import pytest
from sqlalchemy import inspect, select

from app.models.corporate_action import (
    CorporateAction,
    CorporateActionSource,
    CorporateActionStatus,
    CorporateActionType,
)
from app.services.corporate_actions.fetcher import CorporateActionFetcher


@pytest.fixture(autouse=True)
def _require_schema(db_session):
    if db_session is None:
        pytest.skip("DB-backed test requires db_session")
    inspector = inspect(db_session.bind)
    if not inspector.has_table("corporate_actions"):
        pytest.skip("corporate_actions table not present in test DB")


def _stub_http(payloads: Dict[str, Any]) -> Callable[..., Any]:
    """Build a fake ``requests.get`` that returns canned payloads keyed by URL."""

    def _get(url: str, *, params: Optional[Dict[str, Any]] = None, timeout: int = 30):
        body = None
        for needle, value in payloads.items():
            if needle in url:
                body = value
                break
        if body is None:
            body = {"historical": []}
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=body)
        return resp

    return _get


def test_fetcher_inserts_split_and_dividend_actions(db_session):
    db = db_session
    payloads = {
        "stock_split/AAPL": {
            "symbol": "AAPL",
            "historical": [
                {
                    "date": "2025-06-15",
                    "label": "June 15, 25",
                    "numerator": 4.0,
                    "denominator": 1.0,
                }
            ],
        },
        "stock_dividend/AAPL": {
            "symbol": "AAPL",
            "historical": [
                {
                    "date": "2025-05-09",
                    "label": "May 9, 25",
                    "dividend": 0.25,
                    "adjDividend": 0.25,
                    "recordDate": "2025-05-08",
                    "paymentDate": "2025-05-15",
                }
            ],
        },
    }
    fetcher = CorporateActionFetcher(db, api_key="fake", http_get=_stub_http(payloads))

    report = fetcher.fetch_for_symbols(["AAPL"], since_date=date(2025, 1, 1))
    db.flush()

    assert report.symbols_total == 1
    assert report.symbols_fetched == 1
    assert report.symbols_errored == 0
    assert report.actions_inserted == 2

    rows = (
        db.execute(select(CorporateAction).where(CorporateAction.symbol == "AAPL"))
        .scalars()
        .all()
    )
    assert len(rows) == 2

    split = next(r for r in rows if r.action_type == CorporateActionType.SPLIT.value)
    assert split.ex_date == date(2025, 6, 15)
    assert split.ratio_numerator == Decimal("4")
    assert split.ratio_denominator == Decimal("1")
    assert split.source == CorporateActionSource.FMP.value
    assert split.status == CorporateActionStatus.PENDING.value

    div = next(
        r for r in rows if r.action_type == CorporateActionType.CASH_DIVIDEND.value
    )
    assert div.cash_amount == Decimal("0.25")
    assert div.payment_date == date(2025, 5, 15)


def test_fetcher_is_idempotent_on_symbol_type_exdate(db_session):
    db = db_session
    payloads = {
        "stock_split/MSFT": {
            "historical": [
                {
                    "date": "2025-04-01",
                    "label": "April 1, 25",
                    "numerator": 2,
                    "denominator": 1,
                }
            ],
        },
    }
    fetcher = CorporateActionFetcher(db, api_key="fake", http_get=_stub_http(payloads))

    first = fetcher.fetch_for_symbols(["MSFT"], since_date=date(2025, 1, 1))
    db.flush()
    second = fetcher.fetch_for_symbols(["MSFT"], since_date=date(2025, 1, 1))
    db.flush()

    assert first.actions_inserted == 1
    assert second.actions_inserted == 0
    assert second.actions_skipped_duplicate == 1

    count = (
        db.execute(
            select(CorporateAction).where(CorporateAction.symbol == "MSFT")
        )
        .scalars()
        .all()
    )
    assert len(count) == 1


def test_fetcher_isolates_per_symbol_http_failure(db_session):
    db = db_session

    def _get(url: str, *, params=None, timeout=30):
        if "BORK" in url:
            raise RuntimeError("simulated 500")
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"historical": []})
        return resp

    fetcher = CorporateActionFetcher(db, api_key="fake", http_get=_get)
    report = fetcher.fetch_for_symbols(
        ["GOOD", "BORK", "ALSO_GOOD"], since_date=date(2025, 1, 1)
    )

    assert report.symbols_total == 3
    assert report.symbols_fetched == 2
    assert report.symbols_errored == 1
    assert "BORK" in report.errored_symbols


def test_fetcher_filters_out_actions_before_since_date(db_session):
    db = db_session
    payloads = {
        "stock_split/AMZN": {
            "historical": [
                {
                    "date": "2024-01-01",
                    "label": "Jan 1, 24",
                    "numerator": 2,
                    "denominator": 1,
                },
                {
                    "date": "2025-06-01",
                    "label": "Jun 1, 25",
                    "numerator": 3,
                    "denominator": 1,
                },
            ],
        },
    }
    fetcher = CorporateActionFetcher(db, api_key="fake", http_get=_stub_http(payloads))
    report = fetcher.fetch_for_symbols(["AMZN"], since_date=date(2025, 1, 1))
    db.flush()

    assert report.actions_inserted == 1
    rows = (
        db.execute(select(CorporateAction).where(CorporateAction.symbol == "AMZN"))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].ex_date == date(2025, 6, 1)


def test_fetcher_fails_loud_when_api_key_missing(db_session):
    db = db_session
    fetcher = CorporateActionFetcher(db, api_key=None, http_get=_stub_http({}))
    report = fetcher.fetch_for_symbols(["AAPL", "MSFT"], since_date=date(2025, 1, 1))

    assert report.symbols_errored == 2
    assert report.actions_inserted == 0
    assert report.errored_symbols == ["AAPL", "MSFT"]


def test_fetcher_classifies_reverse_split_when_numerator_lt_denominator(db_session):
    db = db_session
    payloads = {
        "stock_split/REVS": {
            "historical": [
                {
                    "date": "2025-08-01",
                    "label": "Aug 1, 25",
                    "numerator": 1,
                    "denominator": 10,
                }
            ],
        },
    }
    fetcher = CorporateActionFetcher(db, api_key="fake", http_get=_stub_http(payloads))
    fetcher.fetch_for_symbols(["REVS"], since_date=date(2025, 1, 1))
    db.flush()

    row = (
        db.execute(select(CorporateAction).where(CorporateAction.symbol == "REVS"))
        .scalar_one()
    )
    assert row.action_type == CorporateActionType.REVERSE_SPLIT.value
    assert row.ratio_numerator == Decimal("1")
    assert row.ratio_denominator == Decimal("10")
