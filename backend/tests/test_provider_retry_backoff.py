"""Verify provider retry behaviour for rate-limit (429) and transient errors.

Background: production v0 was hitting Yahoo Finance rate limits during
``fundamentals.fill_missing``. The original retry logic capped attempts to 2
on the first 429, which made things strictly worse — Yahoo's throttle
window persists for >5 min and the call gave up after ~2 seconds. This
test guards the fix that grants the full retry budget with a longer base
delay on rate-limited calls.

We patch ``time.sleep`` and ``asyncio.sleep`` so the tests run in
milliseconds while still asserting the *shape* of the backoff (which base
delay was selected and how many attempts were made).
"""
from __future__ import annotations

from typing import List

import pytest

from backend.services.market import provider_router as pr_module


class _FakeProviderRouter:
    """Shim exposing only the retry helpers under test.

    ``_extract_http_status`` is decorated with ``@staticmethod`` on the real
    router; copying it via attribute access unwraps the descriptor, so we
    have to re-wrap it here. Otherwise Python rebinds it as a regular
    method and passes ``self`` as the first arg, breaking the call.
    """

    _call_blocking_with_retries = pr_module.ProviderRouter._call_blocking_with_retries
    _call_blocking_with_retries_sync = pr_module.ProviderRouter._call_blocking_with_retries_sync
    _extract_http_status = staticmethod(pr_module.ProviderRouter._extract_http_status)


class _RateLimitError(Exception):
    """Mimics yfinance's typical 429 surface — message contains 'too many'."""

    def __init__(self, msg: str = "429 Client Error: Too Many Requests") -> None:
        super().__init__(msg)


def _make_failing_fn(times: int, exc_factory):
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] <= times:
            raise exc_factory()
        return "ok"

    return fn, calls


def test_sync_rate_limited_uses_full_retry_budget(monkeypatch):
    """The previous bug capped retries to 2 on first 429. Verify that a
    rate-limited call now uses the full attempts budget (default 6)."""
    sleeps: List[float] = []
    monkeypatch.setattr(pr_module.time, "sleep", lambda s: sleeps.append(s))

    fn, calls = _make_failing_fn(5, _RateLimitError)
    router = _FakeProviderRouter()

    result = _FakeProviderRouter._call_blocking_with_retries_sync(router, fn, attempts=6)

    assert result == "ok"
    assert calls["n"] == 6, "should have used full 6-attempt budget"
    assert len(sleeps) == 5, "5 retries means 5 sleeps between them"


def test_sync_rate_limited_uses_long_base_delay(monkeypatch):
    """A rate-limited call's first sleep should be >> a non-transient
    failure's first sleep (8s base vs 0.2s)."""
    sleeps: List[float] = []
    monkeypatch.setattr(pr_module.time, "sleep", lambda s: sleeps.append(s))

    fn, _ = _make_failing_fn(2, _RateLimitError)
    router = _FakeProviderRouter()

    try:
        _FakeProviderRouter._call_blocking_with_retries_sync(router, fn, attempts=3)
    except _RateLimitError:
        pass

    # First sleep should be ~8 * jitter (between 6 and 12s).
    assert sleeps, "expected at least one sleep"
    assert 4.0 <= sleeps[0] <= 12.5, f"rate-limit first sleep {sleeps[0]} outside expected 6-12s window"


def test_sync_non_transient_uses_short_base_delay(monkeypatch):
    """Non-transient errors still get the fast ~0.2s base delay so we don't
    pause unnecessarily for things like 404s."""
    sleeps: List[float] = []
    monkeypatch.setattr(pr_module.time, "sleep", lambda s: sleeps.append(s))

    class _NotFound(Exception):
        pass

    fn, _ = _make_failing_fn(2, _NotFound)
    router = _FakeProviderRouter()

    try:
        _FakeProviderRouter._call_blocking_with_retries_sync(router, fn, attempts=3)
    except _NotFound:
        pass

    assert sleeps, "expected at least one sleep"
    # 0.2 base * jitter (0.75-1.25) => 0.15-0.25s
    assert sleeps[0] < 1.0, f"non-transient first sleep {sleeps[0]} too long"


def test_sync_transient_5xx_uses_medium_base_delay(monkeypatch):
    """5xx but not rate-limited should use 0.8s base."""
    sleeps: List[float] = []
    monkeypatch.setattr(pr_module.time, "sleep", lambda s: sleeps.append(s))

    class _ServerError(Exception):
        def __init__(self):
            super().__init__("500 Internal Server Error")
            self.status_code = 500

    fn, _ = _make_failing_fn(2, _ServerError)
    router = _FakeProviderRouter()

    try:
        _FakeProviderRouter._call_blocking_with_retries_sync(router, fn, attempts=3)
    except _ServerError:
        pass

    assert sleeps, "expected at least one sleep"
    # 0.8 base * jitter (0.75-1.25) => 0.6-1.0s — should sit between non-transient and rate-limit.
    assert 0.4 <= sleeps[0] <= 2.0, f"transient first sleep {sleeps[0]} outside expected 0.6-1.0s window"


def test_sync_no_runaway_when_max_delay_caps(monkeypatch):
    """The max_delay_seconds cap should kick in for late retries even on
    rate-limit; 8 * 2^4 = 128 must clamp to 60s default."""
    sleeps: List[float] = []
    monkeypatch.setattr(pr_module.time, "sleep", lambda s: sleeps.append(s))

    fn, _ = _make_failing_fn(10, _RateLimitError)
    router = _FakeProviderRouter()

    try:
        _FakeProviderRouter._call_blocking_with_retries_sync(
            router, fn, attempts=6, max_delay_seconds=60.0
        )
    except _RateLimitError:
        pass

    # max sleep should never exceed 60 * 1.25 (jitter ceiling) = 75s
    assert max(sleeps) <= 75.5, f"sleep {max(sleeps)} blew past max_delay cap"


@pytest.mark.asyncio
async def test_async_rate_limited_uses_full_retry_budget(monkeypatch):
    """Mirror of the sync test for the async path."""
    sleeps: List[float] = []

    async def _fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(pr_module.asyncio, "sleep", _fake_sleep)

    fn, calls = _make_failing_fn(5, _RateLimitError)
    router = _FakeProviderRouter()

    result = await _FakeProviderRouter._call_blocking_with_retries(router, fn, attempts=6)

    assert result == "ok"
    assert calls["n"] == 6
    assert len(sleeps) == 5
