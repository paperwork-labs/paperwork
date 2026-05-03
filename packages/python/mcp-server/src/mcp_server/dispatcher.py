"""JSON-RPC 2.0 dispatcher for the MCP transport.

Implements the minimum viable subset of the MCP protocol over plain
HTTP JSON-RPC: ``tools/list`` and ``tools/call``. We intentionally
skip the SSE / stdio transports the upstream Python ``mcp`` SDK uses
because:

* Our consumers are HTTP MCP clients (ChatGPT, Cursor, Claude desktop)
  configured with a simple bearer-authed POST endpoint.
* The SDK adds heavy async machinery that doesn't fit FastAPI's
  existing dependency-injection auth path.
* Limiting ourselves to a tiny dispatcher keeps the audit surface
  small, which matters for a credential-bearing endpoint.

Per-call ``user_id`` is **always** taken from the authenticated bearer
token at the route layer; any caller-supplied ``user_id`` (or ``db``,
``session``) in the JSON-RPC arguments is rejected with
``-32602 Invalid params``. This is enforced via :data:`RESERVED_ARG_NAMES`
which the dispatcher refuses to forward to handlers.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Mapping
from typing import Any

from .quota import DailyCallQuota

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
RESERVED_ARG_NAMES: frozenset[str] = frozenset({"user_id", "db", "session"})


def _error(
    request_id: Any,
    code: int,
    message: str,
    *,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render a JSON-RPC 2.0 error envelope."""
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": err}


def _result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


# Type aliases for handler maps. Handlers are duck-typed: they receive
# ``db`` and ``user_id`` plus any whitelisted kwargs from the JSON-RPC
# ``arguments`` object. They must return JSON-serializable data; the
# dispatcher wraps it in ``{"content": ...}``.
ToolHandler = Callable[..., dict[str, Any]]


class MCPServer:
    """Dispatch JSON-RPC envelopes to per-tool handlers.

    Construction parameters
    -----------------------
    tool_definitions
        JSON-Schema-style tool catalog returned by ``tools/list``. Each
        entry must have at least ``name`` and ``description``. Order is
        preserved in the wire response.
    tool_handlers
        ``{name -> callable}``. Each callable must accept ``db`` and
        ``user_id`` keyword arguments; any other declared params can be
        supplied by the caller via ``arguments``.
    tool_required_scope
        ``{name -> required_scope}``. **Fail-CLOSED**: a tool that's
        absent from this map is hidden from ``tools/list`` and rejected
        from ``tools/call``. This guarantees that adding a new tool
        without touching the scope map does not auto-grant it to every
        tier.
    quota
        Optional :class:`DailyCallQuota`. When the route layer provides
        a non-``None`` ``daily_limit`` we increment this counter and
        reject if the cap is exceeded. Pass ``None`` to disable per-call
        rate limiting.
    reserved_arg_names
        Override for :data:`RESERVED_ARG_NAMES` -- only useful for tests
        and for products with extra reserved arg names.
    """

    def __init__(
        self,
        tool_definitions: list[dict[str, Any]],
        tool_handlers: Mapping[str, ToolHandler],
        tool_required_scope: Mapping[str, str],
        *,
        quota: DailyCallQuota | None = None,
        reserved_arg_names: frozenset[str] = RESERVED_ARG_NAMES,
    ) -> None:
        self._definitions = list(tool_definitions)
        self._handlers = dict(tool_handlers)
        self._scope_map = dict(tool_required_scope)
        self._known_tools = set(self._handlers.keys())
        self._quota = quota
        self._reserved = reserved_arg_names

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(
        self,
        payload: Any,
        *,
        db: Any,
        user_id: int,
        allowed_scopes: frozenset[str],
        daily_limit: int | None,
    ) -> dict[str, Any]:
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
            return _result(
                request_id,
                {"tools": self._tools_list(allowed_scopes)},
            )
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
    # Internal: tools/list
    # ------------------------------------------------------------------

    def _tools_list(self, allowed_scopes: frozenset[str]) -> list[dict[str, Any]]:
        visible: list[dict[str, Any]] = []
        for tool in self._definitions:
            name = str(tool.get("name", ""))
            # Fail-CLOSED: unmapped tools must never appear in tools/list.
            # Adding a new tool therefore requires an explicit entry in
            # tool_required_scope; otherwise it stays hidden for every
            # tier (including FREE).
            required = self._scope_map.get(name)
            if required is None:
                logger.warning(
                    "MCP tool %r has no required-scope entry; "
                    "hiding from tools/list",
                    name,
                )
                continue
            if required in allowed_scopes:
                visible.append(tool)
        return visible

    # ------------------------------------------------------------------
    # Internal: tools/call
    # ------------------------------------------------------------------

    def _handle_tools_call(
        self,
        request_id: Any,
        params: dict[str, Any],
        *,
        db: Any,
        user_id: int,
        allowed_scopes: frozenset[str],
        daily_limit: int | None,
    ) -> dict[str, Any]:
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
        # Fail-CLOSED: reject if the tool has no scope mapping. Never
        # default to a permissive scope -- that would auto-grant newly
        # added tools to every tier.
        required_scope = self._scope_map.get(name)
        if required_scope is None:
            logger.warning(
                "MCP tool %r has no required-scope entry; rejecting tools/call",
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
        if (
            daily_limit is not None
            and self._quota is not None
            and not self._quota.consume(user_id=user_id, limit=daily_limit)
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
        # session -- the transport injects those from the authenticated
        # MCP context.
        for reserved in arguments.keys() & self._reserved:
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


__all__ = [
    "ERR_INTERNAL",
    "ERR_INVALID_PARAMS",
    "ERR_INVALID_REQUEST",
    "ERR_METHOD_NOT_FOUND",
    "ERR_PARSE",
    "JSONRPC_VERSION",
    "RESERVED_ARG_NAMES",
    "MCPServer",
    "ToolHandler",
]
