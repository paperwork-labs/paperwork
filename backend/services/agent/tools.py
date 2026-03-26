"""
Agent Tools
===========

Defines available tools/actions for the auto-ops agent.
Each tool maps to a Celery task or service method.
"""

from typing import Any, Dict, List, Optional

AGENT_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_health",
            "description": "Check the composite health status of all system dimensions (coverage, stage_quality, jobs, audit, regime). Returns current status and any issues.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Run a read-only SQL query against the database to investigate issues. Only SELECT queries allowed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL SELECT query to run",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum rows to return (default 100)",
                        "default": 100,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information about errors, market conditions, or technical documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_url",
            "description": "Fetch and read content from a specific URL (e.g., documentation, status pages).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_alert",
            "description": "Send an alert notification via Discord webhook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The alert message to send",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["info", "warning", "error", "critical"],
                        "description": "Alert severity level",
                    },
                },
                "required": ["message", "severity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_jobs",
            "description": "List recent job runs with their status and results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["all", "running", "failed", "completed"],
                        "description": "Filter by job status",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum jobs to return",
                        "default": 20,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "backfill_stale_daily",
            "description": "Backfill stale daily price data for tracked symbols that are missing recent bars.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recompute_indicators",
            "description": "Recompute technical indicators (stage, RS, TD Sequential) for the tracked universe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "batch_size": {
                        "type": "integer",
                        "description": "Number of symbols to process per batch",
                        "default": 50,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_daily",
            "description": "Record today's market snapshot history for all symbols.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_regime",
            "description": "Compute the current market regime (R1-R5) based on VIX, breadth, and sector data.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "monitor_coverage",
            "description": "Check coverage health and identify symbols with missing or stale data.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recover_stale_jobs",
            "description": "Find and recover jobs that have been running too long (likely stuck).",
            "parameters": {
                "type": "object",
                "properties": {
                    "stale_minutes": {
                        "type": "integer",
                        "description": "Consider jobs stale after this many minutes",
                        "default": 120,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bootstrap_coverage",
            "description": "Bootstrap daily coverage data for tracked symbols with recent history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_days": {
                        "type": "integer",
                        "description": "Number of days of history to bootstrap",
                        "default": 5,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refresh_index_constituents",
            "description": "Refresh the list of index constituents (S&P 500, NASDAQ-100, Russell 2000).",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "string",
                        "enum": ["SP500", "NASDAQ100", "RUSSELL2000", "all"],
                        "description": "Which index to refresh",
                    },
                },
                "required": ["index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_broker_connection",
            "description": "Check the connection status of broker integrations (IBKR, TastyTrade, Schwab).",
            "parameters": {
                "type": "object",
                "properties": {
                    "broker": {
                        "type": "string",
                        "enum": ["ibkr", "tastytrade", "schwab", "all"],
                        "description": "Which broker to check",
                    },
                },
                "required": [],
            },
        },
    },
]


TOOL_TO_CELERY_TASK: Dict[str, str] = {
    "backfill_stale_daily": "backend.tasks.market.backfill.stale_daily",
    "recompute_indicators": "backend.tasks.market.indicators.recompute_universe",
    "record_daily": "backend.tasks.market.history.record_daily",
    "compute_regime": "backend.tasks.market.regime.compute_daily",
    "monitor_coverage": "backend.tasks.market.coverage.health_check",
    "recover_stale_jobs": "backend.tasks.market.maintenance.recover_jobs",
    "bootstrap_coverage": "backend.tasks.market.coverage.daily_bootstrap",
    "refresh_index_constituents": "backend.tasks.market.backfill.constituents",
}


def get_tools_for_openai() -> List[Dict[str, Any]]:
    """Return tools formatted for OpenAI function calling."""
    return AGENT_TOOLS
