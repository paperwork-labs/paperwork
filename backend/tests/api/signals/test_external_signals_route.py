"""Tests for ``GET /api/v1/signals/external``."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_current_user
from backend.api.main import app
from backend.database import get_db
from backend.models.external_signal import ExternalSignal
from backend.models.user import User


def _user(db_session) -> User:
    u = User(
        username="extsig",
        email="extsig@example.com",
        full_name="Test",
        password_hash="x",
    )
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def authed_client(db_session) -> TestClient:
    u = _user(db_session)
    app.dependency_overrides[get_current_user] = lambda: u
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_401_without_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)
    client = TestClient(app, raise_server_exceptions=True)
    r = client.get("/api/v1/signals/external?symbol=AAPL&days=7")
    assert r.status_code == 401


def test_empty_symbol_no_rows(db_session, authed_client) -> None:
    r = authed_client.get("/api/v1/signals/external?symbol=ZZZZ&days=7")
    assert r.status_code == 200
    body = r.json()
    assert body == {"items": []}


def test_returns_rows_newest_first(db_session, authed_client) -> None:
    ts = datetime(2025, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    t0 = date.today()
    d_old = t0 - timedelta(days=20)
    d_new = t0 - timedelta(days=2)
    db_session.add(
        ExternalSignal(
            symbol="AAPL",
            source="zacks",
            signal_date=d_old,
            signal_type="zacks_rank_1",
            value=None,
            raw_payload={},
            created_at=ts,
        )
    )
    db_session.add(
        ExternalSignal(
            symbol="AAPL",
            source="finviz",
            signal_date=d_new,
            signal_type="insider_buy",
            value=None,
            raw_payload={},
            created_at=ts,
        )
    )
    db_session.commit()

    r = authed_client.get("/api/v1/signals/external?symbol=AAPL&days=30")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["signal_date"] == d_new.isoformat()
    assert items[1]["signal_date"] == d_old.isoformat()
    assert items[0]["source"] == "finviz"


def test_batch_returns_per_symbol_newest_first(db_session, authed_client) -> None:
    ts = datetime(2025, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    t0 = date.today()
    d_msft = t0 - timedelta(days=1)
    d_aapl_old = t0 - timedelta(days=5)
    d_aapl_new = t0 - timedelta(days=1)
    db_session.add(
        ExternalSignal(
            symbol="AAPL",
            source="s",
            signal_date=d_aapl_old,
            signal_type="a",
            value=None,
            raw_payload={},
            created_at=ts,
        )
    )
    db_session.add(
        ExternalSignal(
            symbol="AAPL",
            source="s",
            signal_date=d_aapl_new,
            signal_type="b",
            value=None,
            raw_payload={},
            created_at=ts,
        )
    )
    db_session.add(
        ExternalSignal(
            symbol="MSFT",
            source="s2",
            signal_date=d_msft,
            signal_type="c",
            value=None,
            raw_payload={},
            created_at=ts,
        )
    )
    db_session.commit()

    r = authed_client.get(
        "/api/v1/signals/external/batch?symbols=AAPL%2CMSFT%2CAAPL&days=30"
    )
    assert r.status_code == 200
    by_sym = r.json()["by_symbol"]
    assert list(by_sym.keys()) == ["AAPL", "MSFT"]
    aapl = by_sym["AAPL"]
    assert [x["signal_type"] for x in aapl] == ["b", "a"]
    assert len(by_sym["MSFT"]) == 1
    assert by_sym["MSFT"][0]["symbol"] == "MSFT"
