"""Tracked universe helpers.

Single source of truth for:
- prefer Redis `tracked:all` if present (UI/source-of-truth)
- otherwise derive from DB: active index constituents ∪ portfolio symbols
"""

from __future__ import annotations

import json
from typing import Iterable, List

from sqlalchemy.orm import Session

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
    except Exception:
        pass
    try:
        for (s,) in db.query(Position.symbol).distinct():
            if s:
                syms.add(str(s).upper())
    except Exception:
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
    except Exception:
        pass
    return tracked_symbols_from_db(db), False


def tracked_symbols(db: Session, *, redis_client) -> list[str]:
    """Return the tracked universe symbols, preferring Redis tracked:all."""
    return tracked_symbols_with_source(db, redis_client=redis_client)[0]


