"""Per-persona rate limiting.

SlowAPI gives us a global default (100/minute by remote address) in
``app/rate_limit.py``. Track I adds a *dynamic* per-persona cap on top:
some personas (CFO, strategy) warrant stricter limits because each call
is expensive and agentic; others (engineering, EA) can take more
traffic. The spec declares ``requests_per_minute``; this module enforces
it at the ``/brain/process`` layer before we touch an LLM.

We key on ``(organization_id, persona)``. This means a shared bot token
across channels still gets protected per-persona; an org hitting the CPA
persona 100x/minute can be throttled without impacting its QA calls.

Redis unavailable ⇒ fail open (log, allow). Same stance as cost_tracker:
prefer degraded ops to Brain-wide outage on a Redis blip.

medallion: ops
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60


class PersonaRateLimitExceeded(Exception):
    """Persona hit its per-minute rate limit for this organization."""

    def __init__(
        self,
        *,
        persona: str,
        limit: int,
        current: int,
        retry_after: int,
    ):
        self.persona = persona
        self.limit = limit
        self.current = current
        self.retry_after = retry_after
        super().__init__(
            f"{persona} exceeded {limit}/min (current={current}); retry in {retry_after}s"
        )


def _key(organization_id: str, persona: str, bucket: int) -> str:
    return f"ratelimit:persona:{organization_id}:{persona}:{bucket}"


async def check_and_increment(
    redis_client: Any | None,
    *,
    organization_id: str,
    persona: str,
    limit_per_minute: int | None,
) -> int:
    """Increment the per-minute counter. Raises if over limit.

    Returns the new count for observability. A None limit is a no-op
    that returns 0.
    """
    if limit_per_minute is None or limit_per_minute <= 0:
        return 0
    if redis_client is None:
        logger.warning(
            "persona_rate_limit: redis unavailable, failing open persona=%s org=%s",
            persona,
            organization_id,
        )
        return 0

    # Fixed-window counter. Use the current minute as the bucket so the
    # counter rolls over naturally — no need to rely on sliding-window
    # math. The bucket gets a 2-minute TTL so stale buckets go away
    # without us having to GC manually.
    now = int(time.time())
    bucket = now // WINDOW_SECONDS
    key = _key(organization_id, persona, bucket)

    try:
        count = await redis_client.incr(key)
        try:
            await redis_client.expire(key, WINDOW_SECONDS * 2, nx=True)
        except TypeError:
            await redis_client.expire(key, WINDOW_SECONDS * 2)
    except Exception:
        logger.warning(
            "persona_rate_limit: redis INCR failed persona=%s org=%s",
            persona,
            organization_id,
            exc_info=True,
        )
        return 0

    count = int(count)
    if count > limit_per_minute:
        retry_after = WINDOW_SECONDS - (now % WINDOW_SECONDS)
        raise PersonaRateLimitExceeded(
            persona=persona,
            limit=limit_per_minute,
            current=count,
            retry_after=max(1, retry_after),
        )
    return count
