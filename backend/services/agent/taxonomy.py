"""
Action Risk Taxonomy
====================

Defines risk levels for agent actions and classification rules.
"""

from enum import Enum
from typing import Dict, Set


class RiskLevel(str, Enum):
    """Risk classification for agent actions."""
    SAFE = "safe"           # Auto-execute always (monitoring, read-only ops)
    MODERATE = "moderate"   # Auto-execute in "safe" mode (backfills, recomputes)
    RISKY = "risky"         # Requires approval (data corrections, batch operations)
    CRITICAL = "critical"   # Always requires approval (trading, deletions)


ACTION_RISK_MAP: Dict[str, RiskLevel] = {
    # SAFE: Read-only monitoring and status checks
    "check_health": RiskLevel.SAFE,
    "query_database": RiskLevel.SAFE,
    "fetch_logs": RiskLevel.SAFE,
    "web_search": RiskLevel.SAFE,
    "browse_url": RiskLevel.SAFE,
    "send_alert": RiskLevel.SAFE,
    "list_jobs": RiskLevel.SAFE,
    "check_broker_connection": RiskLevel.SAFE,
    # SAFE: Holistic chat tools (read-only)
    "get_portfolio_summary": RiskLevel.SAFE,
    "get_position_details": RiskLevel.SAFE,
    "get_activity": RiskLevel.SAFE,
    "get_market_snapshot": RiskLevel.SAFE,
    "get_tracked_universe": RiskLevel.SAFE,
    "get_constituents": RiskLevel.SAFE,
    "get_regime": RiskLevel.SAFE,
    "describe_tables": RiskLevel.SAFE,
    # SAFE: Schedule management (read-only)
    "list_schedules": RiskLevel.SAFE,
    # MODERATE: Codebase exploration (read-only, but can expose internals to the LLM / Redis history)
    "read_file": RiskLevel.MODERATE,
    "list_files": RiskLevel.MODERATE,
    # MODERATE: Schedule management (triggers tasks)
    "run_task_now": RiskLevel.MODERATE,

    # MODERATE: Standard remediation tasks
    "backfill_stale_daily": RiskLevel.MODERATE,
    "recompute_indicators": RiskLevel.MODERATE,
    "record_daily": RiskLevel.MODERATE,
    "compute_regime": RiskLevel.MODERATE,
    "monitor_coverage": RiskLevel.MODERATE,
    "recover_stale_jobs": RiskLevel.MODERATE,
    "bootstrap_coverage": RiskLevel.MODERATE,
    "refresh_index_constituents": RiskLevel.MODERATE,
    "fill_missing_fundamentals": RiskLevel.MODERATE,
    "deep_backfill": RiskLevel.MODERATE,
    
    # RISKY: May affect data integrity or require significant compute
    "backfill_full_history": RiskLevel.RISKY,
    "recompute_all_indicators": RiskLevel.RISKY,
    "sync_broker_account": RiskLevel.RISKY,
    "clear_cache": RiskLevel.RISKY,
    "restart_service": RiskLevel.RISKY,
    
    # CRITICAL: Trading or data destructive operations
    "execute_order": RiskLevel.CRITICAL,
    "cancel_order": RiskLevel.CRITICAL,
    "modify_position": RiskLevel.CRITICAL,
    "delete_data": RiskLevel.CRITICAL,
    "run_migration": RiskLevel.CRITICAL,
}


SAFE_ACTIONS: Set[str] = {k for k, v in ACTION_RISK_MAP.items() if v == RiskLevel.SAFE}
MODERATE_ACTIONS: Set[str] = {k for k, v in ACTION_RISK_MAP.items() if v == RiskLevel.MODERATE}
RISKY_ACTIONS: Set[str] = {k for k, v in ACTION_RISK_MAP.items() if v == RiskLevel.RISKY}
CRITICAL_ACTIONS: Set[str] = {k for k, v in ACTION_RISK_MAP.items() if v == RiskLevel.CRITICAL}


def classify_action_risk(action_type: str) -> RiskLevel:
    """Classify an action type by its risk level."""
    return ACTION_RISK_MAP.get(action_type, RiskLevel.RISKY)


def can_auto_execute(action_type: str, autonomy_level: str) -> bool:
    """
    Check if an action can be auto-executed given the autonomy level.
    
    Args:
        action_type: The action type to check
        autonomy_level: One of "full", "safe", "ask"
        
    Returns:
        True if action can be auto-executed
    """
    if autonomy_level == "ask":
        return False
    
    risk = classify_action_risk(action_type)
    
    if autonomy_level == "full":
        return risk != RiskLevel.CRITICAL
    
    if autonomy_level == "safe":
        return risk in (RiskLevel.SAFE, RiskLevel.MODERATE)
    
    return False
