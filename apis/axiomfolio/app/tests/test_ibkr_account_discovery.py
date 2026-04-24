from __future__ import annotations

import pytest

from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.models.user import User
from app.services.portfolio.ibkr.pipeline import IBKRSyncService

def _make_user(db_session, suffix: str) -> User:
    user = User(
        email=f"discover_{suffix}@example.com",
        username=f"discover_{suffix}",
        password_hash="x",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_account_auto_discovery_is_scoped_to_seed_user(db_session):
    user_a = _make_user(db_session, "a")
    user_b = _make_user(db_session, "b")
    seed = BrokerAccount(
        user_id=user_a.id,
        broker=BrokerType.IBKR,
        account_number="USEEDA",
        account_type=AccountType.TAXABLE,
    )
    db_session.add(seed)
    db_session.commit()
    db_session.refresh(seed)

    # Another tenant already has a similarly shaped IBKR account.
    other = BrokerAccount(
        user_id=user_b.id,
        broker=BrokerType.IBKR,
        account_number="U15891532",
        account_type=AccountType.IRA,
    )
    db_session.add(other)
    db_session.commit()

    report_xml = """
    <FlexQueryResponse>
      <FlexStatements>
        <FlexStatement accountId="U19490886">
          <AccountInformation>
            <AccountInformation accountType="joint" />
          </AccountInformation>
        </FlexStatement>
        <FlexStatement accountId="U15891532">
          <AccountInformation>
            <AccountInformation accountType="ira" />
          </AccountInformation>
        </FlexStatement>
      </FlexStatements>
    </FlexQueryResponse>
    """
    result = IBKRSyncService._discover_accounts_from_report(db_session, seed, report_xml)
    db_session.commit()

    assert "U19490886" in result["created"]
    created_for_a = (
        db_session.query(BrokerAccount)
        .filter(BrokerAccount.user_id == user_a.id, BrokerAccount.account_number == "U19490886")
        .first()
    )
    assert created_for_a is not None
    assert created_for_a.auto_discovered is True
    assert created_for_a.api_credentials_stored is False
    assert created_for_a.is_enabled is False

    # Existing account for user_b is untouched (no cross-tenant mutation).
    user_b_row = (
        db_session.query(BrokerAccount)
        .filter(BrokerAccount.user_id == user_b.id, BrokerAccount.account_number == "U15891532")
        .first()
    )
    assert user_b_row is not None
    assert user_b_row.account_type == AccountType.IRA
