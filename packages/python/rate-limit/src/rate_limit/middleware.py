"""ASGI middleware wiring SlowAPI into FastAPI / Starlette."""

from __future__ import annotations

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class RateLimitMiddleware:
    """Thin outer shell around :class:`slowapi.middleware.SlowAPIASGIMiddleware`.

    Sets ``app.state.limiter`` and registers ``RateLimitExceeded`` handling on the
    Starlette app the first time a request hits, then delegates to SlowAPI's
    ASGI middleware (which calls ``_rate_limit_exceeded_handler`` for 429s).
    """

    def __init__(self, app: ASGIApp, *, limiter: Limiter) -> None:
        self._inner = SlowAPIASGIMiddleware(app)
        self._limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            app = scope.get("app")
            if app is not None:
                app.state.limiter = self._limiter
                if not getattr(app.state, "_paperwork_rate_limit_exc_handler", False):
                    app.add_exception_handler(
                        RateLimitExceeded, _rate_limit_exceeded_handler
                    )
                    app.state._paperwork_rate_limit_exc_handler = True
        await self._inner(scope, receive, send)


__all__ = ["RateLimitMiddleware"]
