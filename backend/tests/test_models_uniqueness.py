import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect

from backend.models import BrokerAccount, User
from backend.models.broker_account import BrokerType, AccountType, AccountStatus
from backend.models.trade import Trade
from backend.models.transaction import Transaction, TransactionType
from backend.models.options import Option
from datetime import datetime, date


@pytest.fixture
def db(db_session):
    yield db_session


@pytest.fixture(autouse=True)
def _require_schema(db_session):
    inspector = inspect(db_session.bind)
    if not inspector.has_table("users") or not inspector.has_table("broker_accounts"):
        pytest.skip("Test DB not migrated; required tables missing")


@pytest.fixture
def broker_account(db):
    # ensure user exists to satisfy FK
    user = db.query(User).filter_by(id=1).first()
    if not user:
        user = User(id=1, username="testuser", email="test@example.com", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

    ba = BrokerAccount(
        user_id=1,
        broker=BrokerType.IBKR,
        account_number="TEST_ACC",
        account_name="Test Account",
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        is_enabled=True,
        currency="USD",
    )
    db.add(ba)
    db.commit()
    db.refresh(ba)
    return ba


def test_trade_unique_account_execution(db, broker_account):
    t1 = Trade(
        account_id=broker_account.id,
        symbol="AAPL",
        side="BUY",
        quantity=1,
        price=100.0,
        execution_id="exec-1",
    )
    db.add(t1)
    db.commit()

    t2 = Trade(
        account_id=broker_account.id,
        symbol="AAPL",
        side="BUY",
        quantity=1,
        price=100.0,
        execution_id="exec-1",
    )
    nested = db.begin_nested()
    db.add(t2)
    with pytest.raises(IntegrityError):
        db.flush()
    nested.rollback()


def test_trade_same_order_id_different_execution_allowed(db, broker_account):
    """Multiple fills under one order_id are allowed (only execution_id is unique)."""
    t1 = Trade(
        account_id=broker_account.id,
        symbol="MSFT",
        side="BUY",
        quantity=1,
        price=100.0,
        order_id="ord-1",
        execution_id="exec-1",
    )
    db.add(t1)
    db.commit()

    t2 = Trade(
        account_id=broker_account.id,
        symbol="MSFT",
        side="BUY",
        quantity=1,
        price=100.0,
        order_id="ord-1",
        execution_id="exec-2",
    )
    db.add(t2)
    db.commit()
    assert db.query(Trade).filter_by(account_id=broker_account.id).count() == 2


def test_transaction_unique_external_and_execution(db, broker_account):
    tx1 = Transaction(
        account_id=broker_account.id,
        symbol="AAPL",
        external_id="ext-1",
        execution_id="",
        transaction_type=TransactionType.BUY,
        amount=1.0,
        net_amount=1.0,
        currency="USD",
        transaction_date=datetime.utcnow(),
    )
    db.add(tx1)
    db.commit()

    tx2 = Transaction(
        account_id=broker_account.id,
        symbol="AAPL",
        external_id="ext-1",
        execution_id="",
        transaction_type=TransactionType.BUY,
        amount=1.0,
        net_amount=1.0,
        currency="USD",
        transaction_date=datetime.utcnow(),
    )
    nested = db.begin_nested()
    db.add(tx2)
    with pytest.raises(IntegrityError):
        db.flush()
    nested.rollback()

    tx3 = Transaction(
        account_id=broker_account.id,
        symbol="AAPL",
        external_id="ext-2",
        execution_id="exec-1",
        transaction_type=TransactionType.BUY,
        amount=1.0,
        net_amount=1.0,
        currency="USD",
        transaction_date=datetime.utcnow(),
    )
    db.add(tx3)
    db.commit()

    tx4 = Transaction(
        account_id=broker_account.id,
        symbol="AAPL",
        external_id="ext-3",
        execution_id="exec-1",
        transaction_type=TransactionType.BUY,
        amount=1.0,
        net_amount=1.0,
        currency="USD",
        transaction_date=datetime.utcnow(),
    )
    nested = db.begin_nested()
    db.add(tx4)
    with pytest.raises(IntegrityError):
        db.flush()
    nested.rollback()


def test_option_position_unique_contract(db, broker_account):
    op1 = Option(
        user_id=1,
        account_id=broker_account.id,
        symbol="AAPL 2025-01-17 C 200",
        underlying_symbol="AAPL",
        strike_price=200.0,
        expiry_date=date(2025, 1, 17),
        option_type="CALL",
        open_quantity=1,
        multiplier=100,
    )
    db.add(op1)
    db.commit()

    op2 = Option(
        user_id=1,
        account_id=broker_account.id,
        symbol="AAPL 2025-01-17 C 200",
        underlying_symbol="AAPL",
        strike_price=200.0,
        expiry_date=date(2025, 1, 17),
        option_type="CALL",
        open_quantity=1,
        multiplier=100,
    )
    nested = db.begin_nested()
    db.add(op2)
    with pytest.raises(IntegrityError):
        db.flush()
    nested.rollback()
