"""Unit tests for :class:`mcp_server.dispatcher.MCPServer`.

Covers the full JSON-RPC envelope contract and every error path: bad
input shape, unknown method, unknown tool, scope gating (fail-CLOSED),
reserved arg blocking, quota enforcement, and handler exception
translation. AxiomFolio's higher-level integration tests in
``apis/axiomfolio/app/tests/mcp/test_tools.py`` cover the FastAPI route
+ DB layer; this file covers the pure-Python dispatcher in isolation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from mcp_server import (
    ERR_INTERNAL,
    ERR_INVALID_PARAMS,
    ERR_INVALID_REQUEST,
    ERR_METHOD_NOT_FOUND,
    DailyCallQuota,
    MCPServer,
)

# ----------------------------------------------------------------------
# Builders
# ----------------------------------------------------------------------


def _make_server(
    *,
    extra_tools: dict[str, Any] | None = None,
    extra_scopes: dict[str, str] | None = None,
    quota: DailyCallQuota | None = None,
) -> MCPServer:
    """Return a small MCPServer with a couple of canned tools."""

    def echo(*, db, user_id, message="hi"):
        return {"echo": message, "user_id": user_id}

    def boom(*, db, user_id):
        raise RuntimeError("intentional failure")

    def reject(*, db, user_id, n: int = 0):
        if n < 0:
            raise ValueError("n must be non-negative")
        return {"n": n}

    handlers = {"echo": echo, "boom": boom, "reject": reject}
    handlers.update(extra_tools or {})

    definitions = [
        {"name": "echo", "description": "Echo a message"},
        {"name": "boom", "description": "Always raises"},
        {"name": "reject", "description": "Validates input"},
    ]
    for name in (extra_tools or {}).keys():
        definitions.append({"name": name, "description": f"extra: {name}"})

    scopes = {
        "echo": "mcp.read",
        "boom": "mcp.read",
        "reject": "mcp.read",
    }
    scopes.update(extra_scopes or {})

    return MCPServer(
        definitions, handlers, scopes, quota=quota
    )


# ----------------------------------------------------------------------
# Envelope shape
# ----------------------------------------------------------------------


class TestEnvelope:
    def test_non_dict_payload_returns_invalid_request(self):
        srv = _make_server()
        out = srv.handle(
            "not a dict",
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INVALID_REQUEST
        assert out["id"] is None

    def test_wrong_jsonrpc_version_returns_invalid_request(self):
        srv = _make_server()
        out = srv.handle(
            {"jsonrpc": "1.0", "id": 7, "method": "tools/list"},
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INVALID_REQUEST
        assert out["id"] == 7

    def test_missing_method_returns_invalid_request(self):
        srv = _make_server()
        out = srv.handle(
            {"jsonrpc": "2.0", "id": 1},
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INVALID_REQUEST

    def test_unknown_method_returns_method_not_found(self):
        srv = _make_server()
        out = srv.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "frobnicate"},
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_METHOD_NOT_FOUND
        assert "tools/list" in out["error"]["data"]["supported"]

    def test_params_not_object_returns_invalid_params(self):
        # ``[1, 2]`` is truthy and non-dict, so it survives the
        # ``params or {}`` defaulting and trips the type check.
        # An empty list ``[]`` is intentionally tolerated (collapses
        # to ``{}``) -- preserved from AxiomFolio's pre-extraction
        # behavior.
        srv = _make_server()
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": [1, 2],
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INVALID_PARAMS


# ----------------------------------------------------------------------
# tools/list -- fail-CLOSED scope gating
# ----------------------------------------------------------------------


class TestToolsList:
    def test_only_in_scope_tools_visible(self):
        srv = _make_server()
        out = srv.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        names = {t["name"] for t in out["result"]["tools"]}
        assert names == {"echo", "boom", "reject"}

    def test_no_scopes_means_no_tools(self):
        srv = _make_server()
        out = srv.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset(),
            daily_limit=None,
        )
        assert out["result"]["tools"] == []

    def test_unmapped_tool_hidden_fail_closed(self):
        """Tool registered in handlers but missing from scope map stays hidden.

        This is the critical fail-CLOSED guarantee: adding a new tool
        without an explicit scope mapping never auto-grants it to any
        tier. Same regression coverage AxiomFolio relies on.
        """
        srv = MCPServer(
            tool_definitions=[
                {"name": "echo", "description": "Echo"},
                {"name": "secret", "description": "No scope mapping"},
            ],
            tool_handlers={
                "echo": lambda *, db, user_id: {"ok": True},
                "secret": lambda *, db, user_id: {"leaked": "data"},
            },
            tool_required_scope={"echo": "mcp.read"},
        )
        out = srv.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read", "*"}),
            daily_limit=None,
        )
        names = {t["name"] for t in out["result"]["tools"]}
        assert names == {"echo"}


# ----------------------------------------------------------------------
# tools/call -- happy path + error paths
# ----------------------------------------------------------------------


class TestToolsCall:
    def test_handler_invoked_with_db_and_user_id(self):
        srv = _make_server()
        db = MagicMock()
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"message": "yo"}},
            },
            db=db,
            user_id=42,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["result"]["content"] == {"echo": "yo", "user_id": 42}

    def test_missing_name(self):
        srv = _make_server()
        out = srv.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}},
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INVALID_PARAMS

    def test_unknown_tool(self):
        srv = _make_server()
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "nope"},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_METHOD_NOT_FOUND

    def test_scope_gate_blocks_call(self):
        srv = _make_server()
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {}},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset(),
            daily_limit=None,
        )
        # Scope gate uses -32601 (method not available) per AxiomFolio
        # convention -- callers can't tell "exists but not for me" from
        # "doesn't exist".
        assert out["error"]["code"] == ERR_METHOD_NOT_FOUND

    def test_unmapped_tool_call_fails_closed(self):
        """tools/call on a handler with no scope entry is rejected."""
        srv = MCPServer(
            tool_definitions=[{"name": "secret", "description": "?"}],
            tool_handlers={"secret": lambda *, db, user_id: {"ok": True}},
            tool_required_scope={},
        )
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "secret", "arguments": {}},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"*"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_METHOD_NOT_FOUND
        assert "not registered" in out["error"]["message"]

    def test_reserved_user_id_argument_rejected(self):
        srv = _make_server()
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "echo",
                    "arguments": {"user_id": 999},
                },
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INVALID_PARAMS
        assert "user_id" in out["error"]["message"]

    def test_reserved_db_argument_rejected(self):
        srv = _make_server()
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"db": object()}},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INVALID_PARAMS

    def test_unknown_argument_rejected(self):
        srv = _make_server()
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"bogus": 1}},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INVALID_PARAMS

    def test_handler_value_error_is_invalid_params(self):
        srv = _make_server()
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "reject", "arguments": {"n": -1}},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INVALID_PARAMS
        assert "non-negative" in out["error"]["message"]

    def test_handler_unexpected_exception_is_internal(self):
        srv = _make_server()
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "boom"},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INTERNAL
        # Detail must be generic so we don't leak internals.
        assert out["error"]["message"] == "Tool execution failed"

    def test_arguments_must_be_object(self):
        srv = _make_server()
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": [1, 2]},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert out["error"]["code"] == ERR_INVALID_PARAMS


# ----------------------------------------------------------------------
# Quota integration
# ----------------------------------------------------------------------


class TestQuotaIntegration:
    def test_no_quota_no_check(self):
        srv = _make_server(quota=None)
        # A non-None daily_limit but no quota object -> no rate-limiting.
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "echo"},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=10,
        )
        assert out["result"]["content"]["echo"] == "hi"

    def test_quota_enforced(self, fake_redis_factory):
        quota = DailyCallQuota(fake_redis_factory)
        srv = _make_server(quota=quota)
        for _ in range(2):
            out = srv.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "echo"},
                },
                db=MagicMock(),
                user_id=1,
                allowed_scopes=frozenset({"mcp.read"}),
                daily_limit=2,
            )
            assert "result" in out
        # 3rd call exceeds limit
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 99,
                "method": "tools/call",
                "params": {"name": "echo"},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=2,
        )
        assert out["error"]["code"] == ERR_INVALID_REQUEST
        assert "Daily MCP call limit" in out["error"]["message"]

    def test_daily_limit_none_skips_quota(self, fake_redis_factory):
        """daily_limit=None means unlimited; quota.consume must NOT be called."""
        called = []
        bad_quota = DailyCallQuota(fake_redis_factory)

        original = bad_quota.consume

        def trace(**kwargs):
            called.append(kwargs)
            return original(**kwargs)

        bad_quota.consume = trace  # type: ignore[method-assign]

        srv = _make_server(quota=bad_quota)
        out = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "echo"},
            },
            db=MagicMock(),
            user_id=1,
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=None,
        )
        assert "result" in out
        assert called == []
