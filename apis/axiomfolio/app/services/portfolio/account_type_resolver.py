"""Resolve broker account types from provider metadata and XML signals.

medallion: ops
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.broker_account import AccountType, BrokerType


@dataclass(frozen=True)
class AccountTypeResolution:
    account_type: AccountType
    warning: Optional[dict]


def _map_label(raw: Optional[str]) -> Optional[AccountType]:
    if not raw:
        return None
    label = str(raw).strip().lower()
    if label in {"taxable", "brokerage", "individual", "joint"}:
        return AccountType.TAXABLE
    if label in {"ira", "traditional_ira", "traditional ira"}:
        return AccountType.IRA
    if label in {"roth_ira", "roth ira"}:
        return AccountType.ROTH_IRA
    if label in {"hsa"}:
        return AccountType.HSA
    if label in {"trust"}:
        return AccountType.TRUST
    if label in {"business", "corporate"}:
        return AccountType.BUSINESS
    return None


def resolve_account_type(
    *,
    broker: BrokerType,
    account_number: str,
    ibkr_account_type_label: Optional[str],
    oauth_account_type_label: Optional[str],
    fallback: AccountType = AccountType.TAXABLE,
) -> AccountTypeResolution:
    """Reconcile provider-level account-type hints into one enum value."""
    ibkr_type = _map_label(ibkr_account_type_label)
    oauth_type = _map_label(oauth_account_type_label)

    resolved = ibkr_type or oauth_type or fallback
    warning = None
    if ibkr_type and oauth_type and ibkr_type != oauth_type:
        warning = {
            "code": "account_type_mismatch",
            "broker": broker.value,
            "account_number": account_number,
            "ibkr_account_type": ibkr_type.value,
            "oauth_account_type": oauth_type.value,
            "resolved_account_type": resolved.value,
        }

    return AccountTypeResolution(account_type=resolved, warning=warning)
