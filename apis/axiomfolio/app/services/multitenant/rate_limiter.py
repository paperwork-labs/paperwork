"""Per-tenant token-bucket rate limiter (Redis-backed, fail-CLOSED).

Iron law: if Redis is unreachable we MUST refuse the request. Letting
traffic through silently when our defense layer is down would mask the
outage and could be exploited as a denial-of-wallet (e.g. unbounded LLM
calls). The middleware that calls us surfaces a 503 rather than 429 in
that case.

The bucket is computed from ``TenantRateLimit`` rows with a
hard-coded fallback so the limiter still works on a fresh DB. Lookup
order:

1. ``(user_id, exact endpoint pattern)`` — tenant override
2. ``(user_id, '*')`` — tenant-wide override
3. ``(NULL, exact endpoint pattern)`` — global default for endpoint
4. ``(NULL, '*')`` — global default
5. Hard-coded fallback (``DEFAULT_BUCKET``)

medallion: ops
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass
from enum import Enum

import redis as redis_sync
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.multitenant import (
    RateLimitViolation,
    TenantRateLimit,
)
from app.services.multitenant.redis_namespace import tenant_key

logger = logging.getLogger(__name__)


# Token-bucket implemented client-side with WATCH/MULTI/EXEC for
# atomicity. We deliberately avoid Lua so the limiter works against any
# Redis-API-compatible backend (real Redis, Elasticache, fakeredis in
# tests, RESP3 proxies).
_WATCH_RETRY_LIMIT = 4
_KEY_TTL_MS = 120_000


# Hard-coded fallback so a fresh DB without TenantRateLimit rows is
# still defended.
DEFAULT_BUCKET_PER_MINUTE = 120
DEFAULT_BURST_CAPACITY = 60


class RateLimitDecision(str, Enum):
    ALLOWED = "allowed"
    LIMITED = "limited"
    FAILED_CLOSED = "failed_closed"


@dataclass
class RateLimitResult:
    decision: RateLimitDecision
    bucket_per_minute: int
    burst_capacity: int
    tokens_remaining: int
    retry_after_ms: int

    @property
    def allowed(self) -> bool:
        return self.decision == RateLimitDecision.ALLOWED

    @property
    def http_status(self) -> int:
        if self.decision == RateLimitDecision.ALLOWED:
            return 200
        if self.decision == RateLimitDecision.LIMITED:
            return 429
        return 503  # FAILED_CLOSED


class TenantRateLimiter:
    """Per-(user, endpoint) Redis token-bucket limiter."""

    def __init__(
        self,
        redis_client: redis_sync.Redis | None = None,
        redis_url: str | None = None,
    ) -> None:
        self._redis = redis_client
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379/0")

    # -- redis plumbing -------------------------------------------------

    def _get_redis(self) -> redis_sync.Redis:
        if self._redis is not None:
            return self._redis
        # Lazy connect; callers may want to inject a fake in tests.
        self._redis = redis_sync.from_url(
            self._redis_url, socket_timeout=1.5, socket_connect_timeout=1.5
        )
        return self._redis

    def _consume(
        self,
        client: redis_sync.Redis,
        key: str,
        capacity: int,
        refill_per_sec: float,
        now_ms: int,
        cost: int,
    ) -> tuple[int, int, int]:
        """Atomically refill + consume from a token-bucket key.

        Returns ``(allowed, tokens_remaining, retry_after_ms)``. Uses
        WATCH/MULTI/EXEC so it's safe against concurrent callers without
        requiring server-side Lua.
        """
        attempts = 0
        while True:
            attempts += 1
            with client.pipeline() as pipe:
                try:
                    pipe.watch(key)
                    raw = pipe.hmget(key, "tokens", "ts")
                    raw_tokens, raw_ts = raw[0], raw[1]
                    if raw_tokens is None:
                        tokens = float(capacity)
                        ts = now_ms
                    else:
                        tokens = float(raw_tokens)
                        ts = int(raw_ts) if raw_ts is not None else now_ms

                    elapsed_ms = max(0, now_ms - ts)
                    tokens = min(float(capacity), tokens + (elapsed_ms / 1000.0) * refill_per_sec)

                    if tokens >= cost:
                        tokens -= cost
                        allowed = 1
                        retry_after_ms = 0
                    else:
                        allowed = 0
                        deficit = cost - tokens
                        retry_after_ms = (
                            int(math.ceil((deficit / refill_per_sec) * 1000.0))
                            if refill_per_sec > 0
                            else 60_000
                        )

                    pipe.multi()
                    pipe.hset(key, mapping={"tokens": tokens, "ts": now_ms})
                    pipe.pexpire(key, _KEY_TTL_MS)
                    pipe.execute()
                    return allowed, int(tokens), retry_after_ms
                except redis_sync.exceptions.WatchError:
                    if attempts >= _WATCH_RETRY_LIMIT:
                        # Treat persistent contention as a degraded state.
                        # Fail CLOSED rather than letting traffic through.
                        raise redis_sync.exceptions.RedisError(
                            "rate_limiter watch contention exceeded retry limit"
                        )
                    continue

    # -- public API -----------------------------------------------------

    def resolve_bucket(self, db: Session, user_id: int | None, endpoint: str) -> tuple[int, int]:
        """Return ``(per_minute, burst_capacity)`` for a (user, endpoint) pair."""
        # Order of preference (most specific wins):
        candidates: list[tuple[int | None, str]] = []
        if user_id is not None:
            candidates.append((user_id, endpoint))
            candidates.append((user_id, "*"))
        candidates.append((None, endpoint))
        candidates.append((None, "*"))

        for uid, pattern in candidates:
            stmt = select(TenantRateLimit).where(TenantRateLimit.endpoint_pattern == pattern)
            if uid is None:
                stmt = stmt.where(TenantRateLimit.user_id.is_(None))
            else:
                stmt = stmt.where(TenantRateLimit.user_id == uid)
            row = db.execute(stmt).scalar_one_or_none()
            if row is not None:
                return int(row.bucket_size_per_minute), int(row.burst_capacity)

        return DEFAULT_BUCKET_PER_MINUTE, DEFAULT_BURST_CAPACITY

    def check(
        self,
        db: Session,
        user_id: int | None,
        endpoint: str,
        cost: int = 1,
    ) -> RateLimitResult:
        """Consume ``cost`` tokens. Fails CLOSED if Redis is unreachable.

        ``user_id`` may be None for unauthenticated endpoints; those
        are bucketed under ``tenant:global:ratelimit:{endpoint}`` and
        share a single bucket across the world. That's deliberate:
        anonymous endpoints should be conservatively bucketed.
        """
        per_minute, burst = self.resolve_bucket(db, user_id, endpoint)
        capacity = max(1, burst)
        refill_per_sec = max(per_minute / 60.0, 0.001)

        bucket_key = tenant_key(user_id, f"ratelimit:{endpoint}")
        now_ms = int(time.time() * 1000)

        try:
            client = self._get_redis()
            allowed_int, tokens_remaining, retry_after_ms = self._consume(
                client, bucket_key, capacity, refill_per_sec, now_ms, cost
            )
        except (
            redis_sync.exceptions.ConnectionError,
            redis_sync.exceptions.TimeoutError,
            redis_sync.exceptions.RedisError,
            OSError,
        ) as exc:
            # IRON LAW: fail CLOSED. Surface 503 (not 429) so the caller
            # knows this is an infrastructure failure, not user abuse.
            logger.error(
                "rate_limiter: Redis unreachable; failing CLOSED user_id=%s endpoint=%s err=%s",
                user_id,
                endpoint,
                exc,
            )
            return RateLimitResult(
                decision=RateLimitDecision.FAILED_CLOSED,
                bucket_per_minute=per_minute,
                burst_capacity=capacity,
                tokens_remaining=0,
                retry_after_ms=1000,
            )

        if allowed_int == 1:
            return RateLimitResult(
                decision=RateLimitDecision.ALLOWED,
                bucket_per_minute=per_minute,
                burst_capacity=capacity,
                tokens_remaining=tokens_remaining,
                retry_after_ms=0,
            )

        # 429 — log a violation row. The middleware that called us is
        # responsible for the actual HTTP response.
        try:
            db.add(
                RateLimitViolation(
                    user_id=user_id,
                    endpoint=endpoint,
                    headers=None,
                )
            )
            db.commit()
        except Exception as exc:  # pragma: no cover - best-effort audit
            logger.warning("rate_limiter: failed to record violation: %s", exc)
            db.rollback()

        return RateLimitResult(
            decision=RateLimitDecision.LIMITED,
            bucket_per_minute=per_minute,
            burst_capacity=capacity,
            tokens_remaining=tokens_remaining,
            retry_after_ms=retry_after_ms,
        )


# Process-wide singleton (lazy redis connect inside).
rate_limiter = TenantRateLimiter()
