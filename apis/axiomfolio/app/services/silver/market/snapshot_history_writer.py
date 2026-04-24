"""
Single module for MarketSnapshotHistory upsert semantics.

All production writes should go through this module so column mapping and conflict
behavior stay aligned when the model grows new fields.

Callers:
- ``market_data_service.MarketDataService.persist_snapshot`` (ORM)
- ``app.tasks.market.history.snapshot_for_date`` (ORM)
- ``app.tasks.market.history.record_daily`` (ORM)
- ``app.tasks.market.history.snapshot_last_n_days`` (PostgreSQL upsert, wide rows)
- ``app.tasks.market.history.snapshot_for_symbol`` (PostgreSQL upsert, partial rows)

medallion: silver
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.market_data import MarketSnapshotHistory

_HISTORY_HEADLINE_FIELDS: tuple[str, ...] = (
    "current_price",
    "rsi",
    "atr_value",
    "sma_50",
    "macd",
    "macd_signal",
)

# ORM insert: kwargs handled explicitly or via server default — do not duplicate in **wide.
_ORM_INSERT_RESERVED: frozenset[str] = frozenset(
    {
        "id",
        "symbol",
        "analysis_type",
        "as_of_date",
        "analysis_timestamp",
        "current_price",
        "rsi",
        "atr_value",
        "sma_50",
        "macd",
        "macd_signal",
    }
)

# Wide PostgreSQL upsert: do not overwrite these on conflict (identity + ledger timestamp).
_PG_CONFLICT_PRESERVE: frozenset[str] = frozenset(
    {"id", "symbol", "analysis_type", "as_of_date", "analysis_timestamp"}
)

_PG_PARTIAL_CONFLICT_KEYS: frozenset[str] = frozenset({"symbol", "analysis_type", "as_of_date"})


def upsert_snapshot_history_row(
    session: Session,
    symbol: str,
    as_of_date: datetime,
    snapshot: Mapping[str, Any],
    *,
    analysis_type: str = "technical_snapshot",
    update_analysis_timestamp: bool = True,
) -> MarketSnapshotHistory:
    """Idempotent upsert on (symbol, analysis_type, as_of_date).

    Sets headline columns, then copies every snapshot key that exists on the model.
    When ``update_analysis_timestamp`` is True (live / operator paths), refreshes
    ``analysis_timestamp`` on each write. Backfill tasks that rely on server default
    can pass False.
    """
    now = datetime.now(timezone.utc)
    snap = dict(snapshot)
    existing = (
        session.query(MarketSnapshotHistory)
        .filter(
            MarketSnapshotHistory.symbol == symbol,
            MarketSnapshotHistory.analysis_type == analysis_type,
            MarketSnapshotHistory.as_of_date == as_of_date,
        )
        .first()
    )
    if existing:
        if update_analysis_timestamp:
            existing.analysis_timestamp = now
        for f in _HISTORY_HEADLINE_FIELDS:
            setattr(existing, f, snap.get(f))
        for k, v in snap.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
        return existing

    ctor_kw: dict[str, Any] = {
        "symbol": symbol,
        "analysis_type": analysis_type,
        "as_of_date": as_of_date,
        "current_price": snap.get("current_price"),
        "rsi": snap.get("rsi"),
        "atr_value": snap.get("atr_value"),
        "sma_50": snap.get("sma_50"),
        "macd": snap.get("macd"),
        "macd_signal": snap.get("macd_signal"),
    }
    if update_analysis_timestamp:
        ctor_kw["analysis_timestamp"] = now
    ctor_kw.update(
        {
            k: v
            for k, v in snap.items()
            if k not in _ORM_INSERT_RESERVED and hasattr(MarketSnapshotHistory, k)
        }
    )
    hist = MarketSnapshotHistory(**ctor_kw)
    for k, v in snap.items():
        if hasattr(hist, k):
            setattr(hist, k, v)
    session.add(hist)
    return hist


def build_snapshot_history_pg_upsert_stmt(
    rows: Sequence[Mapping[str, Any]],
    *,
    conflict_update: str = "wide",
) -> Any:
    """Return ``INSERT ... ON CONFLICT DO UPDATE`` for ``market_snapshot_history``.

    Parameters
    ----------
    rows:
        One or more row dicts (model column names only).
    conflict_update:
        - ``wide``: update every column except those in ``_PG_CONFLICT_PRESERVE``
          (matches historical backfill that sends a full indicator-shaped row).
        - ``partial``: update only keys present on ``rows[0]``, excluding the natural
          key columns (for dataframe-driven rows that omit nullable columns).
    """
    if not rows:
        raise ValueError("rows must not be empty")
    stmt = pg_insert(MarketSnapshotHistory).values(list(rows))
    if conflict_update == "wide":
        set_ = {
            c.name: getattr(stmt.excluded, c.name)
            for c in MarketSnapshotHistory.__table__.columns
            if c.name and c.name not in _PG_CONFLICT_PRESERVE
        }
    elif conflict_update == "partial":
        keys = frozenset(rows[0].keys())
        set_ = {
            k: stmt.excluded[k]
            for k in keys
            if k not in _PG_PARTIAL_CONFLICT_KEYS
        }
    else:
        raise ValueError(f"unknown conflict_update: {conflict_update!r}")
    return stmt.on_conflict_do_update(constraint="uq_symbol_type_asof", set_=set_)
