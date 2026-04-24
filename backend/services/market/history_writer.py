"""
History Writer
==============

Single source of truth for writing to MarketSnapshotHistory.
Ensures consistent schema, deduplication, and upsert semantics.

medallion: silver
"""

import logging
from datetime import date
from typing import Dict, List, Optional, Set

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.models.market_data import MarketSnapshot, MarketSnapshotHistory, MarketRegime

logger = logging.getLogger(__name__)

# Natural key + columns we do not overwrite on conflict (ledger key + insert-only timestamp).
_HISTORY_CONFLICT_UPDATE_EXCLUDE = frozenset(
    {
        "id",
        "symbol",
        "analysis_type",
        "as_of_date",
        "analysis_timestamp",
    }
)


def snapshot_to_history_row(
    snap: MarketSnapshot,
    as_of_date: date,
    regime: Optional[MarketRegime] = None,
) -> Dict:
    """Convert a MarketSnapshot to a dict suitable for MarketSnapshotHistory.

    Args:
        snap: The MarketSnapshot object
        as_of_date: The date for the history row
        regime: Optional current regime to denormalize

    Returns:
        Dict with all columns needed for MarketSnapshotHistory
    """
    skip_cols = {"id", "created_at", "updated_at", "metadata", "raw_analysis"}

    data = {
        "symbol": snap.symbol,
        "as_of_date": as_of_date,
        "analysis_type": "technical_snapshot",
    }

    # Copy all indicator columns
    for col in snap.__table__.columns:
        if col.name in skip_cols or col.name in data:
            continue
        val = getattr(snap, col.name, None)
        if val is not None:
            data[col.name] = val

    # Denormalize regime state if available
    if regime:
        data["regime_state"] = regime.regime_state
        data["regime_composite"] = regime.composite_score

    return data


def upsert_history_rows(
    db: Session,
    rows: List[Dict],
    batch_size: int = 100,
) -> int:
    """Upsert rows into MarketSnapshotHistory using PostgreSQL INSERT ... ON CONFLICT.

    Executes one bulk statement per batch (no per-row SELECT). Keys not present on the
    model table (e.g. stale denormalized fields) are ignored.

    Transaction: this function does **not** commit. The caller owns the session and
    must ``commit()`` (or nest in a larger unit of work).

    Args:
        db: SQLAlchemy session.
        rows: Column-keyed dicts; must include ``symbol`` and ``as_of_date``.
        batch_size: Max rows per INSERT statement.

    Returns:
        Number of rows successfully sent (per batch that executed without error).
    """
    table = MarketSnapshotHistory.__table__
    allowed_cols = {c.name for c in table.columns}

    prepared: List[Dict] = []
    for row_data in rows:
        symbol = row_data.get("symbol")
        as_of = row_data.get("as_of_date")
        analysis_type = row_data.get("analysis_type", "technical_snapshot")
        if not symbol or not as_of:
            continue
        payload = {
            k: v for k, v in row_data.items() if k in allowed_cols and k != "id"
        }
        payload["symbol"] = symbol
        payload["as_of_date"] = as_of
        payload["analysis_type"] = analysis_type
        prepared.append(payload)

    if not prepared:
        return 0

    written = 0
    for start in range(0, len(prepared), batch_size):
        batch = prepared[start : start + batch_size]
        key_union: Set[str] = set()
        for p in batch:
            key_union.update(p.keys())
        key_union.discard("id")
        normalized = [{k: p.get(k) for k in sorted(key_union)} for p in batch]

        set_columns = sorted(key_union - _HISTORY_CONFLICT_UPDATE_EXCLUDE)
        try:
            stmt = pg_insert(table).values(normalized)
            if not set_columns:
                stmt = stmt.on_conflict_do_nothing(constraint="uq_symbol_type_asof")
            else:
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_symbol_type_asof",
                    set_={k: stmt.excluded[k] for k in set_columns},
                )
            db.execute(stmt)
            written += len(batch)
        except Exception as e:
            logger.warning(
                "Bulk upsert market_snapshot_history failed for batch offset %s (%s rows): %s",
                start,
                len(batch),
                e,
                exc_info=True,
            )

    db.flush()
    return written


def record_daily_snapshot_history(
    db: Session,
    as_of_date: Optional[date] = None,
    include_regime: bool = True,
) -> Dict:
    """Record all current MarketSnapshots to history for a given date.

    This is the primary function to call from scheduled tasks.

    Transaction: does **not** commit. Call ``db.commit()`` after this returns if the
    write should be persisted.

    Args:
        db: SQLAlchemy session
        as_of_date: Date to record (defaults to today)
        include_regime: Whether to denormalize current regime state

    Returns:
        Dict with stats: symbols_recorded, existing_skipped, errors
    """
    from datetime import date as date_type

    if as_of_date is None:
        as_of_date = date_type.today()

    # Get current regime if needed
    regime = None
    if include_regime:
        from backend.services.market.regime_engine import get_current_regime
        regime = get_current_regime(db)

    # Get all valid snapshots
    snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.analysis_type == "technical_snapshot",
        MarketSnapshot.is_valid.is_(True),
    ).all()

    if not snapshots:
        return {"symbols_recorded": 0, "existing_skipped": 0, "errors": 0}

    # Convert to history rows
    rows = [snapshot_to_history_row(s, as_of_date, regime) for s in snapshots]

    # Upsert
    written = upsert_history_rows(db, rows)

    return {
        "symbols_recorded": written,
        "as_of_date": as_of_date.isoformat(),
        "regime_state": regime.regime_state if regime else None,
    }
