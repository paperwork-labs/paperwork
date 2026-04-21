"""Account-type-aware strategy profile (G24)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.models.broker_account import AccountType, BrokerAccount


@dataclass(frozen=True)
class AccountStrategyProfile:
    allow_wash_sale: bool
    tax_lot_method: str
    max_gain_holding_days_for_ltcg: Optional[int]
    margin_available: bool
    options_level: int
    short_allowed: bool


def get_strategy_profile(account: BrokerAccount) -> AccountStrategyProfile:
    """Pure function: derive strategy profile from account metadata only."""
    account_type = account.account_type
    margin_available = bool(getattr(account, "margin_enabled", False))
    options_level = 2 if bool(getattr(account, "options_enabled", False)) else 0

    if account_type == AccountType.TAXABLE:
        return AccountStrategyProfile(
            allow_wash_sale=False,
            tax_lot_method="tax_aware",
            max_gain_holding_days_for_ltcg=365,
            margin_available=margin_available,
            options_level=options_level,
            short_allowed=margin_available,
        )

    if account_type in (AccountType.IRA, AccountType.ROTH_IRA, AccountType.HSA):
        return AccountStrategyProfile(
            allow_wash_sale=True,
            tax_lot_method="average_cost",
            max_gain_holding_days_for_ltcg=None,
            margin_available=False,
            options_level=min(options_level, 1),
            short_allowed=False,
        )

    if account_type in (AccountType.TRUST, AccountType.BUSINESS):
        return AccountStrategyProfile(
            allow_wash_sale=False,
            tax_lot_method="fifo",
            max_gain_holding_days_for_ltcg=365,
            margin_available=margin_available,
            options_level=options_level,
            short_allowed=margin_available,
        )

    return AccountStrategyProfile(
        allow_wash_sale=False,
        tax_lot_method="fifo",
        max_gain_holding_days_for_ltcg=365,
        margin_available=margin_available,
        options_level=options_level,
        short_allowed=margin_available,
    )
