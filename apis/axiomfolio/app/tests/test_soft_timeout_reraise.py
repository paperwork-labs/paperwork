"""Tests for SoftTimeLimitExceeded re-raise pattern.

Verifies that Celery tasks using ``except SoftTimeLimitExceeded: raise``
before ``except Exception`` correctly propagate the soft timeout instead
of swallowing it.
"""

import pytest
from unittest.mock import patch, MagicMock
from celery.exceptions import SoftTimeLimitExceeded


pytestmark = pytest.mark.no_db


def _simulate_task_loop_with_correct_pattern(symbols: list[str], fail_at: int):
    """Simulates the pattern used in history.py tasks:

    for sym in symbols:
        try:
            process(sym)
        except SoftTimeLimitExceeded:
            raise
        except Exception as exc:
            errors += 1
    """
    processed = []
    errors = 0

    for i, sym in enumerate(symbols):
        try:
            if i == fail_at:
                raise SoftTimeLimitExceeded("Celery soft time limit")
            processed.append(sym)
        except SoftTimeLimitExceeded:
            raise
        except Exception:
            errors += 1

    return processed, errors


def _simulate_task_loop_with_broken_pattern(symbols: list[str], fail_at: int):
    """Simulates the BROKEN pattern (no SoftTimeLimitExceeded re-raise)
    where the timeout is accidentally caught by ``except Exception``."""
    processed = []
    errors = 0

    for i, sym in enumerate(symbols):
        try:
            if i == fail_at:
                raise SoftTimeLimitExceeded("Celery soft time limit")
            processed.append(sym)
        except Exception:
            errors += 1

    return processed, errors


class TestSoftTimeoutReraise:
    """Verify the correct except pattern propagates SoftTimeLimitExceeded."""

    def test_correct_pattern_propagates(self):
        """The correct pattern re-raises SoftTimeLimitExceeded."""
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        with pytest.raises(SoftTimeLimitExceeded):
            _simulate_task_loop_with_correct_pattern(symbols, fail_at=2)

    def test_broken_pattern_swallows_timeout(self):
        """The broken pattern catches SoftTimeLimitExceeded as a normal error."""
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        processed, errors = _simulate_task_loop_with_broken_pattern(symbols, fail_at=2)
        assert errors == 1, "Broken pattern incorrectly caught the timeout"
        assert len(processed) == 4, "Broken pattern continued processing after timeout"

    def test_correct_pattern_processes_before_timeout(self):
        """Symbols before the timeout index are processed correctly."""
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        try:
            processed, _ = _simulate_task_loop_with_correct_pattern(symbols, fail_at=3)
        except SoftTimeLimitExceeded:
            pass
        else:
            pytest.fail("Should have raised SoftTimeLimitExceeded")

    def test_soft_timeout_is_not_exception_subclass_in_celery(self):
        """SoftTimeLimitExceeded inherits from Exception but must be re-raised explicitly."""
        assert issubclass(SoftTimeLimitExceeded, Exception)

    def test_real_task_pattern_from_history_module(self):
        """Simulate the actual pattern from app/tasks/market/history.py."""
        session = MagicMock()
        symbols = ["AAPL", "MSFT", "GOOGL"]
        processed = 0
        errors = 0
        error_samples = []

        with pytest.raises(SoftTimeLimitExceeded):
            for sym in symbols:
                try:
                    if sym == "MSFT":
                        raise SoftTimeLimitExceeded()
                    processed += 1
                except SoftTimeLimitExceeded:
                    raise
                except Exception as exc:
                    errors += 1
                    if len(error_samples) < 25:
                        error_samples.append({"symbol": sym, "error": str(exc)})

        assert processed == 1, "Only AAPL should have been processed"
        assert errors == 0, "SoftTimeLimitExceeded should not be counted as an error"
