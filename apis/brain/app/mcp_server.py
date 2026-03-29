"""Brain MCP Server — exposes all Brain tools via Model Context Protocol.

Mounted inside the FastAPI app at /mcp. Anthropic and OpenAI connect here
to discover and execute tools server-side (no client-side dispatch loop).

Tool implementations live in app/tools/. This module registers them as
FastMCP tools and configures the server.
"""

import logging

from fastmcp import FastMCP

from app.tools.axiomfolio import (
    execute_trade,
    get_portfolio,
    get_risk_status,
    get_watchlist,
    modify_position,
    scan_market,
    stage_analysis,
)
from app.tools.github import (
    commit_github_file,
    create_github_issue,
    get_github_pr,
    list_github_prs,
    merge_github_pr,
    read_github_file,
    search_github_code,
)
from app.tools.infra import (
    activate_n8n_workflow,
    check_n8n_status,
    check_neon_status,
    check_render_status,
    check_upstash_status,
    check_vercel_status,
    import_n8n_workflow,
    list_n8n_workflows,
)
from app.tools.memory_tools import search_memory
from app.tools.vault import vault_get, vault_list

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="brain-tools",
    instructions=(
        "Brain tools for Paperwork Labs. Includes GitHub repo access, "
        "infrastructure health checks, AxiomFolio trading, episodic memory, "
        "and secret vault. Use search_memory to recall past conversations."
    ),
)

# -- GitHub tools (7) ----------------------------------------------------------

mcp.tool(name="read_github_file", description="Read a file from the GitHub repository.")(
    read_github_file
)
mcp.tool(name="search_github_code", description="Search code in the GitHub repository.")(
    search_github_code
)
mcp.tool(name="list_github_prs", description="List pull requests on the repository.")(
    list_github_prs
)
mcp.tool(name="get_github_pr", description="Get details of a specific pull request.")(
    get_github_pr
)
mcp.tool(
    name="create_github_issue", description="Create a new issue on the repository."
)(create_github_issue)
mcp.tool(
    name="commit_github_file",
    description="Create or update a file in the repository (Tier 2: write action).",
)(commit_github_file)
mcp.tool(
    name="merge_github_pr",
    description="Merge a pull request (Tier 2: write action).",
)(merge_github_pr)

# -- Infrastructure health tools (5) ------------------------------------------

mcp.tool(name="check_render_status", description="Check health of all Render services.")(
    check_render_status
)
mcp.tool(
    name="check_vercel_status", description="Check recent Vercel deployment status."
)(check_vercel_status)
mcp.tool(name="check_neon_status", description="Check Neon PostgreSQL database status.")(
    check_neon_status
)
mcp.tool(name="check_n8n_status", description="Check n8n workflow automation status.")(
    check_n8n_status
)
mcp.tool(name="check_upstash_status", description="Check Upstash Redis status.")(
    check_upstash_status
)
mcp.tool(
    name="list_n8n_workflows",
    description="List all n8n workflows with their active/inactive status.",
)(list_n8n_workflows)
mcp.tool(
    name="activate_n8n_workflow",
    description="Activate or deactivate an n8n workflow by ID (Tier 1: auto with notification).",
)(activate_n8n_workflow)
mcp.tool(
    name="import_n8n_workflow",
    description="Import a new workflow into n8n from JSON (Tier 2: draft action).",
)(import_n8n_workflow)

# -- AxiomFolio trading tools (7) ----------------------------------------------

mcp.tool(name="scan_market", description="Run market scans for trading candidates.")(
    scan_market
)
mcp.tool(
    name="get_portfolio", description="Get current portfolio positions and P&L."
)(get_portfolio)
mcp.tool(
    name="stage_analysis",
    description="Get technical stage analysis for a stock symbol.",
)(stage_analysis)
mcp.tool(
    name="get_risk_status", description="Get current portfolio risk metrics and gates."
)(get_risk_status)
mcp.tool(name="get_watchlist", description="Get tracked symbols and price alerts.")(
    get_watchlist
)
mcp.tool(
    name="execute_trade",
    description="Execute a trade order (Tier 3: requires explicit approval).",
)(execute_trade)
mcp.tool(
    name="modify_position",
    description="Modify stop-loss or take-profit on a position (Tier 2: draft action).",
)(modify_position)

# -- Memory tools (1) ----------------------------------------------------------

mcp.tool(
    name="search_memory",
    description="Search Brain's episodic memory for relevant past conversations and knowledge.",
)(search_memory)

# -- Vault tools (2) -----------------------------------------------------------


async def _vault_list_wrapper() -> str:
    """List available secret names (no values shown)."""
    result = await vault_list()
    if result.success:
        return f"Available secrets: {result.value}"
    return f"Vault error: {result.error}"


async def _vault_get_wrapper(name: str) -> str:
    """Retrieve a secret value by name. Value is used by Brain internally only."""
    result = await vault_get(name)
    if result.success:
        return f"Secret '{name}' retrieved successfully (value available to Brain)."
    return f"Vault error: {result.error}"


mcp.tool(name="vault_list", description="List available secret names in the vault.")(
    _vault_list_wrapper
)
mcp.tool(
    name="vault_get",
    description="Retrieve a secret from the vault (Tier 1: value not exposed in responses).",
)(_vault_get_wrapper)


def create_mcp_app():
    """Create the ASGI app for mounting in FastAPI."""
    return mcp.http_app(path="/")
