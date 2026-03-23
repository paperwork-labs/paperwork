"""D10: Request idempotency via Redis. If Redis fails, skip check (accept rare duplicates)."""

import logging

logger = logging.getLogger(__name__)

TTL_SECONDS = 300


async def check_and_set(redis_client, request_id: str) -> bool:
    """Returns True if this request_id was already processed. Sets it if not."""
    if not redis_client or not request_id:
        return False
    try:
        key = f"brain:idempotent:{request_id}"
        existed = await redis_client.set(key, "1", nx=True, ex=TTL_SECONDS)
        return existed is None
    except Exception:
        logger.warning("Redis idempotency check failed, proceeding", exc_info=True)
        return False
