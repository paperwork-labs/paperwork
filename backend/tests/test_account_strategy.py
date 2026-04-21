from __future__ import annotations

import pytest

from backend.models.broker_account import AccountType, BrokerAccount
from backend.services.strategy.account_strategy import get_strategy_profile


pytestmark = pytest.mark.no_db


def _account(account_type: AccountType, *, margin: bool = False, options: bool = False) -> BrokerAccount:
    account = BrokerAccount(
        user_id=1,
        broker="ibkr",  # test helper only
        account_number="U123",
        account_type=account_type,
    )
    account.margin_enabled = margin
    account.options_enabled = options
    return account


def test_taxable_profile_disallows_wash_sale_and_allows_short_on_margin():
    profile = get_strategy_profile(_account(AccountType.TAXABLE, margin=True, options=True))
    assert profile.allow_wash_sale is False
    assert profile.tax_lot_method == "tax_aware"
    assert profile.short_allowed is True
    assert profile.options_level == 2


def test_ira_profile_is_tax_advantaged_and_no_short():
    profile = get_strategy_profile(_account(AccountType.IRA, margin=True, options=True))
    assert profile.allow_wash_sale is True
    assert profile.max_gain_holding_days_for_ltcg is None
    assert profile.margin_available is False
    assert profile.short_allowed is False
