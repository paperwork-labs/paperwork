"""Per-account risk profile service.

This layer sits **on top of** the firm-level caps enforced by
``backend/services/execution/risk_gate.py`` — it can only be more
conservative, never looser. The ``RiskGate`` itself is untouched by this
PR; this module provides configuration and advisory plumbing so future
callers (and the UI) can read the tighter-of-two limits.

Multi-tenancy: every public function accepts ``user_id`` and filters
account lookups by it. Cross-tenant access attempts raise
``AccountNotFoundError`` rather than leaking existence information.

medallion: gold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Optional

from sqlalchemy.orm import Session

from backend.models.account_risk_profile import BrokerAccountRiskProfile
from backend.models.broker_account import BrokerAccount
from backend.services.risk.firm_caps import (
    FIRM_CAP_FIELDS,
    FirmCaps,
    FirmCapsUnavailable,
    get_firm_caps,
)

logger = logging.getLogger(__name__)


class AccountNotFoundError(LookupError):
    """Raised when the target account does not belong to the calling user."""


@dataclass(frozen=True)
class EffectiveLimits:
    """Effective per-account caps after merging firm caps with overrides."""

    account_id: int
    firm: Mapping[str, Decimal]
    per_account: Mapping[str, Optional[Decimal]]
    effective: Mapping[str, Decimal]

    def as_dict(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "firm": {k: str(v) for k, v in self.firm.items()},
            "per_account": {
                k: (str(v) if v is not None else None)
                for k, v in self.per_account.items()
            },
            "effective": {k: str(v) for k, v in self.effective.items()},
        }


def _load_account(db: Session, user_id: int, account_id: int) -> BrokerAccount:
    account = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.id == account_id, BrokerAccount.user_id == user_id)
        .one_or_none()
    )
    if account is None:
        raise AccountNotFoundError(
            f"account {account_id} not found for user {user_id}"
        )
    return account


def _load_profile(
    db: Session, account_id: int
) -> Optional[BrokerAccountRiskProfile]:
    return (
        db.query(BrokerAccountRiskProfile)
        .filter(BrokerAccountRiskProfile.account_id == account_id)
        .one_or_none()
    )


def _to_decimal_opt(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _merge_min(
    firm_caps: FirmCaps,
    profile: Optional[BrokerAccountRiskProfile],
    *,
    account_id: int,
) -> tuple[dict[str, Optional[Decimal]], dict[str, Decimal]]:
    firm_map = firm_caps.as_mapping()
    per_account: dict[str, Optional[Decimal]] = {}
    effective: dict[str, Decimal] = {}

    for field in FIRM_CAP_FIELDS:
        firm_value = firm_map[field]
        raw_override = getattr(profile, field, None) if profile is not None else None
        override = _to_decimal_opt(raw_override)
        per_account[field] = override

        if override is None:
            effective[field] = firm_value
            continue

        if override > firm_value:
            # Firm always wins — log loudly so this never silently bends.
            logger.warning(
                "account_risk_profile: per-account %s=%s exceeds firm cap %s "
                "for account_id=%s; using firm cap. Loosening is not permitted.",
                field,
                override,
                firm_value,
                account_id,
            )
            effective[field] = firm_value
        else:
            effective[field] = override

    return per_account, effective


def get_effective_limits(
    db: Session, user_id: int, account_id: int
) -> EffectiveLimits:
    """Return firm, per-account, and effective limits for an account.

    Effective limit per field = ``min(firm_cap, per_account_cap)``. A
    per-account value that exceeds the firm cap is logged as a WARNING
    and the firm cap is used — firm caps are never loosened.

    Raises:
        AccountNotFoundError: account does not belong to ``user_id``.
        FirmCapsUnavailable: firm caps could not be resolved.
    """

    _load_account(db, user_id, account_id)
    firm_caps = get_firm_caps()
    profile = _load_profile(db, account_id)
    per_account, effective = _merge_min(firm_caps, profile, account_id=account_id)
    return EffectiveLimits(
        account_id=account_id,
        firm=firm_caps.as_mapping(),
        per_account=per_account,
        effective=effective,
    )


def _validate_new_limits(
    new_limits: Mapping[str, object], firm_caps: FirmCaps
) -> dict[str, Optional[Decimal]]:
    firm_map = firm_caps.as_mapping()
    cleaned: dict[str, Optional[Decimal]] = {}

    unknown = set(new_limits) - set(FIRM_CAP_FIELDS)
    if unknown:
        raise ValueError(
            f"unknown risk-profile fields: {sorted(unknown)}. "
            f"Allowed: {list(FIRM_CAP_FIELDS)}"
        )

    for field in FIRM_CAP_FIELDS:
        if field not in new_limits:
            cleaned[field] = None
            continue
        raw = new_limits[field]
        if raw is None:
            cleaned[field] = None
            continue
        try:
            value = Decimal(str(raw))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                f"{field!r} must be a decimal fraction in [0, 1], got {raw!r}"
            ) from exc
        if value < 0:
            raise ValueError(
                f"{field!r} cannot be negative (got {value}); use 0 for 'block entirely'"
            )
        if value > 1:
            raise ValueError(
                f"{field!r} must be a fraction <= 1.0 (got {value}); "
                "e.g. 0.05 for 5%"
            )
        firm_value = firm_map[field]
        if value > firm_value:
            raise ValueError(
                f"{field!r} override {value} is looser than the firm cap "
                f"{firm_value}. Per-account limits can only tighten, never "
                f"loosen. Use <= {firm_value} or omit to inherit."
            )
        cleaned[field] = value

    return cleaned


def apply_override(
    db: Session,
    user_id: int,
    account_id: int,
    new_limits: Mapping[str, object],
) -> EffectiveLimits:
    """Validate and persist a per-account risk-profile override.

    ``new_limits`` is a partial mapping; missing keys are treated as
    ``None`` (inherit firm cap). Any value strictly greater than the
    corresponding firm cap raises ``ValueError`` — this is the primary
    guard preventing the per-account layer from loosening the firm layer.

    Returns the recomputed effective limits.

    Raises:
        AccountNotFoundError: account does not belong to ``user_id``.
        ValueError: any requested override exceeds the firm cap or is
            otherwise invalid.
        FirmCapsUnavailable: firm caps could not be resolved.
    """

    _load_account(db, user_id, account_id)
    firm_caps = get_firm_caps()
    cleaned = _validate_new_limits(new_limits, firm_caps)

    profile = _load_profile(db, account_id)
    if profile is None:
        profile = BrokerAccountRiskProfile(account_id=account_id)
        db.add(profile)

    for field in FIRM_CAP_FIELDS:
        setattr(profile, field, cleaned[field])

    db.flush()

    per_account, effective = _merge_min(firm_caps, profile, account_id=account_id)
    return EffectiveLimits(
        account_id=account_id,
        firm=firm_caps.as_mapping(),
        per_account=per_account,
        effective=effective,
    )


__all__ = [
    "AccountNotFoundError",
    "EffectiveLimits",
    "FirmCapsUnavailable",
    "apply_override",
    "get_effective_limits",
]
