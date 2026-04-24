"""Route tests for GET /api/v1/options/chain/{symbol}."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models.watchlist import Watchlist

try:
    from fastapi.testclient import TestClient

    from app.api.main import app

    _HAS_APP = True
except Exception:
    _HAS_APP = False

from app.database import get_db
from app.tests.auth_test_utils import approve_user_for_login_tests


@pytest.fixture(scope="module")
def client():
    if not _HAS_APP:
        pytest.skip("app not importable")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_with_db(client, db_session):
    """API requests use the test transaction so ORM data is visible to routes."""
    if db_session is None:
        yield client
        return

    def _ov():
        yield db_session

    app.dependency_overrides[get_db] = _ov
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _register_and_login(
    client,
    username: str,
    password: str,
    email: str,
    db=None,
) -> str:
    r = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User",
        },
    )
    assert r.status_code == 200
    approve_user_for_login_tests(username, db=db)
    r2 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    return r2.json()["access_token"]


def test_user_cannot_read_symbol_only_in_other_watchlist(client_with_db, db_session):
    au = f"a_{uuid.uuid4().hex[:6]}"
    bu = f"b_{uuid.uuid4().hex[:6]}"
    ta = _register_and_login(client_with_db, au, "Passw0rd!", f"{au}@t.com", db=db_session)
    _register_and_login(client_with_db, bu, "Passw0rd!", f"{bu}@t.com", db=db_session)
    from app.models.user import User

    ub = db_session.query(User).filter(User.username == bu).one()
    db_session.add(Watchlist(user_id=ub.id, symbol="ZZTOP"))
    db_session.commit()

    r = client_with_db.get(
        "/api/v1/options/chain/ZZTOP",
        headers={"Authorization": f"Bearer {ta}"},
    )
    assert r.status_code == 404


def test_source_unavailable_returns_503(client_with_db, db_session, monkeypatch):
    u = f"u_{uuid.uuid4().hex[:6]}"
    token = _register_and_login(client_with_db, u, "Passw0rd!", f"{u}@t.com", db=db_session)
    from app.models.user import User

    usr = db_session.query(User).filter(User.username == u).one()
    db_session.add(Watchlist(user_id=usr.id, symbol="NODATA"))
    db_session.commit()

    def _boom(*a, **k):
        from app.services.gold.options_chain_surface import (
            ChainSourceUnavailableError,
        )

        raise ChainSourceUnavailableError("no chain")

    monkeypatch.setattr(
        "app.services.gold.options_chain_surface.OptionsChainSurface.resolve_rows",
        _boom,
    )
    r = client_with_db.get(
        "/api/v1/options/chain/NODATA?fresh=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 503


def test_read_latest_snapshot_200(client_with_db, db_session):
    from app.models.market.options_chain_snapshot import (
        OptionsChainSnapshot,
    )
    from app.models.user import User

    u = f"read_{uuid.uuid4().hex[:6]}"
    token = _register_and_login(client_with_db, u, "Passw0rd!", f"{u}@t.com", db=db_session)
    usr = db_session.query(User).filter(User.username == u).one()
    db_session.add(Watchlist(user_id=usr.id, symbol="READX"))
    ts = datetime.now(UTC)
    db_session.add(
        OptionsChainSnapshot(
            symbol="READX",
            expiry=date(2026, 6, 19),
            strike=Decimal("50"),
            option_type="CALL",
            bid=Decimal("1.0"),
            ask=Decimal("1.1"),
            mid=Decimal("1.05"),
            spread_abs=Decimal("0.1"),
            spread_rel=Decimal("0.095238"),
            open_interest=10,
            volume=5,
            implied_vol=Decimal("0.3"),
            iv_pctile_1y=None,
            iv_rank_1y=None,
            liquidity_score=Decimal("0.4"),
            snapshot_taken_at=ts,
            source="yfinance",
        )
    )
    db_session.commit()

    r = client_with_db.get(
        "/api/v1/options/chain/READX?fresh=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "READX"
    assert body["source"] == "yfinance"
    assert len(body["expiries"]) >= 1
