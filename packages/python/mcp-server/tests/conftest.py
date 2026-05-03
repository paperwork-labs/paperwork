"""Shared pytest fixtures for the mcp-server package."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest


@pytest.fixture
def fake_redis():
    """Return an in-memory Redis double via ``fakeredis``."""
    fakeredis = pytest.importorskip("fakeredis")
    return fakeredis.FakeStrictRedis()


@pytest.fixture
def fake_redis_factory(fake_redis) -> Callable[[], Any]:
    """A zero-arg factory matching ``DailyCallQuota``'s constructor arg."""
    return lambda: fake_redis
