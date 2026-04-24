"""BrokerAccount.total_value / cash_balance updated when AccountBalance rows are written."""
from __future__ import annotations

import pytest
from decimal import Decimal

from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.models.user import User
from app.services.portfolio.schwab_sync_service import SchwabSyncService


class BalancesClient:
    def __init__(self, bal: dict) -> None:
        self._bal = bal

    async def get_account_balances(self, account_number: str) -> dict:
        return self._bal


def _user_and_account(session) -> BrokerAccount:
    u = session.query(User).filter(User.username == "bal_backfill_t").first()
    if not u:
        u = User(
            username="bal_backfill_t",
            email="bal_backfill_t@example.com",
            password_hash="x",
            is_active=True,
        )
        session.add(u)
        session.commit()
        session.refresh(u)
    ba = (
        session.query(BrokerAccount)
        .filter(
            BrokerAccount.user_id == u.id,
            BrokerAccount.account_number == "SCHWAB_BAL",
        )
        .first()
    )
    if not ba:
        ba = BrokerAccount(
            user_id=u.id,
            broker=BrokerType.SCHWAB,
            account_number="SCHWAB_BAL",
            account_name="Test",
            account_type=AccountType.TAXABLE,
            currency="USD",
        )
        session.add(ba)
        session.commit()
        session.refresh(ba)
    return ba


@pytest.mark.asyncio
async def test_schwab_sync_balances_sets_broker_account_totals(db_session) -> None:
    acct = _user_and_account(db_session)
    acct.total_value = None
    acct.cash_balance = None
    db_session.add(acct)
    db_session.commit()

    bal = {
        "cash_balance": 1234.56,
        "net_liquidating_value": 98765.43,
    }
    svc = SchwabSyncService(client=BalancesClient(bal))
    await svc._sync_balances(acct, db_session)
    db_session.flush()
    assert acct.total_value == Decimal("98765.43")
    assert acct.cash_balance == Decimal("1234.56")
    from app.models.account_balance import AccountBalance

    ab = (
        db_session.query(AccountBalance)
        .filter(AccountBalance.broker_account_id == acct.id)
        .order_by(AccountBalance.id.desc())
        .first()
    )
    assert ab is not None
    assert ab.cash_balance == 1234.56
    assert ab.net_liquidation == 98765.43
