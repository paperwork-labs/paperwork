"""Tests for the position sleeve tagging API.

Covers:
* ``PATCH /api/v1/positions/{id}/sleeve`` updates the sleeve for
  positions owned by the caller.
* Requests for a position owned by another user return 404 (no
  cross-tenant leakage).
* Invalid sleeve values return 400.
* ``GET /api/v1/positions/by-sleeve`` groups the caller's open
  positions by sleeve with ``active`` / ``conviction`` buckets.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.routes.positions import router as positions_router
from app.database import get_db
from app.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerAccount,
    BrokerType,
    SyncStatus,
)
from app.models.position import Position, PositionStatus, PositionType, Sleeve
from app.models.user import User


def _make_user(db_session, *, email: str) -> User:
    u = User(
        username=email.split("@")[0],
        email=email,
        full_name="Sleeve Tester",
        password_hash="x",
    )
    db_session.add(u)
    db_session.flush()
    return u


def _make_account(db_session, *, user_id: int) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user_id,
        account_number=f"ACCT-{user_id}",
        account_name="Test",
        broker=BrokerType.IBKR,
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        sync_status=SyncStatus.SUCCESS,
    )
    db_session.add(acct)
    db_session.flush()
    return acct


def _make_position(
    db_session,
    *,
    user_id: int,
    account_id: int,
    symbol: str,
    sleeve: str | None = None,
) -> Position:
    p = Position(
        user_id=user_id,
        account_id=account_id,
        symbol=symbol,
        quantity=Decimal("10"),
        position_type=PositionType.LONG,
        status=PositionStatus.OPEN,
        sleeve=sleeve,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def app(db_session):
    test_app = FastAPI()
    test_app.include_router(positions_router, prefix="/api/v1")
    test_app.dependency_overrides[get_db] = lambda: db_session
    return test_app


@pytest.fixture
def as_user(app, db_session):
    """Return a helper that swaps the ``get_current_user`` override."""

    def _set(user: User):
        app.dependency_overrides[get_current_user] = lambda: user

    return _set


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


class TestPatchSleeve:
    def test_updates_sleeve_for_owner(self, db_session, client, as_user):
        user = _make_user(db_session, email="owner@example.com")
        acct = _make_account(db_session, user_id=user.id)
        pos = _make_position(
            db_session,
            user_id=user.id,
            account_id=acct.id,
            symbol="AAPL",
            sleeve=Sleeve.ACTIVE.value,
        )
        as_user(user)

        r = client.patch(
            f"/api/v1/positions/{pos.id}/sleeve",
            json={"sleeve": "conviction"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["sleeve"] == "conviction"
        assert body["symbol"] == "AAPL"

        db_session.refresh(pos)
        assert pos.sleeve == Sleeve.CONVICTION.value

    def test_rejects_invalid_sleeve(self, db_session, client, as_user):
        user = _make_user(db_session, email="bad@example.com")
        acct = _make_account(db_session, user_id=user.id)
        pos = _make_position(db_session, user_id=user.id, account_id=acct.id, symbol="MSFT")
        as_user(user)

        r = client.patch(
            f"/api/v1/positions/{pos.id}/sleeve",
            json={"sleeve": "moonshot"},
        )
        assert r.status_code == 400

    def test_cannot_modify_other_users_position(self, db_session, client, as_user):
        owner = _make_user(db_session, email="a@example.com")
        attacker = _make_user(db_session, email="b@example.com")
        acct = _make_account(db_session, user_id=owner.id)
        pos = _make_position(db_session, user_id=owner.id, account_id=acct.id, symbol="NVDA")
        as_user(attacker)

        r = client.patch(
            f"/api/v1/positions/{pos.id}/sleeve",
            json={"sleeve": "conviction"},
        )
        assert r.status_code == 404

        db_session.refresh(pos)
        # Unchanged.
        assert pos.sleeve != Sleeve.CONVICTION.value


class TestListBySleeve:
    def test_groups_positions_by_sleeve(self, db_session, client, as_user):
        user = _make_user(db_session, email="list@example.com")
        acct = _make_account(db_session, user_id=user.id)
        _make_position(
            db_session,
            user_id=user.id,
            account_id=acct.id,
            symbol="AAA",
            sleeve=Sleeve.ACTIVE.value,
        )
        _make_position(
            db_session,
            user_id=user.id,
            account_id=acct.id,
            symbol="BBB",
            sleeve=Sleeve.CONVICTION.value,
        )
        _make_position(
            db_session,
            user_id=user.id,
            account_id=acct.id,
            symbol="CCC",
            sleeve=None,  # null -> defaults to 'active' bucket
        )
        as_user(user)

        r = client.get("/api/v1/positions/by-sleeve")
        assert r.status_code == 200, r.text
        body = r.json()
        groups = body["items_by_sleeve"]
        assert "active" in groups
        assert "conviction" in groups
        active_syms = {p["symbol"] for p in groups["active"]}
        conv_syms = {p["symbol"] for p in groups["conviction"]}
        assert "AAA" in active_syms
        assert "CCC" in active_syms  # null coerced to active
        assert "BBB" in conv_syms
        assert body["total"] == 3

    def test_only_returns_own_positions(self, db_session, client, as_user):
        owner = _make_user(db_session, email="owner2@example.com")
        other = _make_user(db_session, email="other2@example.com")
        acct_o = _make_account(db_session, user_id=owner.id)
        acct_x = _make_account(db_session, user_id=other.id)
        _make_position(
            db_session,
            user_id=owner.id,
            account_id=acct_o.id,
            symbol="MINE",
            sleeve=Sleeve.ACTIVE.value,
        )
        _make_position(
            db_session,
            user_id=other.id,
            account_id=acct_x.id,
            symbol="YOURS",
            sleeve=Sleeve.CONVICTION.value,
        )
        as_user(owner)

        r = client.get("/api/v1/positions/by-sleeve")
        assert r.status_code == 200
        body = r.json()
        seen = {p["symbol"] for group in body["items_by_sleeve"].values() for p in group}
        assert "MINE" in seen
        assert "YOURS" not in seen
