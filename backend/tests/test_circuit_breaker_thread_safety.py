"""Tests for circuit breaker thread safety.

Verifies that concurrent access from multiple threads doesn't corrupt
state, and that failure/success recording works under contention.
"""

import threading
import pytest

from backend.services.risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig


pytestmark = pytest.mark.no_db


class MockRedis:
    """Thread-safe in-memory Redis mock."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            val = self._data.get(key)
            return val.encode() if isinstance(val, str) else val

    def set(self, key, value):
        with self._lock:
            self._data[key] = str(value) if not isinstance(value, str) else value

    def delete(self, key):
        with self._lock:
            self._data.pop(key if isinstance(key, str) else key.decode(), None)

    def incr(self, key):
        with self._lock:
            val = int(self._data.get(key, 0) or 0)
            self._data[key] = str(val + 1)
            return val + 1

    def scan_iter(self, pattern):
        with self._lock:
            prefix = pattern.rstrip("*")
            return [k for k in self._data.keys() if k.startswith(prefix)]


@pytest.fixture
def thread_safe_redis():
    return MockRedis()


@pytest.fixture
def cb(thread_safe_redis):
    config = CircuitBreakerConfig(
        tier1_loss_pct=2.0,
        tier2_loss_pct=3.0,
        tier3_loss_pct=5.0,
        max_orders_per_day=500,
        max_orders_per_symbol=50,
        consecutive_loss_limit=10,
    )
    breaker = CircuitBreaker(config=config, redis_client=thread_safe_redis)
    breaker.set_starting_equity(100_000)
    return breaker


class TestConcurrentAccess:
    """Multiple threads calling can_trade() simultaneously."""

    def test_concurrent_can_trade_does_not_crash(self, cb):
        """50 threads calling can_trade() concurrently should not raise."""
        errors = []

        def worker():
            try:
                for _ in range(20):
                    cb.can_trade()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Concurrent can_trade() raised: {errors}"

    def test_concurrent_record_fill_no_crash(self, cb):
        """Multiple threads recording fills simultaneously."""
        errors = []

        def worker(thread_id):
            try:
                for i in range(10):
                    cb.record_fill(f"SYM{thread_id}", -10, is_exit=True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Concurrent record_fill() raised: {errors}"


class TestFailureRecordingUnderContention:
    """Verify failure accumulation is correct under thread contention."""

    def test_all_losses_counted(self, cb, thread_safe_redis):
        """20 threads each recording 5 fills = 100 total order count."""
        barrier = threading.Barrier(20)

        def worker():
            barrier.wait()
            for _ in range(5):
                cb.record_fill("AAPL", -10, is_exit=True)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        order_count = int(thread_safe_redis.get("circuit:order_count") or 0)
        assert order_count == 100, f"Expected 100 orders, got {order_count}"


class TestSuccessResetsFailures:
    """A winning trade resets the consecutive loss counter."""

    def test_win_resets_consecutive_losses(self, cb, thread_safe_redis):
        """After consecutive losses, a win resets the counter to 0."""
        for _ in range(5):
            cb.record_fill("AAPL", -100, is_exit=True)

        consec = int(thread_safe_redis.get("circuit:consecutive_losses") or 0)
        assert consec == 5

        cb.record_fill("MSFT", 500, is_exit=True)

        consec = int(thread_safe_redis.get("circuit:consecutive_losses") or 0)
        assert consec == 0, "Winning trade should reset consecutive losses"

    def test_mixed_concurrent_wins_and_losses(self, cb, thread_safe_redis):
        """Concurrent wins and losses shouldn't crash."""
        errors = []

        def loser():
            try:
                for _ in range(10):
                    cb.record_fill("LOSE", -50, is_exit=True)
            except Exception as e:
                errors.append(e)

        def winner():
            try:
                for _ in range(10):
                    cb.record_fill("WIN", 50, is_exit=True)
            except Exception as e:
                errors.append(e)

        threads = [
            *[threading.Thread(target=loser) for _ in range(5)],
            *[threading.Thread(target=winner) for _ in range(5)],
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Mixed concurrent fills raised: {errors}"

        status = cb.get_status()
        assert isinstance(status["tier"], int)
        assert isinstance(status["daily_pnl"], float)
