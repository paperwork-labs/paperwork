"""Tests for app.services.cache — the module whose absence silently
disabled distributed locks on every sync, order submit, and webhook idempotency
check. See KNOWLEDGE.md R40.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_module_imports() -> None:
    """The module must exist so `from app.services.cache import redis_client`
    in callers doesn't raise ModuleNotFoundError."""
    import app.services.cache as cache_mod

    assert hasattr(cache_mod, "get_redis_client")


def test_get_redis_client_raises_without_url() -> None:
    """Fail loudly (not silently return a no-op) if REDIS_URL is missing."""
    import app.services.cache as cache_mod

    cache_mod._redis_client = None
    with patch.object(cache_mod.settings, "REDIS_URL", ""):
        with pytest.raises(RuntimeError, match="REDIS_URL"):
            cache_mod.get_redis_client()


def test_get_redis_client_memoizes() -> None:
    """Subsequent calls return the same client instance (no reconnect storm)."""
    import app.services.cache as cache_mod

    cache_mod._redis_client = None
    fake_client = object()
    with patch.object(cache_mod.settings, "REDIS_URL", "redis://localhost:6379/0"):
        with patch.object(cache_mod.redis, "from_url", return_value=fake_client) as mock_from_url:
            first = cache_mod.get_redis_client()
            second = cache_mod.get_redis_client()
            assert first is fake_client
            assert second is fake_client
            assert mock_from_url.call_count == 1

    cache_mod._redis_client = None


def test_module_attr_redis_client_lazy() -> None:
    """`from app.services.cache import redis_client` triggers
    instantiation via module __getattr__, not at import time."""
    import app.services.cache as cache_mod

    cache_mod._redis_client = None
    fake_client = object()
    with patch.object(cache_mod.settings, "REDIS_URL", "redis://localhost:6379/0"):
        with patch.object(cache_mod.redis, "from_url", return_value=fake_client):
            client = cache_mod.redis_client
            assert client is fake_client

    cache_mod._redis_client = None


def test_module_attr_unknown_raises() -> None:
    import app.services.cache as cache_mod

    with pytest.raises(AttributeError):
        _ = cache_mod.nonexistent_attribute
