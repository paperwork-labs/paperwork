"""
Shared utilities for market routes.
"""

import json
import logging
from typing import List, Dict, Any, Callable

from app.api.dependencies import market_visibility_scope, market_exposed_to_all
from app.services.silver.math.constants import (
    SNAPSHOT_PREFERRED_COLUMNS,
    SNAPSHOTS_PREFERRED_COLUMNS,
    SNAPSHOT_HISTORY_PREFERRED_COLUMNS,
)

logger = logging.getLogger(__name__)


def visibility_scope() -> str:
    return market_visibility_scope()


def snapshot_preferred_columns(kind: str) -> list[str]:
    if kind == "single":
        return list(SNAPSHOT_PREFERRED_COLUMNS)
    if kind == "list":
        return list(SNAPSHOTS_PREFERRED_COLUMNS)
    if kind == "history":
        return list(SNAPSHOT_HISTORY_PREFERRED_COLUMNS)
    raise ValueError(f"Unknown snapshot column kind: {kind}")


def enqueue_task(task_fn: Callable, *args, **kwargs) -> Dict[str, Any]:
    """Standardize task enqueue responses."""
    result = task_fn.delay(*args, **kwargs)
    return {"task_id": result.id}


TASK_ACTIONS: List[Dict[str, Any]] = [
    {
        "task_name": "admin_backfill_5m",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/5m",
        "description": "Backfill 5m bars for last N days (default 5).",
        "params_schema": [
            {"name": "n_days", "type": "int", "default": 5, "min": 1, "max": 60},
            {"name": "batch_size", "type": "int", "default": 50, "min": 10, "max": 500},
        ],
        "status_task": "admin_backfill_5m",
    },
    {
        "task_name": "admin_backfill_daily",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/daily",
        "description": "Backfill last ~200 daily bars for tracked universe.",
        "params_schema": [
            {"name": "days", "type": "int", "default": 200, "min": 30, "max": 3000},
        ],
        "status_task": "admin_backfill_daily",
    },
    {
        "task_name": "admin_coverage_backfill_stale",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/coverage/stale",
        "description": "Backfill stale/missing daily bars across tracked symbols.",
        "status_task": "admin_coverage_backfill_stale",
    },
    {
        "task_name": "admin_coverage_refresh",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/coverage/refresh",
        "description": "Recompute coverage health snapshot and cache.",
        "status_task": "admin_coverage_refresh",
    },
    {
        "task_name": "admin_coverage_backfill",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/coverage",
        "description": "Guided backfill: refresh -> tracked -> daily -> recompute -> history -> refresh.",
        "status_task": "admin_coverage_backfill",
    },
    {
        "task_name": "admin_indicators_recompute_universe",
        "method": "POST",
        "endpoint": "/market-data/admin/indicators/recompute-universe",
        "description": "Recompute indicators for tracked universe.",
        "params_schema": [
            {"name": "batch_size", "type": "int", "default": 50, "min": 10, "max": 200},
        ],
        "status_task": "admin_indicators_recompute_universe",
    },
    {
        "task_name": "admin_snapshots_history_backfill",
        "method": "POST",
        "endpoint": "/market-data/admin/backfill/snapshots/history",
        "description": "Backfill snapshot history for last 200 trading days.",
        "params_schema": [
            {"name": "days", "type": "int", "default": 200, "min": 5, "max": 3000},
        ],
        "status_task": "admin_snapshots_history_backfill",
    },
    {
        "task_name": "admin_snapshots_history_record",
        "method": "POST",
        "endpoint": "/market-data/admin/snapshots/history/record",
        "description": "Record immutable daily analysis history.",
        "status_task": "admin_snapshots_history_record",
    },
    {
        "task_name": "market_indices_constituents_refresh",
        "method": "POST",
        "endpoint": "/market-data/indices/constituents/refresh",
        "description": "Refresh SP500 / NASDAQ100 / DOW30 / RUSSELL2000 constituents.",
        "status_task": "market_indices_constituents_refresh",
    },
    {
        "task_name": "market_universe_tracked_refresh",
        "method": "POST",
        "endpoint": "/market-data/universe/tracked/refresh",
        "description": "Refresh tracked symbol universe (index + portfolio).",
        "status_task": "market_universe_tracked_refresh",
    },
    {
        "task_name": "admin_recover_stale_job_runs",
        "method": "POST",
        "endpoint": "/market-data/admin/jobs/recover-stale",
        "description": "Mark job runs stuck in RUNNING as cancelled.",
        "params_schema": [
            {"name": "stale_minutes", "type": "int", "default": 120, "min": 30, "max": 10080},
        ],
        "status_task": "admin_recover_stale_job_runs",
    },
]


def coverage_actions(backfill_5m_enabled: bool = True) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = [
        {
            "label": "Refresh Index Constituents",
            "task_name": "market_indices_constituents_refresh",
            "description": "Fetch SP500 / NASDAQ100 / DOW30 members (FMP-first, Wikipedia fallback).",
        },
        {
            "label": "Update Tracked Symbols",
            "task_name": "market_universe_tracked_refresh",
            "description": "Union index constituents with held symbols and publish to Redis.",
        },
        {
            "label": "Backfill Daily Coverage (Tracked)",
            "task_name": "admin_coverage_backfill",
            "description": "Guided flow: refresh -> tracked -> daily backfill -> recompute -> history.",
        },
        {
            "label": "Backfill Daily (Stale Only)",
            "task_name": "admin_coverage_backfill_stale",
            "description": "Backfill daily bars only for symbols currently stale (>48h) in coverage.",
        },
        {
            "label": "Refresh Coverage Cache",
            "task_name": "admin_coverage_refresh",
            "description": "Recompute coverage snapshot and refresh Redis cache.",
        },
        {
            "label": "Backfill 5m Last N Days",
            "task_name": "admin_backfill_5m",
            "description": "Populate 5m bars for the tracked set to improve intraday freshness.",
        },
    ]
    if not backfill_5m_enabled:
        for action in actions:
            if action.get("task_name") == "admin_backfill_5m":
                action["disabled"] = True
                action["description"] = f"{action.get('description')} (disabled)"
    return actions


def coverage_education() -> Dict[str, Any]:
    return {
        "coverage": "Coverage measures how many tracked symbols have fresh bars stored in price_data.",
        "tracked": "Tracked is the union of live index constituents plus any symbols seen in brokerage accounts.",
        "how_to_fix": [
            "Refresh Index Constituents to sync SP500 / NASDAQ100 / DOW30 membership.",
            "Update Tracked Symbol Cache to rebuild the Redis universe from the DB.",
            "Backfill Daily Coverage (Tracked) to backfill daily bars and recompute indicators.",
            "Backfill 5m to capture latest intraday data for freshness dashboards.",
        ],
    }


def tracked_actions() -> List[Dict[str, str]]:
    return [
        {
            "label": "Update Tracked Symbols",
            "task_name": "market_universe_tracked_refresh",
            "description": "Rebuild tracked:all / tracked:new from DB index_constituents + portfolio.",
        },
    ]


def tracked_education() -> Dict[str, Any]:
    return {
        "overview": "Tracked symbols represent everything the platform monitors (index members + holdings).",
        "details": [
            "Update Tracked Symbol Cache unions DB constituents with holdings and publishes to Redis.",
            "You can sort/filter the table by sector, industry, ATR, or stage to decide next action.",
        ],
    }
