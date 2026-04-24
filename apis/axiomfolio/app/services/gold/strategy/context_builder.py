"""
Context Builder for Strategy Evaluation
========================================

Single source of truth for building rule evaluation context from MarketSnapshot.
Handles field aliases and regime context inclusion for consistent evaluation
across live evaluation, API endpoints, and backtesting.

medallion: gold
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.market_data import MarketSnapshot, MarketSnapshotHistory

logger = logging.getLogger(__name__)

# Field aliases: template/rule field -> actual snapshot column
# Templates may use rsi_14, but snapshot has rsi. This mapping ensures compatibility.
FIELD_ALIASES: Dict[str, str] = {
    "rsi_14": "rsi",
    "company_name": "name",
}

# Fields to skip when converting snapshot to context
SKIP_FIELDS = {"id", "raw_analysis", "created_at", "updated_at", "metadata"}


def snapshot_to_context(
    snap: MarketSnapshot,
    include_regime: bool = True,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Convert a MarketSnapshot to a rule evaluation context dict.

    Args:
        snap: The MarketSnapshot object
        include_regime: Whether to include regime context (requires db session)
        db: SQLAlchemy session for fetching regime data

    Returns:
        Dict with all snapshot fields plus aliases and optional regime context
    """
    ctx: Dict[str, Any] = {"symbol": snap.symbol}

    for col in snap.__table__.columns:
        if col.name in SKIP_FIELDS:
            continue
        val = getattr(snap, col.name, None)
        ctx[col.name] = val

    # Add aliases so templates using rsi_14 or company_name still work
    for alias, actual in FIELD_ALIASES.items():
        if actual in ctx and alias not in ctx:
            ctx[alias] = ctx[actual]

    if include_regime and db is not None:
        regime_ctx = get_regime_context(db)
        ctx.update(regime_ctx)

    return ctx


def history_to_context(
    row: MarketSnapshotHistory,
    include_regime: bool = False,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Convert a MarketSnapshotHistory row to a rule evaluation context dict.

    Args:
        row: The MarketSnapshotHistory object
        include_regime: Whether to include regime context
        db: SQLAlchemy session for fetching regime data

    Returns:
        Dict with all history fields plus aliases
    """
    ctx: Dict[str, Any] = {"symbol": row.symbol}

    for col in row.__table__.columns:
        if col.name in SKIP_FIELDS:
            continue
        val = getattr(row, col.name, None)
        ctx[col.name] = val

    # Add aliases
    for alias, actual in FIELD_ALIASES.items():
        if actual in ctx and alias not in ctx:
            ctx[alias] = ctx[actual]

    # For history rows, use denormalized regime_state if available
    if not include_regime and hasattr(row, "regime_state") and row.regime_state:
        ctx["regime_state"] = row.regime_state

    if include_regime and db is not None:
        regime_ctx = get_regime_context(db)
        ctx.update(regime_ctx)

    return ctx


def get_regime_context(db: Session) -> Dict[str, Any]:
    """Fetch current market regime and return as flat dict for rule evaluation.

    Args:
        db: SQLAlchemy session

    Returns:
        Dict with regime_state, regime_multiplier, and related fields
    """
    try:
        from app.services.silver.regime.regime_engine import get_current_regime

        regime = get_current_regime(db)
        if regime is None:
            return {"regime_state": "UNKNOWN", "regime_multiplier": 1.0}
        return {
            "regime_state": regime.regime_state or "UNKNOWN",
            "regime_composite": regime.composite_score,
            "regime_multiplier": regime.regime_multiplier or 1.0,
            "regime_max_equity_pct": regime.max_equity_exposure_pct,
            "regime_cash_floor_pct": regime.cash_floor_pct,
        }
    except Exception:
        logger.warning("Could not fetch regime context for strategy evaluation")
        return {"regime_state": "UNKNOWN", "regime_multiplier": 1.0}


def add_prev_fields(
    ctx: Dict[str, Any],
    prev_row: Optional[MarketSnapshotHistory],
) -> Dict[str, Any]:
    """Add _prev suffix fields from prior history row for crossover detection.

    Args:
        ctx: Current context dict
        prev_row: Previous day's history row (or None)

    Returns:
        Updated context with _prev fields for key indicators
    """
    prev_fields = [
        "rsi",
        "ema10_dist_n",
        "sma50_dist_n",
        "sma150_dist_n",
        "current_price",
        "stage_label",
    ]

    if prev_row is None:
        for field in prev_fields:
            ctx[f"{field}_prev"] = None
        return ctx

    for field in prev_fields:
        val = getattr(prev_row, field, None)
        ctx[f"{field}_prev"] = val

    return ctx
