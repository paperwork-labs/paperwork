"""
Agent Tools
===========

Defines available tools/actions for the auto-ops agent.
Each tool maps to a Celery task or service method.
"""

from typing import Any, Dict, FrozenSet, List, Optional

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
            "description": "Send an alert notification via Brain webhook.",
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
    # ==================== HOLISTIC CHAT TOOLS ====================
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_summary",
            "description": "Get portfolio summary including risk metrics, sector allocation, P&L, and account balances for the admin user.",
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
            "name": "get_position_details",
            "description": "Get detailed information about a specific position including current price, P&L, and market snapshot (stage, indicators).",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The stock symbol (e.g., AAPL, NVDA)",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_activity",
            "description": "Get recent portfolio activity including trades, optionally filtered by symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of activities to return",
                        "default": 20,
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Filter by symbol (optional)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_snapshot",
            "description": "Get the current market snapshot for a symbol including stage, indicators (RSI, MACD, MAs), RS rank, and sector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The stock symbol (e.g., AAPL, NVDA, SPY)",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tracked_universe",
            "description": "Get the tracked universe of symbols showing total count, breakdown by source (index membership, holdings), and a sample.",
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
            "name": "get_constituents",
            "description": "Get the list of symbols in a specific index (S&P 500, NASDAQ-100, or Russell 2000).",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "string",
                        "enum": ["SP500", "NASDAQ100", "RUSSELL2000"],
                        "description": "Which index to get constituents for",
                    },
                },
                "required": ["index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_regime",
            "description": "Get the current market regime (R1-R5) with all inputs (VIX, breadth, sectors) and portfolio rules.",
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
            "name": "describe_tables",
            "description": "List database tables or describe columns for a specific table. Use this before query_database to understand the schema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Table name to describe (optional - omit to list all tables)",
                    },
                },
                "required": [],
            },
        },
    },
    # ==================== MARKET INSIGHT TOOLS ====================
    {
        "type": "function",
        "function": {
            "name": "get_stage_distribution",
            "description": "Get distribution of stocks by stage (1A-4C) across the tracked universe. Shows market breadth and % bullish/bearish.",
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
            "name": "get_sector_strength",
            "description": "Rank sectors by % of stocks in constructive stages (2A/2B/2C). Shows sector rotation leaders and laggards.",
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
            "name": "get_top_scans",
            "description": "Get top stocks passing scan overlay filters. Returns actionable trade ideas ranked by relative strength.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scan_tier": {
                        "type": "string",
                        "description": "Scan tier to filter by (e.g., 'Breakout Elite', 'Breakout Standard', 'Breakdown Elite')",
                        "default": "Breakout Elite",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum stocks to return",
                        "default": 10,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_exit_alerts",
            "description": "Get positions that may need attention based on stage deterioration (3A/3B/4A/4B/4C stages).",
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
            "name": "get_regime_history",
            "description": "Get regime changes over specified period. Shows current regime, transitions, and volatility assessment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days of history to retrieve",
                        "default": 30,
                    },
                },
                "required": [],
            },
        },
    },
    # ==================== MARKET CONTEXT TOOLS ====================
    {
        "type": "function",
        "function": {
            "name": "get_rotation_analysis",
            "description": "Analyze sector rotation by comparing sector performance over 5, 20, and 60 day windows. Shows money flow leaders/laggards.",
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
            "name": "get_breadth_momentum",
            "description": "Get market breadth indicators: % above 200D/50D SMA, new highs vs new lows trend, advancing/declining analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Days of history for trend analysis",
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
            "name": "compare_historical_regime",
            "description": "Find historical periods with similar market regime characteristics. Useful for understanding what happened next in similar conditions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lookback_years": {
                        "type": "integer",
                        "description": "Years of history to search",
                        "default": 2,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_internals",
            "description": "Get VIX analysis (spot, term structure via VIX3M ratio, VVIX), breadth percentages, and overall volatility assessment.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    # ==================== RESEARCH & STRATEGY TOOLS ====================
    {
        "type": "function",
        "function": {
            "name": "backtest_scan",
            "description": "Get historical win rate and average return for a scan tier. Shows how Breakout Elite/Standard picks have performed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scan_tier": {
                        "type": "string",
                        "description": "Scan tier to analyze (e.g., 'Breakout Elite', 'Breakout Standard', 'Breakdown Elite')",
                        "default": "Breakout Elite",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Days of historical data to analyze",
                        "default": 90,
                    },
                    "holding_period": {
                        "type": "integer",
                        "description": "Forward return window in days (5, 10, 20, 60)",
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
            "name": "get_similar_setups",
            "description": "Find stocks with similar technical setups: matching stage, RS rank, and pattern characteristics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Reference symbol to find similar setups for",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return",
                        "default": 10,
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_strategy_stats",
            "description": "Get performance statistics for saved strategies: win rate, avg return, Sharpe, max drawdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_id": {
                        "type": "integer",
                        "description": "Strategy ID (optional - omit to list all strategies with summary stats)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_historical_entry",
            "description": "Analyze how stocks entering a specific stage performed under given regime. E.g., 'How did Stage 2A entries perform in R3?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage": {
                        "type": "string",
                        "description": "Stage label (e.g., '2A', '2B', '1B')",
                    },
                    "regime": {
                        "type": "string",
                        "description": "Regime state (R1, R2, R3, R4, R5)",
                        "default": "R3",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Days of history to analyze",
                        "default": 180,
                    },
                },
                "required": ["stage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_strategies",
            "description": "List all saved strategies with their status and basic info.",
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
            "name": "run_backtest",
            "description": "Run a backtest for a strategy over specified date range. Returns performance metrics and trade list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_id": {
                        "type": "integer",
                        "description": "Strategy ID to backtest",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date (YYYY-MM-DD)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (YYYY-MM-DD)",
                    },
                    "initial_capital": {
                        "type": "number",
                        "description": "Starting capital",
                        "default": 100000,
                    },
                },
                "required": ["strategy_id", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_strategy_templates",
            "description": "List available strategy templates (breakout, pullback, momentum, etc.) that can be used as starting points.",
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
            "name": "create_strategy",
            "description": "Create a new strategy from a template or custom rules. Use after discussing strategy goals with user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Strategy name (unique, descriptive)",
                    },
                    "template_id": {
                        "type": "string",
                        "description": "Template ID to base strategy on (use list_strategy_templates to see options)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Strategy description",
                    },
                    "overrides": {
                        "type": "object",
                        "description": "Optional overrides to template defaults (e.g., entry stages, RS threshold)",
                    },
                },
                "required": ["name", "template_id"],
            },
        },
    },
    # ==================== CODEBASE EXPLORATION TOOLS ====================
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the backend codebase to understand implementation details. Use this to answer questions about how things work.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to backend/ (e.g., 'services/market/indicator_engine.py')",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Start line number (1-indexed, optional)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "End line number (optional)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in a path of the backend codebase. Use this to explore the code structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to backend/ (e.g., 'services/market/')",
                        "default": "",
                    },
                },
                "required": [],
            },
        },
    },
]


# Implemented in AgentBrain._execute_safe_tool — never dispatched to Celery.
INLINE_ONLY_AGENT_TOOLS: FrozenSet[str] = frozenset({
    "read_file",
    "list_files",
    "get_stage_distribution",
    "get_sector_strength",
    "get_top_scans",
    "get_exit_alerts",
    "get_regime_history",
    # Market Context tools
    "get_rotation_analysis",
    "get_breadth_momentum",
    "compare_historical_regime",
    "get_market_internals",
    # Research & Strategy tools
    "backtest_scan",
    "get_similar_setups",
    "get_strategy_stats",
    "analyze_historical_entry",
    "list_strategies",
    "run_backtest",
    "list_strategy_templates",
    "create_strategy",
})

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
