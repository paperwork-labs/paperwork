"""Shared FastAPI ``HTTPBearer`` instance for the MCP transport.

Exposed as a module-level singleton so the OpenAPI schema lists exactly
one ``MCPBearer`` security scheme regardless of how many product
backends mount the MCP routes. ``auto_error=False`` lets the auth
dependency translate a missing header into a uniform ``401 Invalid MCP
token`` error -- callers must never be able to distinguish "missing
token" from "wrong token" via timing or message text.
"""

from __future__ import annotations

from fastapi.security import HTTPBearer

mcp_bearer = HTTPBearer(auto_error=False, scheme_name="MCPBearer")

__all__ = ["mcp_bearer"]
