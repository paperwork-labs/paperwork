"""Firm-level risk caps — single source of truth for the upper bound on
every per-account tunable.

This module is **additive** to ``backend/config.py``. ``config.py`` is a
Danger Zone file; we read ``MAX_SINGLE_POSITION_PCT`` from it but never
edit it. The remaining caps (``max_stage_2c_pct``, ``max_options_pct``,
``max_daily_loss_pct``, ``hard_stop_pct``) are defined here as firm-level
constants because they are not user-tunable from the app config — they
are product-policy limits baked into the codebase.

Every value surfaced here is the **absolute upper bound** for the
corresponding per-account risk-profile field. ``min(firm, per_account)``
composition (see ``account_risk_profile.get_effective_limits``) means a
per-account value looser than the firm cap is never honoured — the firm
cap always wins.

If the firm cap for a field cannot be determined (e.g. a config value is
``None`` or missing), we raise ``FirmCapsUnavailable`` rather than
defaulting to zero or infinity — silent fallbacks mask broken systems
(see ``.cursor/rules/no-silent-fallback.mdc``).

medallion: gold
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.config import settings as app_settings

logger = logging.getLogger(__name__)


# Product-policy constants (not user-tunable from the app settings). These
# are intentionally conservative so the per-account layer can only tighten.
# Any future change requires a PR review under the same rules as any other
# risk-affecting code.
_FIRM_MAX_STAGE_2C_PCT = Decimal("1.0000")  # 100% — no additional firm limit beyond position cap
_FIRM_MAX_OPTIONS_PCT = Decimal("0.2000")  # 20% of account value may be in options
_FIRM_MAX_DAILY_LOSS_PCT = Decimal("0.0500")  # 5% daily loss kill switch per-account ceiling
_FIRM_HARD_STOP_PCT = Decimal("0.1000")  # 10% hard-stop distance ceiling


FIRM_CAP_FIELDS: tuple[str, ...] = (
    "max_position_pct",
    "max_stage_2c_pct",
    "max_options_pct",
    "max_daily_loss_pct",
    "hard_stop_pct",
)


class FirmCapsUnavailable(RuntimeError):
    """Raised when a firm-level cap cannot be resolved.

    Deliberately a hard failure — callers must not default to zero or
    infinity, because either value produces a dangerous effective limit.
    """


@dataclass(frozen=True)
class FirmCaps:
    """Immutable snapshot of the firm-level caps at call time.

    All fields are ``Decimal`` in the closed interval ``[0, 1]`` and
    represent fractions of account value (e.g. ``Decimal("0.15")`` for
    15%).
    """

    max_position_pct: Decimal
    max_stage_2c_pct: Decimal
    max_options_pct: Decimal
    max_daily_loss_pct: Decimal
    hard_stop_pct: Decimal

    def as_mapping(self) -> Mapping[str, Decimal]:
        return {
            "max_position_pct": self.max_position_pct,
            "max_stage_2c_pct": self.max_stage_2c_pct,
            "max_options_pct": self.max_options_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "hard_stop_pct": self.hard_stop_pct,
        }


def _to_decimal(value: object, field: str) -> Decimal:
    if value is None:
        raise FirmCapsUnavailable(
            f"firm cap for {field!r} is None; refusing to default to 0 or infinity"
        )
    try:
        dec = Decimal(str(value))
    except Exception as exc:
        raise FirmCapsUnavailable(
            f"firm cap for {field!r} is not a valid decimal: {value!r}"
        ) from exc
    if dec < 0 or dec > 1:
        raise FirmCapsUnavailable(f"firm cap for {field!r} out of range [0, 1]: {dec}")
    return dec


def get_firm_caps() -> FirmCaps:
    """Return the current firm-level caps.

    Reads ``MAX_SINGLE_POSITION_PCT`` from ``backend.config.settings``
    (read-only) and combines it with the module-level product-policy
    constants. Raises ``FirmCapsUnavailable`` if any value is missing
    or invalid — never silently substitutes a default.
    """

    max_position_raw = getattr(app_settings, "MAX_SINGLE_POSITION_PCT", None)
    max_position = _to_decimal(max_position_raw, "max_position_pct")

    return FirmCaps(
        max_position_pct=max_position,
        max_stage_2c_pct=_to_decimal(_FIRM_MAX_STAGE_2C_PCT, "max_stage_2c_pct"),
        max_options_pct=_to_decimal(_FIRM_MAX_OPTIONS_PCT, "max_options_pct"),
        max_daily_loss_pct=_to_decimal(_FIRM_MAX_DAILY_LOSS_PCT, "max_daily_loss_pct"),
        hard_stop_pct=_to_decimal(_FIRM_HARD_STOP_PCT, "hard_stop_pct"),
    )
