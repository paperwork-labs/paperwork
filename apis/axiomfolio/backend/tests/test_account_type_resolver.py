from __future__ import annotations

import pytest

from backend.models.broker_account import AccountType, BrokerType
from backend.services.portfolio.account_type_resolver import resolve_account_type


pytestmark = pytest.mark.no_db


def test_resolver_uses_ibkr_label_when_present():
    result = resolve_account_type(
        broker=BrokerType.IBKR,
        account_number="U19490886",
        ibkr_account_type_label="joint",
        oauth_account_type_label=None,
    )
    assert result.account_type == AccountType.TAXABLE
    assert result.warning is None


def test_resolver_emits_structured_warning_on_disagreement():
    result = resolve_account_type(
        broker=BrokerType.IBKR,
        account_number="U15891532",
        ibkr_account_type_label="ira",
        oauth_account_type_label="taxable",
    )
    assert result.account_type == AccountType.IRA
    assert result.warning is not None
    assert result.warning["code"] == "account_type_mismatch"
    assert result.warning["account_number"] == "U15891532"
