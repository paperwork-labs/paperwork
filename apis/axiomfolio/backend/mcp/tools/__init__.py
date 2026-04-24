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

TOOL_REQUIRED_SCOPE = {
    "get_holdings": "mcp.read_portfolio",
    "get_recent_trades": "mcp.read_portfolio",
    "get_dividend_summary": "mcp.read_portfolio",
    "get_stage_summary": "mcp.read_signals",
    "get_recent_explanations": "mcp.read_trade_cards",
    "get_pick_history": "mcp.read_signals",
}

__all__ = [
    "TOOL_DEFINITIONS",
    "TOOL_HANDLERS",
    "TOOL_REQUIRED_SCOPE",
    "get_dividend_summary",
    "get_holdings",
    "get_pick_history",
    "get_recent_explanations",
    "get_recent_trades",
    "get_stage_summary",
]
