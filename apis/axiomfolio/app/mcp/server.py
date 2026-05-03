"""AxiomFolio adapter for the shared :mod:`mcp_server` package.

The dispatcher, JSON-RPC envelope handling, fail-CLOSED scope gating,
reserved-arg blocking, and per-user daily quota all live in
``packages/python/mcp-server/`` (Wave K2). This module wires those
generic pieces to AxiomFolio specifics:

* the production tool catalog (:mod:`app.mcp.tools`);
* AxiomFolio's ``MarketInfra`` Redis client for the daily quota.

The public surface of this module is stable from before the extraction
so callers (``app/api/routes/mcp.py``, ``app/mcp/__init__.py``) keep
working byte-identical:

* :class:`MCPServer` re-exported from the shared package
* :func:`build_default_server` returns the production-wired server
* :func:`mcp_quota_degradation_snapshot` for ``/admin/health``
"""

from __future__ import annotations

from typing import Any

from mcp_server import DailyCallQuota, MCPServer

from app.mcp.tools import (
    TOOL_DEFINITIONS,
    TOOL_HANDLERS,
    TOOL_REQUIRED_SCOPE,
)
from app.services.silver.market.market_data_service import infra


# Lazy factory so we only resolve ``infra.redis_client`` at the moment
# the quota actually needs to talk to Redis. ``MarketInfra`` constructs
# its sync client on first access; calling it eagerly at import time
# would hit Redis during test collection.
def _redis_factory():
    return infra.redis_client


_quota = DailyCallQuota(_redis_factory)


def mcp_quota_degradation_snapshot() -> dict[str, Any]:
    """Return a copy of the quota-degradation counters for ``/admin/health``."""
    return _quota.degradation_snapshot()


def build_default_server() -> MCPServer:
    """Construct the singleton server wired to the production tool catalog."""
    return MCPServer(
        TOOL_DEFINITIONS,
        TOOL_HANDLERS,
        TOOL_REQUIRED_SCOPE,
        quota=_quota,
    )


__all__ = [
    "MCPServer",
    "build_default_server",
    "mcp_quota_degradation_snapshot",
]
