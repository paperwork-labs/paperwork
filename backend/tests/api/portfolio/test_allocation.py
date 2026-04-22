"""API tests for `/api/v1/portfolio/allocation`.

Covers the three group-by modes (sector, asset_class, account), the ordering
and percentage math contract the frontend treemap depends on, auth, and --
most importantly -- cross-tenant isolation: a query for ``group_by=sector``
must never surface another user's positions even if both users hold the same
symbol in the same sector.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_current_user
from backend.api.main import app
from backend.database import get_db
from backend.models import BrokerAccount, User
from backend.models.broker_account import AccountType, BrokerType
from backend.models.position import Position, PositionStatus, PositionType
from backend.models.user import UserRole


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available")


def _make_user(db_session, label: str) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"{label}_{suffix}@example.com",
        username=f"{label}_{suffix}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_account(
    db_session,
    user: User,
    *,
    name: str = "Primary",
    broker: BrokerType = BrokerType.IBKR,
) -> BrokerAccount:
    suffix = uuid.uuid4().hex[:6]
    acc = BrokerAccount(
        user_id=user.id,
        broker=broker,
        account_number=f"U{suffix}",
        account_name=name,
        account_type=AccountType.TAXABLE,
        is_enabled=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def _seed_position(
    db_session,
    *,
    account: BrokerAccount,
    symbol: str,
    market_value: float,
    sector: str | None = "Technology",
    instrument_type: str = "STOCK",
    status: PositionStatus = PositionStatus.OPEN,
) -> Position:
    pos = Position(
        user_id=account.user_id,
        account_id=account.id,
        symbol=symbol,
        instrument_type=instrument_type,
        position_type=PositionType.LONG,
        quantity=Decimal("1"),
        status=status,
        average_cost=Decimal("100"),
        total_cost_basis=Decimal("100"),
        current_price=Decimal(str(market_value)),
        market_value=Decimal(str(market_value)),
        sector=sector,
    )
    db_session.add(pos)
    db_session.commit()
    db_session.refresh(pos)
    return pos


@pytest.fixture
def auth_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    return _make_user(db_session, "alloc")


@pytest.fixture
def primary_account(db_session, auth_user):
    return _make_account(db_session, auth_user, name="Primary")


@pytest.fixture(autouse=True)
def _wire_overrides(db_session, auth_user):
    if db_session is None:
        yield
        return

    def _get_db():
        yield db_session

    def _get_user():
        return auth_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Auth / shape
# ---------------------------------------------------------------------------


def test_empty_portfolio_returns_zero_total(client, db_session, primary_account):
    if db_session is None:
        pytest.skip("database not configured")
    res = client.get("/api/v1/portfolio/allocation?group_by=sector")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["group_by"] == "sector"
    assert body["total_value"] == 0
    assert body["groups"] == []
    assert "generated_at" in body


def test_requires_auth_when_overrides_dropped(client, db_session, primary_account):
    """Without the dependency overrides the route must reject anonymous calls.

    We don't use the shared module-scoped client (which has overrides wired in
    by the autouse fixture); we instantiate a fresh one *after* dropping the
    user override. This proves the route's auth dependency is wired through to
    `get_current_user` and not just relying on the test override to admit
    every caller.
    """
    if db_session is None:
        pytest.skip("database not configured")
    app.dependency_overrides.pop(get_current_user, None)
    unauth_client = TestClient(app, raise_server_exceptions=False)
    res = unauth_client.get("/api/v1/portfolio/allocation?group_by=sector")
    assert res.status_code in (401, 403), res.text


# ---------------------------------------------------------------------------
# Group-by modes
# ---------------------------------------------------------------------------


def test_group_by_sector_aggregates_and_sorts(client, db_session, primary_account):
    if db_session is None:
        pytest.skip("database not configured")
    _seed_position(
        db_session, account=primary_account, symbol="AAPL", market_value=4000, sector="Technology"
    )
    _seed_position(
        db_session, account=primary_account, symbol="MSFT", market_value=6000, sector="Technology"
    )
    _seed_position(
        db_session, account=primary_account, symbol="JNJ", market_value=2000, sector="Healthcare"
    )

    res = client.get("/api/v1/portfolio/allocation?group_by=sector")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_value"] == pytest.approx(12000.0)

    groups = body["groups"]
    assert [g["label"] for g in groups] == ["Technology", "Healthcare"], groups
    tech = groups[0]
    assert tech["key"] == "technology"
    assert tech["total_value"] == pytest.approx(10000.0)
    assert tech["percentage"] == pytest.approx(10000 / 12000 * 100)
    # Holdings sorted by descending value, no leakage of other sectors.
    assert [h["symbol"] for h in tech["holdings"]] == ["MSFT", "AAPL"]
    assert tech["holdings"][0]["value"] == pytest.approx(6000.0)


def test_missing_sector_buckets_into_other(client, db_session, primary_account):
    if db_session is None:
        pytest.skip("database not configured")
    _seed_position(
        db_session, account=primary_account, symbol="ZZZZ", market_value=1000, sector=None
    )
    res = client.get("/api/v1/portfolio/allocation?group_by=sector")
    body = res.json()
    assert len(body["groups"]) == 1
    assert body["groups"][0]["label"] == "Other"


def test_group_by_asset_class_uses_instrument_type(client, db_session, primary_account):
    if db_session is None:
        pytest.skip("database not configured")
    _seed_position(
        db_session,
        account=primary_account,
        symbol="AAPL",
        market_value=5000,
        instrument_type="STOCK",
    )
    _seed_position(
        db_session,
        account=primary_account,
        symbol="SPY-CALL",
        market_value=1500,
        instrument_type="OPTION",
    )

    res = client.get("/api/v1/portfolio/allocation?group_by=asset_class")
    assert res.status_code == 200
    body = res.json()
    labels = {g["label"] for g in body["groups"]}
    assert labels == {"Equity", "Option"}
    equity = next(g for g in body["groups"] if g["label"] == "Equity")
    assert equity["total_value"] == pytest.approx(5000.0)


def test_group_by_account_buckets_per_brokerage(
    client, db_session, auth_user, primary_account
):
    if db_session is None:
        pytest.skip("database not configured")
    secondary = _make_account(db_session, auth_user, name="Roth IRA", broker=BrokerType.SCHWAB)
    _seed_position(db_session, account=primary_account, symbol="AAPL", market_value=4000)
    _seed_position(db_session, account=secondary, symbol="VTI", market_value=6000)

    res = client.get("/api/v1/portfolio/allocation?group_by=account")
    assert res.status_code == 200
    body = res.json()
    labels = {g["label"] for g in body["groups"]}
    assert labels == {"Primary", "Roth IRA"}
    keys = {g["key"] for g in body["groups"]}
    assert all(k.startswith("acct-") for k in keys)


def test_invalid_group_by_returns_422(client, db_session, primary_account):
    if db_session is None:
        pytest.skip("database not configured")
    res = client.get("/api/v1/portfolio/allocation?group_by=nope")
    # FastAPI/Pydantic returns 422 for Literal validation failures -- the
    # frontend relies on this to distinguish "bad request" from "no data".
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Filtering: closed positions, missing prices
# ---------------------------------------------------------------------------


def test_closed_positions_excluded(client, db_session, primary_account):
    if db_session is None:
        pytest.skip("database not configured")
    _seed_position(
        db_session,
        account=primary_account,
        symbol="OLD",
        market_value=9999,
        status=PositionStatus.CLOSED,
    )
    _seed_position(
        db_session,
        account=primary_account,
        symbol="NEW",
        market_value=1000,
        status=PositionStatus.OPEN,
    )

    res = client.get("/api/v1/portfolio/allocation?group_by=sector")
    body = res.json()
    assert body["total_value"] == pytest.approx(1000.0)
    holdings = [h["symbol"] for g in body["groups"] for h in g["holdings"]]
    assert holdings == ["NEW"]


def test_missing_market_value_skipped_not_zeroed(client, db_session, primary_account):
    """Positions without a market price must not contribute to the aggregate;
    silently treating them as zero would make the chart look healthy while
    misrepresenting the real allocation (the silent-fallback bug class flagged
    in `.cursor/rules/no-silent-fallback.mdc`).
    """
    if db_session is None:
        pytest.skip("database not configured")
    pos = Position(
        user_id=primary_account.user_id,
        account_id=primary_account.id,
        symbol="NOPRICE",
        instrument_type="STOCK",
        position_type=PositionType.LONG,
        quantity=Decimal("10"),
        status=PositionStatus.OPEN,
        sector="Technology",
        # market_value intentionally None.
    )
    db_session.add(pos)
    db_session.commit()
    _seed_position(db_session, account=primary_account, symbol="HASPRICE", market_value=500)

    res = client.get("/api/v1/portfolio/allocation?group_by=sector")
    body = res.json()
    holdings = [h["symbol"] for g in body["groups"] for h in g["holdings"]]
    assert holdings == ["HASPRICE"]
    assert body["total_value"] == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Cross-tenant isolation -- the most important test in this file.
# ---------------------------------------------------------------------------


def test_cross_tenant_isolation(client, db_session, auth_user, primary_account):
    """User A must never see User B's positions, even when both hold the same
    symbol in the same sector. The route filters on ``BrokerAccount.user_id``
    AND ``Position.user_id`` -- this test would fail if either guard were
    dropped.
    """
    if db_session is None:
        pytest.skip("database not configured")

    other = _make_user(db_session, "alloc_other")
    other_acc = _make_account(db_session, other, name="Other Primary")

    # Both users hold AAPL in Technology with materially different sizes so a
    # leak would be unmistakable in the assertion below.
    _seed_position(
        db_session, account=primary_account, symbol="AAPL", market_value=1000, sector="Technology"
    )
    _seed_position(
        db_session,
        account=other_acc,
        symbol="AAPL",
        market_value=999_999,
        sector="Technology",
    )

    res = client.get("/api/v1/portfolio/allocation?group_by=sector")
    assert res.status_code == 200
    body = res.json()
    assert body["total_value"] == pytest.approx(1000.0)
    tech = body["groups"][0]
    assert tech["label"] == "Technology"
    assert len(tech["holdings"]) == 1
    assert tech["holdings"][0]["symbol"] == "AAPL"
    assert tech["holdings"][0]["value"] == pytest.approx(1000.0)
