"""Shared MCP (Model Context Protocol) transport for Paperwork Labs.

A tiny, audit-friendly JSON-RPC 2.0 dispatcher with bearer-token auth
and per-user daily quota. Every product backend (AxiomFolio, FileFree,
LaunchFree) wires this into its own ``/api/v1/mcp/jsonrpc`` route, plugs
in a backend-specific token model + tier resolver via
:class:`MCPAuthBuilder`, and registers its tool catalog with
:class:`MCPServer`.

Public surface (re-exported here so consumers never have to import a
private submodule path):

* Dispatcher: :class:`MCPServer`, :data:`RESERVED_ARG_NAMES`,
  :data:`JSONRPC_VERSION`, the JSON-RPC error codes
  ``ERR_PARSE / ERR_INVALID_REQUEST / ERR_METHOD_NOT_FOUND /
  ERR_INVALID_PARAMS / ERR_INTERNAL``.
* Auth: :class:`MCPAuthBuilder`, :class:`MCPAuthContext`,
  :func:`generate_token`, :func:`hash_token`,
  :func:`split_credential` (legacy alias :func:`_split_credential`).
* Quota: :class:`DailyCallQuota`, :func:`make_module_level_quota`.
* FastAPI: :data:`mcp_bearer` -- the shared ``HTTPBearer`` scheme.

See ``packages/python/mcp-server/README.md`` for the integration
example backends should follow.
"""

from .auth import (
    DEFAULT_TOKEN_RANDOM_BYTES,
    MCPAuthBuilder,
    MCPAuthContext,
    _split_credential,
    generate_token,
    hash_token,
    split_credential,
)
from .bearer import mcp_bearer
from .dispatcher import (
    ERR_INTERNAL,
    ERR_INVALID_PARAMS,
    ERR_INVALID_REQUEST,
    ERR_METHOD_NOT_FOUND,
    ERR_PARSE,
    JSONRPC_VERSION,
    RESERVED_ARG_NAMES,
    MCPServer,
)
from .quota import DailyCallQuota, make_module_level_quota

__all__ = [
    "DEFAULT_TOKEN_RANDOM_BYTES",
    "ERR_INTERNAL",
    "ERR_INVALID_PARAMS",
    "ERR_INVALID_REQUEST",
    "ERR_METHOD_NOT_FOUND",
    "ERR_PARSE",
    "JSONRPC_VERSION",
    "RESERVED_ARG_NAMES",
    "DailyCallQuota",
    "MCPAuthBuilder",
    "MCPAuthContext",
    "MCPServer",
    "_split_credential",
    "generate_token",
    "hash_token",
    "make_module_level_quota",
    "mcp_bearer",
    "split_credential",
]
