"""Read-only MCP tool implementations.

Importing this module gives you :data:`TOOL_DEFINITIONS` (JSON-Schema
catalog for ``tools/list``) and :data:`TOOL_HANDLERS` (callable map for
``tools/call``). Both are derived from :mod:`backend.mcp.tools.portfolio`.
"""

from backend.mcp.tools.portfolio import (
    TOOL_DEFINITIONS,
    TOOL_HANDLERS,
    get_dividend_summary,
    get_holdings,
    get_pick_history,
    get_recent_explanations,
    get_recent_trades,
    get_stage_summary,
)

__all__ = [
    "TOOL_DEFINITIONS",
    "TOOL_HANDLERS",
    "get_dividend_summary",
    "get_holdings",
    "get_pick_history",
    "get_recent_explanations",
    "get_recent_trades",
    "get_stage_summary",
]
