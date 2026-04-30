"""Brain MCP Server — exposes all Brain tools via Model Context Protocol.

Mounted inside the FastAPI app at /mcp. Anthropic and OpenAI connect here
to discover and execute tools server-side (no client-side dispatch loop).

Tool implementations live in app/tools/. This module registers them as
FastMCP tools and configures the server.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.applications import Starlette

from fastmcp import FastMCP

from app.tools.axiomfolio import (
    approve_trade,
    execute_trade,
    get_market_regime,
    get_portfolio,
    get_risk_status,
    preview_trade,
    reject_trade,
    scan_market,
    stage_analysis,
)
from app.tools.github import (
    commit_github_file,
    create_github_issue,
    get_github_pr,
    get_github_pr_diff,
    list_github_prs,
    merge_github_pr,
    read_github_file,
    review_github_pr,
    search_github_code,
)
from app.tools.infra import (
    check_neon_status,
    check_render_status,
    check_upstash_status,
    check_vercel_status,
)
from app.tools.memory_tools import search_memory
from app.tools.vault import vault_get, vault_list, vault_set

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
mcp.tool(name="get_github_pr", description="Get details of a specific pull request.")(get_github_pr)
mcp.tool(
    name="get_github_pr_diff",
    description="Fetch the unified diff for a PR (capped at 60k chars).",
)(get_github_pr_diff)
mcp.tool(
    name="review_github_pr",
    description=(
        "Post a review on a PR (Tier 2: write action). "
        "event: COMMENT | APPROVE | REQUEST_CHANGES. "
        "Optional inline comments: list of {path, line, body}."
    ),
)(review_github_pr)
mcp.tool(name="create_github_issue", description="Create a new issue on the repository.")(
    create_github_issue
)
mcp.tool(
    name="commit_github_file",
    description="Create or update a file in the repository (Tier 2: write action).",
)(commit_github_file)
mcp.tool(
    name="merge_github_pr",
    description="Merge a pull request (Tier 2: write action).",
)(merge_github_pr)


# -- Brain PR reviewer (2) -----------------------------------------------------
# These wrap the full pipeline (fetch metadata + diff + memory context, call
# Claude, post review, persist episode) so Brain's agent loop can invoke them
# directly. No external webhook/cron is needed — Brain drives itself.


async def _brain_review_pr_wrapper(pr_number: int, organization_id: str = "paperwork-labs") -> str:
    """Run Brain's full PR review pipeline on one PR (fetch, analyze, post, remember)."""
    from app.database import async_session_factory
    from app.services.pr_review import review_pr

    async with async_session_factory() as session:
        result = await review_pr(session, pr_number=pr_number, org_id=organization_id)
    if result.get("posted"):
        return (
            f"Reviewed PR #{pr_number}: {result.get('verdict')} "
            f"(model={result.get('model')}). {result.get('summary', '')[:400]}"
        )
    return (
        f"PR #{pr_number} review did not post: {result.get('error') or result.get('review_result')}"
    )


async def _brain_sweep_open_prs_wrapper(
    limit: int = 30,
    organization_id: str = "paperwork-labs",
    force: bool = False,
) -> str:
    """Review every open non-bot PR Brain hasn't reviewed at its current head SHA.

    Uses memory (episodes) to skip PRs already reviewed at the same SHA — so
    calling this repeatedly is cheap: it only spends tokens on genuinely-new work.
    """
    from app.database import async_session_factory
    from app.services.pr_review import sweep_open_prs

    async with async_session_factory() as session:
        report = await sweep_open_prs(session, org_id=organization_id, limit=limit, force=force)
    reviewed = report.get("reviewed") or []
    skipped = report.get("skipped") or []
    errors = report.get("errors") or []
    lines = [
        f"Scanned: {report.get('scanned', 0)}",
        f"Reviewed: {len(reviewed)}",
    ]
    for r in reviewed[:10]:
        lines.append(f"  #{r.get('number')}: {r.get('verdict')}")
    if skipped:
        lines.append(f"Skipped: {len(skipped)}")
        for s in skipped[:8]:
            lines.append(f"  #{s.get('number')}: {s.get('reason')}")
    if errors:
        lines.append(f"Errors: {len(errors)}")
        for e in errors[:5]:
            lines.append(f"  #{e.get('number')}: {e.get('error')}")
    return "\n".join(lines)


mcp.tool(
    name="brain_review_pr",
    description=(
        "Brain's executive PR reviewer: fetches PR metadata + diff, pulls "
        "historical context from memory, calls Claude, posts a structured "
        "review on GitHub, and stores the episode. Tier 2: write action."
    ),
)(_brain_review_pr_wrapper)
mcp.tool(
    name="brain_sweep_open_prs",
    description=(
        "Review every open non-bot PR Brain hasn't already reviewed at its "
        "current head SHA. Skips Dependabot/Renovate/GH-Actions PRs and any PR "
        "labeled skip-brain-review / deps:major / dependencies / do-not-merge. "
        "Idempotent: memory (episodes) tracks reviewed PRs."
    ),
)(_brain_sweep_open_prs_wrapper)

# -- Infrastructure health tools (5) ------------------------------------------

mcp.tool(name="check_render_status", description="Check health of all Render services.")(
    check_render_status
)
mcp.tool(name="check_vercel_status", description="Check recent Vercel deployment status.")(
    check_vercel_status
)
mcp.tool(name="check_neon_status", description="Check Neon PostgreSQL database status.")(
    check_neon_status
)
mcp.tool(name="check_upstash_status", description="Check Upstash Redis status.")(
    check_upstash_status
)

# -- AxiomFolio trading tools (8) ----------------------------------------------

mcp.tool(name="scan_market", description="Run market scans for trading candidates (Tier 0).")(
    scan_market
)
mcp.tool(name="get_portfolio", description="Get current portfolio positions and P&L (Tier 0).")(
    get_portfolio
)
mcp.tool(
    name="stage_analysis",
    description="Get technical stage analysis for a stock symbol (Tier 0).",
)(stage_analysis)
mcp.tool(
    name="get_risk_status", description="Get circuit breaker status and risk metrics (Tier 0)."
)(get_risk_status)
mcp.tool(name="get_market_regime", description="Get current market regime R1-R5 (Tier 0).")(
    get_market_regime
)
mcp.tool(
    name="preview_trade",
    description="Create a PREVIEW trade order for approval (Tier 2). Returns order_id.",
)(preview_trade)
mcp.tool(
    name="approve_trade",
    description="Approve a pending trade order by order_id (Tier 3).",
)(approve_trade)
mcp.tool(
    name="reject_trade",
    description="Reject a pending trade order by order_id (Tier 3).",
)(reject_trade)
mcp.tool(
    name="execute_trade",
    description="Execute an approved trade order by order_id (Tier 3: REAL trade).",
)(execute_trade)

# -- Memory tools (1) ----------------------------------------------------------

mcp.tool(
    name="search_memory",
    description="Search Brain's episodic memory for relevant past conversations and knowledge.",
)(search_memory)

# -- Vault tools (3) -----------------------------------------------------------


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


async def _vault_set_wrapper(name: str, value: str, service: str) -> str:
    """Store or update a secret in the vault (Tier 2: write action)."""
    result = await vault_set(name, value, service)
    if result.success:
        return f"Secret '{name}' saved to vault."
    return f"Vault error: {result.error}"


mcp.tool(
    name="vault_set",
    description="Store or update a secret in the vault (Tier 2: write action).",
)(_vault_set_wrapper)


def create_mcp_app() -> Starlette:
    """Create the ASGI app for mounting in FastAPI."""
    return mcp.http_app(path="/")
