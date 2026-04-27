"""Fetch and persist auxiliary external signals (stubs for Finviz/Zacks until licensed).

medallion: gold
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, List, Optional, TypedDict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models.external_signal import ExternalSignal

logger = logging.getLogger(__name__)


class ExternalSignalDict(TypedDict, total=False):
    symbol: str
    source: str
    signal_date: date
    signal_type: str
    value: Optional[Decimal]
    raw_payload: dict[str, Any]


def fetch_finviz_signals(symbols: list[str]) -> list[ExternalSignalDict]:
    """Scaffold: real Finviz integration is deferred (licensing)."""
    _ = symbols
    logger.info("finviz fetch not yet implemented")
    return []


def fetch_zacks_signals(symbols: list[str]) -> list[ExternalSignalDict]:
    """Scaffold: real Zacks integration is deferred (licensing)."""
    _ = symbols
    logger.info("zacks fetch not yet implemented")
    return []


def persist_signals(db: Session, signals: list[ExternalSignalDict]) -> int:
    """Upsert into ``external_signals``. Returns the number of upsert operations."""
    if not signals:
        return 0
    n = 0
    for s in signals:
        sym = (s.get("symbol") or "").upper().strip()
        src = (s.get("source") or "").lower().strip()
        sdate = s.get("signal_date")
        stype = (s.get("signal_type") or "").lower().strip()
        if not sym or not src or sdate is None or not stype:
            logger.warning(
                "persist_signals: skip row missing required fields: %s",
                s,
            )
            continue
        payload = s.get("raw_payload") or {}
        val = s.get("value")
        row = {
            "symbol": sym,
            "source": src,
            "signal_date": sdate,
            "signal_type": stype,
            "value": val,
            "raw_payload": payload,
        }
        stmt = pg_insert(ExternalSignal).values(**row)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_external_signals_sym_src_day_type",
            set_={
                "value": stmt.excluded.value,
                "raw_payload": stmt.excluded.raw_payload,
            },
        )
        db.execute(stmt)
        n += 1
    return n


def external_context_bonus_points(
    db: Session,
    symbol: str,
    *,
    lookback_days: int = 7,
) -> Decimal:
    """Minor bonus (0-2) added to pick quality pre-clip when flag is enabled."""
    if not settings.ENABLE_EXTERNAL_SIGNALS:
        return Decimal("0")
    sym = (symbol or "").upper().strip()
    if not sym:
        return Decimal("0")
    cutoff = datetime.now(UTC).date() - timedelta(days=lookback_days)
    n = (
        db.execute(
            select(func.count(ExternalSignal.id)).where(
                ExternalSignal.symbol == sym,
                ExternalSignal.signal_date >= cutoff,
            )
        )
        .scalar()
        or 0
    )
    if n <= 0:
        return Decimal("0")
    return min(
        Decimal("2"),
        Decimal(n) * Decimal("0.4"),
    )


def external_context_bonus_points_map(
    db: Session,
    symbols: list[str],
    *,
    lookback_days: int = 7,
) -> dict[str, Decimal]:
    """Same bonus as :func:`external_context_bonus_points` but one aggregate query (no N+1)."""
    if not settings.ENABLE_EXTERNAL_SIGNALS:
        return {
            (s or "").upper().strip(): Decimal("0")
            for s in symbols
            if (s or "").strip()
        }
    wanted: list[str] = list(
        dict.fromkeys(
            (s or "").upper().strip()
            for s in symbols
            if (s or "").strip()
        )
    )
    out: dict[str, Decimal] = {u: Decimal("0") for u in wanted}
    if not wanted:
        return out
    cutoff = datetime.now(UTC).date() - timedelta(days=lookback_days)
    rows = db.execute(
        select(ExternalSignal.symbol, func.count(ExternalSignal.id))
        .where(
            ExternalSignal.symbol.in_(wanted),
            ExternalSignal.signal_date >= cutoff,
        )
        .group_by(ExternalSignal.symbol)
    ).all()
    for sym, n in rows:
        nn = int(n) if n is not None else 0
        if nn <= 0:
            out[sym] = Decimal("0")
        else:
            out[sym] = min(
                Decimal("2"),
                Decimal(nn) * Decimal("0.4"),
            )
    return out
