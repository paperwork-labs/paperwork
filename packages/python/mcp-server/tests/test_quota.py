"""Unit tests for :class:`mcp_server.quota.DailyCallQuota`."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from mcp_server.quota import DailyCallQuota, make_module_level_quota


class TestConsumeBasic:
    def test_first_call_under_limit_returns_true(self, fake_redis_factory):
        q = DailyCallQuota(fake_redis_factory)
        assert q.consume(user_id=1, limit=5) is True

    def test_exactly_at_limit_returns_true(self, fake_redis_factory):
        q = DailyCallQuota(fake_redis_factory)
        for _ in range(5):
            assert q.consume(user_id=1, limit=5) is True

    def test_over_limit_returns_false(self, fake_redis_factory):
        q = DailyCallQuota(fake_redis_factory)
        for _ in range(5):
            q.consume(user_id=1, limit=5)
        assert q.consume(user_id=1, limit=5) is False

    def test_per_user_isolation(self, fake_redis_factory):
        q = DailyCallQuota(fake_redis_factory)
        for _ in range(3):
            q.consume(user_id=1, limit=3)
        # User 2 starts fresh.
        assert q.consume(user_id=2, limit=3) is True


class TestKeyShape:
    def test_key_uses_prefix_user_and_iso_date(self, fake_redis):
        clock = lambda: datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
        q = DailyCallQuota(
            lambda: fake_redis, key_prefix="myproduct:mcp", clock=clock
        )
        q.consume(user_id=42, limit=1000)
        keys = [k.decode() if isinstance(k, bytes) else k for k in fake_redis.keys("*")]
        assert "myproduct:mcp:42:2026-05-03" in keys

    def test_ttl_set_on_first_increment(self, fake_redis):
        clock = lambda: datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
        q = DailyCallQuota(lambda: fake_redis, clock=clock)
        q.consume(user_id=42, limit=1000)
        ttl = fake_redis.ttl("mcp:calls:42:2026-05-03")
        # Default TTL is 25h; allow some slack for test execution.
        assert 24 * 3600 <= ttl <= 26 * 3600


class TestDegradation:
    def test_redis_outage_fails_open(self):
        broken = MagicMock()
        broken.incr.side_effect = ConnectionError("redis down")
        q = DailyCallQuota(lambda: broken)
        # Fail-OPEN: still allows the call.
        assert q.consume(user_id=1, limit=5) is True
        snap = q.degradation_snapshot()
        assert snap["count"] == 1
        assert "redis down" in snap["last_error"]
        assert snap["last_at"] is not None

    def test_factory_explosion_also_fails_open(self):
        def factory():
            raise RuntimeError("can't construct client")

        q = DailyCallQuota(factory)
        assert q.consume(user_id=1, limit=5) is True
        snap = q.degradation_snapshot()
        assert snap["count"] == 1

    def test_snapshot_returns_copy(self, fake_redis_factory):
        q = DailyCallQuota(fake_redis_factory)
        snap = q.degradation_snapshot()
        snap["count"] = 999
        assert q.degradation_snapshot()["count"] == 0


class TestDayRollover:
    def test_new_day_resets_counter(self, fake_redis):
        ts = {"now": datetime(2026, 5, 3, 23, 59, tzinfo=UTC)}
        q = DailyCallQuota(lambda: fake_redis, clock=lambda: ts["now"])
        for _ in range(5):
            q.consume(user_id=1, limit=5)
        assert q.consume(user_id=1, limit=5) is False
        # New day -> fresh counter.
        ts["now"] = datetime(2026, 5, 4, 0, 0, 1, tzinfo=UTC)
        assert q.consume(user_id=1, limit=5) is True


class TestModuleLevelHelper:
    def test_returns_quota_and_callable_snapshot(self, fake_redis_factory):
        q, snap = make_module_level_quota(fake_redis_factory)
        assert isinstance(q, DailyCallQuota)
        assert callable(snap)
        assert snap() == {"count": 0, "last_error": None, "last_at": None}
