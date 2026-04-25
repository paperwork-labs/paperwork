"""Daily cost ceiling enforcement per (organization, persona).

Why this exists
---------------
Persona specs declare `daily_cost_ceiling_usd`. Before Phase D H3 that
field was decorative — we want enforcement, not documentation.

Contract
--------
- `check_ceiling(org, persona, ceiling_usd)` raises `CostCeilingExceeded`
  if today's spend has already crossed the cap. Call this BEFORE the
  LLM request to fail fast.
- `record_spend(org, persona, amount_usd)` atomically adds to the
  counter after a successful request.
- Counters expire 26 hours after first write — one hour of headroom
  around the PT midnight rollover so there's no user-visible hiccup.

Redis unavailable ⇒ we fail open (log a warning, allow the request).
The alternative is taking Brain down when Redis blips; that's a worse
failure mode for an already-compliance-flagged persona whose user is
waiting on a response. We log loudly so an operator notices.

medallion: ops
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

TTL_SECONDS = 26 * 60 * 60  # 24h + 2h buffer around PT midnight


class CostCeilingExceeded(Exception):
    """Persona hit its daily_cost_ceiling_usd for this organization."""

    def __init__(self, *, persona: str, spent_usd: float, ceiling_usd: float):
        self.persona = persona
        self.spent_usd = spent_usd
        self.ceiling_usd = ceiling_usd
        super().__init__(
            f"{persona} exceeded daily ceiling: "
            f"${spent_usd:.2f} of ${ceiling_usd:.2f}"
        )


def _key(organization_id: str, persona: str) -> str:
    return f"cost:daily:{organization_id}:{persona}"


async def check_ceiling(
    redis_client: Any | None,
    *,
    organization_id: str,
    persona: str,
    ceiling_usd: float | None,
) -> float:
    """Return current spend. Raises CostCeilingExceeded if over the cap.

    If `ceiling_usd` is None, no check is performed; returns 0.0.
    """
    if ceiling_usd is None:
        return 0.0
    if redis_client is None:
        logger.warning(
            "cost_tracker: redis unavailable, failing open for persona=%s org=%s",
            persona, organization_id,
        )
        return 0.0
    try:
        raw = await redis_client.get(_key(organization_id, persona))
    except Exception:
        logger.warning(
            "cost_tracker: redis GET failed, failing open for persona=%s org=%s",
            persona, organization_id,
            exc_info=True,
        )
        return 0.0

    spent = float(raw) if raw else 0.0
    if spent >= ceiling_usd:
        raise CostCeilingExceeded(
            persona=persona,
            spent_usd=spent,
            ceiling_usd=ceiling_usd,
        )
    return spent


async def record_spend(
    redis_client: Any | None,
    *,
    organization_id: str,
    persona: str,
    amount_usd: float,
) -> float:
    """Atomically add `amount_usd` to today's counter. Returns new total.

    `amount_usd <= 0` is a no-op (we don't bother writing). Missing
    Redis is logged and skipped — consistent with check_ceiling's
    fail-open stance.
    """
    if amount_usd <= 0:
        return 0.0
    if redis_client is None:
        logger.info(
            "cost_tracker: redis unavailable, skipping spend record "
            "persona=%s org=%s amount=$%.4f",
            persona, organization_id, amount_usd,
        )
        return 0.0
    key = _key(organization_id, persona)
    try:
        # INCRBYFLOAT is atomic. Ensure TTL is set on first write only.
        new_total = await redis_client.incrbyfloat(key, amount_usd)
        # Set TTL on the key if not already present. Upstash/Redis EXPIRE
        # with NX flag (Redis 7+) is the cleanest path; fall back to
        # unconditional EXPIRE if the client doesn't support NX.
        try:
            await redis_client.expire(key, TTL_SECONDS, nx=True)
        except TypeError:
            await redis_client.expire(key, TTL_SECONDS)
        return float(new_total)
    except Exception:
        logger.warning(
            "cost_tracker: redis INCRBYFLOAT failed persona=%s org=%s",
            persona, organization_id,
            exc_info=True,
        )
        return 0.0
