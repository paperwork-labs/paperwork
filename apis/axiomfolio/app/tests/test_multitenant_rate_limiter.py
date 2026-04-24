"""Unit tests for the per-tenant rate limiter.

We don't hit a real Redis here; we inject a fakeredis instance so the
test runs in CI without infra. The limiter uses a WATCH/MULTI/EXEC
client-side token bucket (no Lua), so fakeredis is sufficient.
"""

from __future__ import annotations

import pytest

from app.services.multitenant.rate_limiter import (
    DEFAULT_BUCKET_PER_MINUTE,
    DEFAULT_BURST_CAPACITY,
    RateLimitDecision,
    TenantRateLimiter,
)

pytestmark = pytest.mark.no_db


@pytest.fixture
def fake_redis():
    fakeredis = pytest.importorskip("fakeredis")
    return fakeredis.FakeRedis()


@pytest.fixture
def limiter(fake_redis):
    return TenantRateLimiter(redis_client=fake_redis)


class _StubDB:
    """Bare-minimum stand-in for an SA Session (limiter only uses
    ``execute(stmt).scalar_one_or_none()`` to look up overrides and
    ``add()`` / ``commit()`` to log violations).
    """

    def __init__(self):
        self.added = []

    def execute(self, *args, **kwargs):
        return _StubResult()

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def rollback(self):
        pass


class _StubResult:
    def scalar_one_or_none(self):
        return None


class _StubRateLimitRow:
    def __init__(self, per_minute: int, burst: int):
        self.bucket_size_per_minute = per_minute
        self.burst_capacity = burst


def test_first_call_allowed_with_default_bucket(limiter):
    db = _StubDB()
    result = limiter.check(db, user_id=42, endpoint="/api/v1/things")
    assert result.decision == RateLimitDecision.ALLOWED
    assert result.bucket_per_minute == DEFAULT_BUCKET_PER_MINUTE
    assert result.burst_capacity == DEFAULT_BURST_CAPACITY
    assert result.tokens_remaining < DEFAULT_BURST_CAPACITY


def test_burst_exhaustion_returns_429(limiter):
    db = _StubDB()
    decisions = []
    for _ in range(DEFAULT_BURST_CAPACITY + 5):
        decisions.append(limiter.check(db, user_id=42, endpoint="/api/v1/burst").decision)
    assert RateLimitDecision.LIMITED in decisions
    last = decisions[-1]
    assert last == RateLimitDecision.LIMITED


def test_violation_row_recorded_on_429(limiter):
    db = _StubDB()
    for _ in range(DEFAULT_BURST_CAPACITY + 1):
        limiter.check(db, user_id=42, endpoint="/api/v1/recordme")
    # The exact count depends on bucket math, but at least one limited
    # result must have produced a violation row.
    from app.models.multitenant import RateLimitViolation

    assert any(isinstance(o, RateLimitViolation) for o in db.added)


def test_isolation_between_tenants(limiter):
    """Tenant A consuming all burst tokens must not affect tenant B."""
    db = _StubDB()
    for _ in range(DEFAULT_BURST_CAPACITY + 5):
        limiter.check(db, user_id=1, endpoint="/api/v1/iso")

    # Tenant B should still be served.
    result = limiter.check(db, user_id=2, endpoint="/api/v1/iso")
    assert result.decision == RateLimitDecision.ALLOWED


def test_redis_unreachable_fails_closed():
    """If Redis raises ConnectionError we MUST return FAILED_CLOSED.

    The middleware then turns this into a 503, not a 429 — operators
    can tell infrastructure outage from user abuse.
    """
    import redis as redis_sync

    class _ExplodingRedis:
        def pipeline(self):
            raise redis_sync.exceptions.ConnectionError("boom")

    bad = TenantRateLimiter(redis_client=_ExplodingRedis())
    db = _StubDB()
    result = bad.check(db, user_id=99, endpoint="/api/v1/closed")
    assert result.decision == RateLimitDecision.FAILED_CLOSED
    assert result.http_status == 503


def test_anonymous_caller_buckets_globally(limiter):
    """user_id=None still rate-limits, just under tenant:global."""
    db = _StubDB()
    result = limiter.check(db, user_id=None, endpoint="/api/v1/anon")
    assert result.decision == RateLimitDecision.ALLOWED


def test_resolve_bucket_uses_endpoint_override(limiter):
    class _DB(_StubDB):
        def execute(self, *args, **kwargs):
            class _R:
                def scalar_one_or_none(self_inner):
                    return _StubRateLimitRow(per_minute=3, burst=3)

            return _R()

    db = _DB()
    result = limiter.check(
        db,
        user_id=99,
        endpoint="/api/v1/accounts/:id/historical-import",
    )
    assert result.bucket_per_minute == 3
    assert result.burst_capacity == 3
