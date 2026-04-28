"""Decorator for APScheduler async jobs: skip execution when Brain is paused (WS-45)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

from app.services.kill_switch import is_brain_paused
from app.services.kill_switch import reason as pause_reason

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def skip_if_brain_paused(job_id: str) -> Callable[[F], F]:
    """Wrap an async scheduler callable; if paused, log and return without running the body."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if is_brain_paused():
                why = pause_reason() or ""
                logger.info("job %s skipped (brain paused: %s)", job_id, why)
                return None
            return await fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
