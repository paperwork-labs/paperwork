"""
Gate FMP 5-minute intraday backfill by MARKET_PROVIDER_POLICY.

FMP historical_chart (5m) requires a paid-style plan; free/starter waste quota on failures.
Resolution of unknown policy names matches ``Settings.provider_policy`` (falls back to paid).

medallion: silver
"""

from __future__ import annotations

import logging

from app.config import PROVIDER_POLICIES, settings

logger = logging.getLogger(__name__)

_INTRADAY_5M_ALLOWED = frozenset({"paid", "unlimited"})


def resolved_market_provider_tier() -> str:
    policy_name = str(settings.MARKET_PROVIDER_POLICY or "").strip().lower()
    if policy_name in PROVIDER_POLICIES:
        return policy_name
    return "paid"


def fmp_5m_intraday_backfill_blocked_tier() -> str | None:
    """Return tier name when 5m intraday backfill must be skipped; else None."""
    resolved = resolved_market_provider_tier()
    if resolved in _INTRADAY_5M_ALLOWED:
        return None
    return resolved


def log_skip_intraday_5m_backfill(blocked_tier: str) -> None:
    logger.info(
        "Intraday 5m backfill skipped: requires paid or unlimited "
        "MARKET_PROVIDER_POLICY (current: %s)",
        blocked_tier,
    )
