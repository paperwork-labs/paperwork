"""Per-tenant Redis key namespacing.

Single source of truth for the ``tenant:{user_id}:{key}`` convention.
Every cache/lock/queue key that holds user data MUST be wrapped with
``tenant_key`` so we can:

* enforce isolation between users in a shared Redis,
* drop a tenant's keys cleanly during GDPR delete (``SCAN tenant:{id}:*``),
* attribute Redis memory back to a tenant for cost rollup.
"""

from __future__ import annotations

from typing import Optional

_NAMESPACE_PREFIX = "tenant"
_GLOBAL_BUCKET = "global"


def tenant_key(user_id: Optional[int], key: str) -> str:
    """Return ``tenant:{user_id}:{key}`` (or ``tenant:global:{key}`` if user_id is None).

    ``user_id is None`` is reserved for genuinely cross-tenant
    infrastructure (e.g. global rate-limit defaults, market data caches
    that are not user-specific). Pass an int for everything else.
    """
    if user_id is None:
        bucket = _GLOBAL_BUCKET
    else:
        bucket = str(int(user_id))
    if not key:
        raise ValueError("tenant_key requires a non-empty key")
    return f"{_NAMESPACE_PREFIX}:{bucket}:{key}"


def tenant_scan_pattern(user_id: int) -> str:
    """Glob pattern that matches all keys for a single tenant."""
    return f"{_NAMESPACE_PREFIX}:{int(user_id)}:*"
