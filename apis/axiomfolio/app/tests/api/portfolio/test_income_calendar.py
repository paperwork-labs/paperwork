"""API tests for `/api/v1/portfolio/income/calendar`.

Covers:
  - Authentication required (no override → 401/403)
  - `past` mode aggregates user's dividends by `pay_date`
  - `projection` mode scales by current shares and inferred cadence
  - Symbols sold out are excluded from projection
  - Symbols with insufficient history (< 2 payments) are excluded
  - Cross-tenant isolation (User A never sees User B's data)
  - Query-parameter validation (`mode`, `months`)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.main import app
from app.database import get_db
from app.models import BrokerAccount, User
from app.models.broker_account import AccountType, BrokerType, SyncStatus
from app.models.position import Position, PositionStatus, PositionType
from app.models.transaction import Dividend
from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available")


@pytest.fixture
def auth_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"income_{suffix}@example.com",
        username=f"income_{suffix}",
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


@pytest.fixture
def broker_account(db_session, auth_user):
    suffix = uuid.uuid4().hex[:6]
    acc = BrokerAccount(
        user_id=auth_user.id,
        broker=BrokerType.IBKR,
        account_number=f"U{suffix}",
        account_name="Primary",
        account_type=AccountType.TAXABLE,
        sync_status=SyncStatus.NEVER_SYNCED,
        is_enabled=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


@pytest.fixture
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
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_dividend(
    db_session,
    *,
    account_id: int,
    symbol: str,
    pay_date: datetime,
    dividend_per_share: float = 0.5,
    shares_held: float = 10.0,
    tax_withheld: float = 0.0,
):
    total = dividend_per_share * shares_held
    div = Dividend(
        account_id=account_id,
        symbol=symbol,
        ex_date=pay_date - timedelta(days=2),
        pay_date=pay_date,
        dividend_per_share=dividend_per_share,
        shares_held=shares_held,
        total_dividend=total,
        tax_withheld=tax_withheld,
        net_dividend=total - tax_withheld,
        currency="USD",
    )
    db_session.add(div)
    return div


def _seed_position(
    db_session,
    *,
    user_id: int,
    account_id: int,
    symbol: str,
    quantity: float,
    instrument_type: str = "STOCK",
):
    pos = Position(
        user_id=user_id,
        account_id=account_id,
        symbol=symbol,
        instrument_type=instrument_type,
        position_type=PositionType.LONG,
        quantity=Decimal(str(quantity)),
        status=PositionStatus.OPEN,
        average_cost=Decimal("100.00"),
        total_cost_basis=Decimal(str(quantity)) * Decimal("100.00"),
    )
    db_session.add(pos)
    return pos


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_requires_authentication(client, db_session):
    """Without the dependency override the request must be rejected."""
    if db_session is None:
        pytest.skip("database not configured")
    res = client.get("/api/v1/portfolio/income/calendar?mode=past&months=12")
    assert res.status_code in (401, 403), res.text


def test_invalid_mode_returns_400(
    client, db_session, _wire_overrides, broker_account
):
    res = client.get("/api/v1/portfolio/income/calendar?mode=garbage")
    assert res.status_code == 400


def test_months_validation(client, db_session, _wire_overrides, broker_account):
    # months=0 violates ge=1
    res = client.get("/api/v1/portfolio/income/calendar?mode=past&months=0")
    assert res.status_code == 422
    # months=99 violates le=24
    res = client.get("/api/v1/portfolio/income/calendar?mode=past&months=99")
    assert res.status_code == 422


def test_past_mode_aggregates_by_pay_date(
    client, db_session, _wire_overrides, broker_account
):
    today = datetime.now(timezone.utc)
    # Two dividends on the same pay date, plus one in a different month.
    pay1 = today - timedelta(days=30)
    pay2 = today - timedelta(days=120)
    _seed_dividend(
        db_session,
        account_id=broker_account.id,
        symbol="AAPL",
        pay_date=pay1,
        dividend_per_share=0.24,
        shares_held=100.0,
        tax_withheld=2.40,
    )
    _seed_dividend(
        db_session,
        account_id=broker_account.id,
        symbol="MSFT",
        pay_date=pay1,
        dividend_per_share=0.75,
        shares_held=50.0,
        tax_withheld=3.75,
    )
    _seed_dividend(
        db_session,
        account_id=broker_account.id,
        symbol="AAPL",
        pay_date=pay2,
        dividend_per_share=0.24,
        shares_held=100.0,
    )
    db_session.commit()

    res = client.get("/api/v1/portfolio/income/calendar?mode=past&months=12")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "past"
    assert body["tax_data_available"] is True
    assert len(body["monthly_totals"]) >= 12

    cells = body["cells"]
    pay1_iso = pay1.date().isoformat()
    pay2_iso = pay2.date().isoformat()

    pay1_cell = next(c for c in cells if c["date"] == pay1_iso)
    # 0.24*100 + 0.75*50 = 24 + 37.5 = 61.50
    assert pay1_cell["total"] == pytest.approx(61.5)
    # tax: 2.40 + 3.75 = 6.15
    assert pay1_cell["tax_withheld"] == pytest.approx(6.15)
    symbols_on_day = {b["symbol"] for b in pay1_cell["by_symbol"]}
    assert symbols_on_day == {"AAPL", "MSFT"}
    # MSFT (37.5) > AAPL (24.0) — bigger contributor first.
    assert [b["symbol"] for b in pay1_cell["by_symbol"]] == ["MSFT", "AAPL"]

    pay2_cell = next(c for c in cells if c["date"] == pay2_iso)
    assert pay2_cell["total"] == pytest.approx(24.0)


def test_past_mode_isolates_other_users(
    client, db_session, auth_user, broker_account, _wire_overrides
):
    # Seed another user with their own dividend; the auth_user must not
    # see it through the calendar endpoint.
    other = User(
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        username=f"other_{uuid.uuid4().hex[:6]}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    other_acc = BrokerAccount(
        user_id=other.id,
        broker=BrokerType.IBKR,
        account_number=f"U{uuid.uuid4().hex[:6]}",
        account_type=AccountType.TAXABLE,
        is_enabled=True,
    )
    db_session.add(other_acc)
    db_session.commit()
    db_session.refresh(other_acc)

    today = datetime.now(timezone.utc)
    _seed_dividend(
        db_session,
        account_id=other_acc.id,
        symbol="AAPL",
        pay_date=today - timedelta(days=10),
        dividend_per_share=99.0,
        shares_held=99.0,
    )
    db_session.commit()

    res = client.get("/api/v1/portfolio/income/calendar?mode=past&months=12")
    assert res.status_code == 200
    body = res.json()
    # Auth user has no dividends — must be empty even though the DB
    # contains rows owned by `other`.
    assert body["cells"] == []
    assert all(m["total"] == 0 for m in body["monthly_totals"])


def test_projection_uses_current_shares_and_quarterly_cadence(
    client, db_session, auth_user, broker_account, _wire_overrides
):
    today = datetime.now(timezone.utc)
    # Four trailing quarterly payments at $0.50/share.
    for q in range(4):
        _seed_dividend(
            db_session,
            account_id=broker_account.id,
            symbol="MSFT",
            pay_date=today - timedelta(days=30 + q * 90),
            dividend_per_share=0.50,
            shares_held=20.0,  # historical position size — shouldn't matter
        )
    # Current position: 100 shares (5x the historical shares_held).
    _seed_position(
        db_session,
        user_id=auth_user.id,
        account_id=broker_account.id,
        symbol="MSFT",
        quantity=100,
    )
    db_session.commit()

    res = client.get(
        "/api/v1/portfolio/income/calendar?mode=projection&months=12"
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "projection"
    assert all(m["projected"] is True for m in body["monthly_totals"])

    msft_cells = [
        c for c in body["cells"]
        if any(s["symbol"] == "MSFT" for s in c["by_symbol"])
    ]
    # Quarterly cadence over 12 months → ~4 projected payments.
    assert 3 <= len(msft_cells) <= 5
    for cell in msft_cells:
        # avg per share ($0.50) × current shares (100) = $50.
        assert cell["total"] == pytest.approx(50.0)


def test_projection_excludes_sold_out_symbols(
    client, db_session, auth_user, broker_account, _wire_overrides
):
    """Symbols with no current position must not appear in projections."""
    today = datetime.now(timezone.utc)
    for q in range(4):
        _seed_dividend(
            db_session,
            account_id=broker_account.id,
            symbol="OLD",
            pay_date=today - timedelta(days=30 + q * 90),
            dividend_per_share=1.00,
            shares_held=50.0,
        )
    db_session.commit()  # NB: no Position seeded for OLD

    res = client.get(
        "/api/v1/portfolio/income/calendar?mode=projection&months=12"
    )
    assert res.status_code == 200
    body = res.json()
    for cell in body["cells"]:
        for entry in cell["by_symbol"]:
            assert entry["symbol"] != "OLD"


def test_projection_excludes_single_payment_history(
    client, db_session, auth_user, broker_account, _wire_overrides
):
    """One historical payment is not enough to infer cadence."""
    today = datetime.now(timezone.utc)
    _seed_dividend(
        db_session,
        account_id=broker_account.id,
        symbol="ONE",
        pay_date=today - timedelta(days=30),
        dividend_per_share=0.50,
        shares_held=10.0,
    )
    _seed_position(
        db_session,
        user_id=auth_user.id,
        account_id=broker_account.id,
        symbol="ONE",
        quantity=100,
    )
    db_session.commit()

    res = client.get(
        "/api/v1/portfolio/income/calendar?mode=projection&months=12"
    )
    assert res.status_code == 200
    body = res.json()
    for cell in body["cells"]:
        for entry in cell["by_symbol"]:
            assert entry["symbol"] != "ONE"


def test_projection_isolates_other_users_positions(
    client, db_session, auth_user, broker_account, _wire_overrides
):
    """Even if another user holds shares in a symbol the auth user has
    historical dividends for, the projection must ONLY use the auth
    user's current shares."""
    today = datetime.now(timezone.utc)
    for q in range(4):
        _seed_dividend(
            db_session,
            account_id=broker_account.id,
            symbol="MSFT",
            pay_date=today - timedelta(days=30 + q * 90),
            dividend_per_share=0.50,
            shares_held=10.0,
        )
    other = User(
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        username=f"other_{uuid.uuid4().hex[:6]}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    other_acc = BrokerAccount(
        user_id=other.id,
        broker=BrokerType.IBKR,
        account_number=f"U{uuid.uuid4().hex[:6]}",
        account_type=AccountType.TAXABLE,
        is_enabled=True,
    )
    db_session.add(other_acc)
    db_session.commit()
    db_session.refresh(other_acc)
    # Other user holds MSFT shares but the auth user holds zero — so the
    # auth user's projection should not include MSFT.
    _seed_position(
        db_session,
        user_id=other.id,
        account_id=other_acc.id,
        symbol="MSFT",
        quantity=999,
    )
    db_session.commit()

    res = client.get(
        "/api/v1/portfolio/income/calendar?mode=projection&months=12"
    )
    assert res.status_code == 200
    body = res.json()
    for cell in body["cells"]:
        for entry in cell["by_symbol"]:
            assert entry["symbol"] != "MSFT"


def test_tax_data_unavailable_when_no_tax_withheld(
    client, db_session, _wire_overrides, broker_account
):
    today = datetime.now(timezone.utc)
    _seed_dividend(
        db_session,
        account_id=broker_account.id,
        symbol="AAPL",
        pay_date=today - timedelta(days=15),
        dividend_per_share=0.24,
        shares_held=100.0,
        tax_withheld=0.0,
    )
    db_session.commit()

    res = client.get("/api/v1/portfolio/income/calendar?mode=past&months=12")
    assert res.status_code == 200
    body = res.json()
    assert body["tax_data_available"] is False
