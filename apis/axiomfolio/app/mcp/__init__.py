"""MCP (Model Context Protocol) server for AxiomFolio.

Exposes a small read-only catalog of portfolio tools to external MCP
clients (ChatGPT, Claude, Cursor, etc.) over a JSON-RPC 2.0 transport
authenticated with per-user bearer tokens.

Public surface:
* :class:`MCPServer` — JSON-RPC dispatcher
* :func:`build_default_server` — server wired to the production tool catalog
"""

from app.mcp.server import MCPServer, build_default_server

__all__ = ["MCPServer", "build_default_server"]
