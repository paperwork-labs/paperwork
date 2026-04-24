"""Tracked universe helpers.

Single source of truth for:
- prefer Redis `tracked:all` if present and fresh (UI/source-of-truth)
- otherwise derive from DB: active index constituents ∪ portfolio symbols

medallion: silver
"""

from __future__ import annotations

import json
import logging
import time
from typing import Iterable, List

from sqlalchemy.orm import Session
from redis.asyncio import Redis as AsyncRedis

from app.models import Position
from app.models.index_constituent import IndexConstituent
from app.services.market.constants import CURATED_MARKET_SYMBOLS

logger = logging.getLogger(__name__)

# Redis freshness for `tracked:all` (see `tracked:all:updated_at` on write).
TRACKED_ALL_UPDATED_AT_KEY = "tracked:all:updated_at"
TRACKED_ALL_MAX_AGE_SEC = 86400  # 24 hours

# Below this count after full resolution, Redis + DB may both be failing; curated-only is ~20.
_TRACKED_UNIVERSE_DEGRADED_THRESHOLD = 50


def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
    return sorted({str(s).upper() for s in (symbols or []) if s})


def _tracked_all_updated_at_is_stale_or_missing(updated_at_raw: object) -> bool:
    """If True, do not use Redis `tracked:all`; use DB instead. Emits warning logs."""
    if updated_at_raw is None:
        logger.warning("tracked:all:updated_at missing, falling through to DB")
        return True
    if isinstance(updated_at_raw, (bytes, bytearray)):
        updated_at_raw = updated_at_raw.decode()
    try:
        ts = float(updated_at_raw)
    except (TypeError, ValueError):
        logger.warning("tracked:all:updated_at invalid, falling through to DB")
        return True
    age = time.time() - ts
    if age > TRACKED_ALL_MAX_AGE_SEC:
        logger.warning(
            "tracked:all is %d hours stale, falling through to DB",
            int(age / 3600),
        )
        return True
    return False


def _log_if_universe_degraded(tracked: list[str]) -> None:
    if len(tracked) < _TRACKED_UNIVERSE_DEGRADED_THRESHOLD:
        logger.error(
            "Tracked universe degraded to %d symbols (expected 500+), sources may be failing",
            len(tracked),
        )


def tracked_symbols_from_db(db: Session) -> list[str]:
    syms: set[str] = set()
    try:
        for (s,) in (
            db.query(IndexConstituent.symbol)
            .filter(IndexConstituent.is_active.is_(True))
            .distinct()
        ):
            if s:
                syms.add(str(s).upper())
    except Exception as e:
        logger.warning("tracked_symbols_from_db: failed loading active index constituents: %s", e)
        pass
    try:
        for (s,) in db.query(Position.symbol).distinct():
            if s:
                syms.add(str(s).upper())
    except Exception as e:
        logger.warning("tracked_symbols_from_db: failed loading distinct position symbols: %s", e)
        pass
    # Always keep curated ETFs/index proxies in tracked coverage.
    syms.update({str(s).upper() for s in CURATED_MARKET_SYMBOLS if s})
    return sorted(syms)


def tracked_symbols_with_source(db: Session, *, redis_client) -> tuple[list[str], bool]:
    """Return tracked universe symbols and whether Redis was used."""
    try:
        updated_at_raw = redis_client.get(TRACKED_ALL_UPDATED_AT_KEY)
        if not _tracked_all_updated_at_is_stale_or_missing(updated_at_raw):
            raw = redis_client.get("tracked:all")
            if raw:
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode()
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    out = _normalize_symbols(parsed)
                    if out:
                        _log_if_universe_degraded(out)
                        return out, True
    except Exception as e:
        logger.warning("tracked_symbols_with_source: failed reading tracked:all from Redis: %s", e)
    out_db = tracked_symbols_from_db(db)
    _log_if_universe_degraded(out_db)
    return out_db, False


def tracked_symbols(db: Session, *, redis_client) -> list[str]:
    """Return the tracked universe symbols, preferring Redis tracked:all."""
    return tracked_symbols_with_source(db, redis_client=redis_client)[0]


async def tracked_symbols_with_source_async(
    db: Session, *, redis_async: AsyncRedis
) -> tuple[list[str], bool]:
    """Async variant: return tracked universe symbols and whether Redis was used."""
    try:
        updated_at_raw = await redis_async.get(TRACKED_ALL_UPDATED_AT_KEY)
        if not _tracked_all_updated_at_is_stale_or_missing(updated_at_raw):
            raw = await redis_async.get("tracked:all")
            if raw:
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode()
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    out = _normalize_symbols(parsed)
                    if out:
                        _log_if_universe_degraded(out)
                        return out, True
    except Exception as e:
        logger.warning(
            "tracked_symbols_with_source_async: failed reading tracked:all from Redis: %s",
            e,
        )
    out_db = tracked_symbols_from_db(db)
    _log_if_universe_degraded(out_db)
    return out_db, False


async def tracked_symbols_async(db: Session, *, redis_async: AsyncRedis) -> list[str]:
    """Async variant of tracked_symbols for async HTTP handlers."""
    out, _ = await tracked_symbols_with_source_async(db, redis_async=redis_async)
    return out


