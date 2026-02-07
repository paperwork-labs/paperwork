#!/usr/bin/env python3
"""
AxiomFolio Clean Model Tests (Broker-Agnostic)
===============================================
Minimal, focused checks to fail fast if someone re-introduces legacy
`accounts` references or enum duplications.

Test Areas:
1. Import integrity for core models
2. All account/broker foreign keys → broker_accounts.id
3. Enum single-source enforcement
4. Basic persistence smoke test
"""

import inspect
import importlib
import pytest
from sqlalchemy import ForeignKey
from sqlalchemy import inspect as sa_inspect

from backend.models import (
    User,
    BrokerAccount,
    Instrument,
    Position,
    TaxLot,
    Trade,
    Transaction,
    Dividend,
    AccountBalance,
    MarginInterest,
    Transfer,
    PortfolioSnapshot,
    Category,
    PositionCategory,
)
from backend.models.broker_account import AccountType, BrokerType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _require_schema(db_session):
    inspector = sa_inspect(db_session.bind)
    if not inspector.has_table("users") or not inspector.has_table("broker_accounts"):
        pytest.skip("Test DB not migrated; required tables missing")

# ---------------------------------------------------------------------------
# 1. Import integrity
# ---------------------------------------------------------------------------


def test_model_imports():
    models = [
        User,
        BrokerAccount,
        Instrument,
        Position,
        TaxLot,
        Trade,
        Transaction,
        Dividend,
        AccountBalance,
        MarginInterest,
        Transfer,
        PortfolioSnapshot,
        Category,
        PositionCategory,
    ]
    for model in models:
        assert inspect.isclass(model)


# ---------------------------------------------------------------------------
# 2. Broker-agnostic foreign keys
# ---------------------------------------------------------------------------

FK_MODELS = [
    (Position, "account_id"),
    (TaxLot, "account_id"),
    (Trade, "account_id"),
    (Transaction, "account_id"),
    (Dividend, "account_id"),
    (AccountBalance, "broker_account_id"),
    (MarginInterest, "broker_account_id"),
    (Transfer, "broker_account_id"),
    (PortfolioSnapshot, "account_id"),
]


def _target(col: ForeignKey) -> str:
    return str(list(col.foreign_keys)[0].target_fullname)


def test_foreign_keys_use_broker_accounts():
    for model, field in FK_MODELS:
        column = getattr(model.__table__.c, field)
        assert column.foreign_keys, f"{model.__name__}.{field} missing FK"
        assert _target(column) == "broker_accounts.id"


# ---------------------------------------------------------------------------
# 3. Enum single-source enforcement
# ---------------------------------------------------------------------------


def test_enum_single_source():
    # Attempting to import enums from portfolio must fail
    portfolio = importlib.import_module("backend.models.portfolio")
    for attr in ("AccountType", "BrokerType"):
        assert not hasattr(portfolio, attr), f"portfolio.py exposes legacy {attr}"


# ---------------------------------------------------------------------------
# 4. Smoke persistence
# ---------------------------------------------------------------------------


def test_basic_persistence(db_session):
    import uuid

    user = User(
        username=f"tester_{uuid.uuid4().hex[:6]}",
        email=f"t_{uuid.uuid4().hex[:6]}@example.com",
    )
    ba = BrokerAccount(
        user=user,
        broker=BrokerType.IBKR,
        account_number="TEST123",
        account_type=AccountType.TAXABLE,
    )
    instr = Instrument(symbol="SPY", instrument_type="STOCK")
    db_session.add_all([user, ba, instr])
    db_session.flush()

    from backend.models.position import PositionType

    pos = Position(
        user=user,
        account_id=ba.id,
        instrument_id=instr.id,
        symbol="SPY",
        quantity=1,
        average_cost=400,
        total_cost_basis=400,
        position_type=PositionType.LONG,
    )
    db_session.add(pos)
    db_session.commit()

    assert db_session.query(Position).count() == 1
