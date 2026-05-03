"""Pre-built SlowAPI key callables for common request state shapes."""

from __future__ import annotations

from collections.abc import Callable

from slowapi.util import get_remote_address
from starlette.requests import Request


def get_user_id_key(request: Request) -> str:
    """Prefer ``request.state.user_id``; fall back to client IP."""
    uid = getattr(request.state, "user_id", None)
    if uid is not None:
        return str(uid)
    return get_remote_address(request)


def get_org_id_key(request: Request) -> str:
    """Prefer ``request.state.org_id``; fall back to client IP."""
    oid = getattr(request.state, "org_id", None)
    if oid is not None:
        return str(oid)
    return get_remote_address(request)


def get_remote_address_key(request: Request) -> str:
    """Always rate-limit by client IP (compose-friendly default)."""
    return get_remote_address(request)


KeyFunc = Callable[[Request], str]

__all__ = [
    "KeyFunc",
    "get_org_id_key",
    "get_remote_address_key",
    "get_user_id_key",
]
