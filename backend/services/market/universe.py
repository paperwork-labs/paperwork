"""Tracked universe helpers.

Single source of truth for:
- prefer Redis `tracked:all` if present (UI/source-of-truth)
- otherwise derive from DB: active index constituents ∪ portfolio symbols
"""

from __future__ import annotations

import json
import logging
from typing import Iterable, List

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from redis.asyncio import Redis as AsyncRedis

from backend.models import Position
from backend.models.index_constituent import IndexConstituent
from backend.services.market.constants import CURATED_MARKET_SYMBOLS


def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
    return sorted({str(s).upper() for s in (symbols or []) if s})


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
        raw = redis_client.get("tracked:all")
        if raw:
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode()
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                out = _normalize_symbols(parsed)
                if out:
                    return out, True
    except Exception as e:
        logger.warning("tracked_symbols_with_source: failed reading tracked:all from Redis: %s", e)
        pass
    return tracked_symbols_from_db(db), False


def tracked_symbols(db: Session, *, redis_client) -> list[str]:
    """Return the tracked universe symbols, preferring Redis tracked:all."""
    return tracked_symbols_with_source(db, redis_client=redis_client)[0]


async def tracked_symbols_with_source_async(
    db: Session, *, redis_async: AsyncRedis
) -> tuple[list[str], bool]:
    """Async variant: return tracked universe symbols and whether Redis was used."""
    try:
        raw = await redis_async.get("tracked:all")
        if raw:
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode()
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                out = _normalize_symbols(parsed)
                if out:
                    return out, True
    except Exception as e:
        logger.warning(
            "tracked_symbols_with_source_async: failed reading tracked:all from Redis: %s",
            e,
        )
    return tracked_symbols_from_db(db), False


async def tracked_symbols_async(db: Session, *, redis_async: AsyncRedis) -> list[str]:
    """Async variant of tracked_symbols for async HTTP handlers."""
    out, _ = await tracked_symbols_with_source_async(db, redis_async=redis_async)
    return out


