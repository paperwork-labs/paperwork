"""JSON-RPC 2.0 dispatcher for the AxiomFolio MCP transport.

Implements the minimum viable subset of the MCP protocol over plain
HTTP JSON-RPC: ``tools/list`` and ``tools/call``. We intentionally
skip the SSE / stdio transports the upstream Python ``mcp`` SDK uses
because:

* Our consumers are HTTP MCP clients (ChatGPT, Cursor, Claude desktop)
  configured with a simple bearer-authed POST endpoint.
* The SDK adds a heavy async machinery surface that doesn't fit
  FastAPI's existing dependency-injection auth path.
* Limiting ourselves to a tiny dispatcher keeps the audit surface
  small, which matters for a credential-bearing endpoint.

Per-call ``user_id`` is **always** taken from the authenticated bearer
token (see :mod:`backend.mcp.auth`); any caller-supplied ``user_id``
in the JSON-RPC arguments is rejected with ``-32602 Invalid params``.
"""

from __future__ import annotations

import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.mcp.tools import TOOL_DEFINITIONS, TOOL_HANDLERS, TOOL_REQUIRED_SCOPE
from app.services.silver.market.market_data_service import infra

logger = logging.getLogger(__name__)


JSONRPC_VERSION = "2.0"

# JSON-RPC 2.0 reserved error codes
ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603

# Argument names that must NEVER be accepted from a client because the
# transport injects them from the authenticated context.
RESERVED_ARG_NAMES = frozenset({"user_id", "db", "session"})


# Degradation surface for the /admin/health endpoint. Incremented each
# time _consume_daily_quota fails open because Redis is unreachable.
# Keeping this module-level rather than in Redis lets us reliably report
# Redis outages without a chicken-and-egg problem.
_MCP_QUOTA_REDIS_UNAVAILABLE: Dict[str, Any] = {
    "count": 0,
    "last_error": None,
    "last_at": None,
}


def mcp_quota_degradation_snapshot() -> Dict[str, Any]:
    """Return a copy of the quota-degradation counters for /admin/health."""
    return dict(_MCP_QUOTA_REDIS_UNAVAILABLE)


def _error(
    request_id: Any,
    code: int,
    message: str,
    *,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Render a JSON-RPC 2.0 error envelope."""
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": err}


def _result(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


class MCPServer:
    """Dispatch JSON-RPC envelopes to per-tool handlers."""

    def __init__(
        self,
        tool_definitions: List[Dict[str, Any]],
        tool_handlers: Dict[str, Callable[..., Dict[str, Any]]],
    ) -> None:
        self._definitions = tool_definitions
        self._handlers = tool_handlers
        self._known_tools = set(tool_handlers.keys())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(
        self,
        payload: Any,
        *,
        db: Session,
        user_id: int,
        allowed_scopes: frozenset[str],
        daily_limit: Optional[int],
    ) -> Dict[str, Any]:
        """Process one JSON-RPC envelope, returning the response envelope."""
        if not isinstance(payload, dict):
            return _error(
                None, ERR_INVALID_REQUEST, "Request must be a JSON object"
            )

        request_id = payload.get("id")
        if payload.get("jsonrpc") != JSONRPC_VERSION:
            return _error(
                request_id,
                ERR_INVALID_REQUEST,
                "Only JSON-RPC 2.0 envelopes are accepted",
            )

        method = payload.get("method")
        if not isinstance(method, str):
            return _error(
                request_id, ERR_INVALID_REQUEST, "Missing 'method' string"
            )

        params = payload.get("params") or {}
        if not isinstance(params, dict):
            return _error(
                request_id,
                ERR_INVALID_PARAMS,
                "'params' must be an object",
            )

        if method == "tools/list":
            visible = []
            for tool in self._definitions:
                name = str(tool.get("name", ""))
                # Fail-CLOSED: unmapped tools must never appear in tools/list.
                # Adding a new tool therefore requires an explicit entry in
                # TOOL_REQUIRED_SCOPE; otherwise it stays hidden for every
                # tier (including Free).
                required = TOOL_REQUIRED_SCOPE.get(name)
                if required is None:
                    logger.warning(
                        "MCP tool %r has no TOOL_REQUIRED_SCOPE entry; "
                        "hiding from tools/list",
                        name,
                    )
                    continue
                if required in allowed_scopes:
                    visible.append(tool)
            return _result(request_id, {"tools": visible})
        if method == "tools/call":
            return self._handle_tools_call(
                request_id,
                params,
                db=db,
                user_id=user_id,
                allowed_scopes=allowed_scopes,
                daily_limit=daily_limit,
            )

        return _error(
            request_id,
            ERR_METHOD_NOT_FOUND,
            f"Unknown method: {method}",
            data={"supported": ["tools/list", "tools/call"]},
        )

    # ------------------------------------------------------------------
    # Internal: tools/call
    # ------------------------------------------------------------------

    def _handle_tools_call(
        self,
        request_id: Any,
        params: Dict[str, Any],
        *,
        db: Session,
        user_id: int,
        allowed_scopes: frozenset[str],
        daily_limit: Optional[int],
    ) -> Dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return _error(
                request_id, ERR_INVALID_PARAMS, "Missing 'name' for tools/call"
            )
        if name not in self._known_tools:
            return _error(
                request_id,
                ERR_METHOD_NOT_FOUND,
                f"Unknown tool: {name}",
                data={"supported": sorted(self._known_tools)},
            )
        # Fail-CLOSED: reject with an explicit 403-ish error if the tool
        # has no scope mapping. Never default to a permissive scope —
        # that would auto-grant newly added tools to every tier.
        required_scope = TOOL_REQUIRED_SCOPE.get(name)
        if required_scope is None:
            logger.warning(
                "MCP tool %r has no TOOL_REQUIRED_SCOPE entry; rejecting tools/call",
                name,
            )
            return _error(
                request_id,
                ERR_METHOD_NOT_FOUND,
                f"Tool '{name}' is not registered for tier gating",
                data={"tool": name},
            )
        if required_scope not in allowed_scopes:
            return _error(
                request_id,
                ERR_METHOD_NOT_FOUND,
                f"Tool '{name}' is not available for this tier",
                data={"required_scope": required_scope},
            )
        if daily_limit is not None and not self._consume_daily_quota(
            user_id=user_id, limit=daily_limit
        ):
            return _error(
                request_id,
                ERR_INVALID_REQUEST,
                "Daily MCP call limit reached",
                data={"limit": daily_limit},
            )
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _error(
                request_id,
                ERR_INVALID_PARAMS,
                "'arguments' must be an object",
            )

        # Defense in depth: callers must never override user_id, db, or
        # session — the transport injects those from the authenticated
        # MCP context.
        for reserved in arguments.keys() & RESERVED_ARG_NAMES:
            return _error(
                request_id,
                ERR_INVALID_PARAMS,
                f"Argument '{reserved}' is reserved and cannot be supplied",
            )

        handler = self._handlers[name]
        sig = inspect.signature(handler)
        accepted = set(sig.parameters.keys())
        unknown = set(arguments.keys()) - accepted
        if unknown:
            return _error(
                request_id,
                ERR_INVALID_PARAMS,
                "Unknown argument(s) for tool",
                data={"unknown": sorted(unknown), "tool": name},
            )

        try:
            result = handler(db=db, user_id=user_id, **arguments)
        except ValueError as ve:
            return _error(
                request_id, ERR_INVALID_PARAMS, str(ve), data={"tool": name}
            )
        except Exception as e:
            # No silent fallback: log + surface as JSON-RPC internal
            # error. The detail is intentionally generic so we don't
            # leak internals across the wire.
            logger.exception(
                "MCP tool '%s' failed for user_id=%s: %s", name, user_id, e
            )
            return _error(
                request_id,
                ERR_INTERNAL,
                "Tool execution failed",
                data={"tool": name},
            )

        return _result(request_id, {"content": result})

    def _consume_daily_quota(self, *, user_id: int, limit: int) -> bool:
        day = datetime.now(timezone.utc).date().isoformat()
        key = f"mcp:calls:{user_id}:{day}"
        try:
            r = infra.redis_client
            used = int(r.incr(key))
            if used == 1:
                r.expire(key, 60 * 60 * 24 + 60 * 60)
            return used <= limit
        except Exception as e:
            # Fail-OPEN on rate-limiter infra outage: allow the call but
            # record the degradation loudly so operators can catch it.
            # The platform treats rate-limit infra as best-effort (see
            # docs/KNOWLEDGE.md D63) — a Redis hiccup must not cascade
            # into a hard MCP outage for every tier.
            logger.warning(
                "MCP quota Redis unavailable (fail-open) user_id=%s: %s",
                user_id,
                e,
            )
            try:
                # Surface degradation in /admin/health counters. Best
                # effort; if even this counter is wedged we still allow.
                _MCP_QUOTA_REDIS_UNAVAILABLE["count"] += 1
                _MCP_QUOTA_REDIS_UNAVAILABLE["last_error"] = str(e)
                _MCP_QUOTA_REDIS_UNAVAILABLE["last_at"] = (
                    datetime.now(timezone.utc).isoformat()
                )
            except Exception:  # noqa: BLE001 - counter is diagnostic only
                pass
            return True


def build_default_server() -> MCPServer:
    """Construct the singleton server wired to the production tool catalog."""
    return MCPServer(TOOL_DEFINITIONS, TOOL_HANDLERS)
