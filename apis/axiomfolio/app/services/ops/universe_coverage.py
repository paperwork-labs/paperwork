"""
Startup and health observability: held position symbols vs global tracked universe.

Failing to track a held symbol means indicator recompute may skip that ticker;
this module surfaces the gap in logs and the ``universe_coverage`` admin-health
dimension without blocking API startup.

medallion: ops
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from decimal import Decimal
from sqlalchemy.orm import Session

from app.models import User
from app.models.position import Position, PositionStatus

logger = logging.getLogger(__name__)

UNIVERSE_COVERAGE_REDIS_KEY = "admin:universe_coverage"


def _quantity_nonzero(quantity: object) -> bool:
    if quantity is None:
        return False
    try:
        return bool(Decimal(str(quantity)) != 0)
    except Exception:
        return True


def run_universe_coverage_check(db: Session) -> Dict[str, Any]:
    """Compare each active user's open position symbols to the tracked universe.

    Returns a JSON-serializable dict including counters and ``state`` in
    ``healthy`` / ``degraded`` / ``error`` (and ``gaps_total`` for degraded).
    Does not commit — read-only.
    """
    from app.services.market.market_data_service import infra
    from app.services.market.universe import tracked_symbols_with_source

    try:
        tracked_list, _src = tracked_symbols_with_source(
            db, redis_client=infra.redis_client
        )
    except Exception as e:  # noqa: BLE001 — surface on health, do not block startup
        logger.exception("universe coverage: failed to load tracked universe: %s", e)
        return {
            "state": "error",
            "users_checked": 0,
            "positions_total": 0,
            "gaps_total": 0,
            "errors": 1,
            "error_detail": str(e)[:2000],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    universe = {str(s).upper() for s in (tracked_list or []) if s}
    users_checked = 0
    positions_total = 0
    gaps_total = 0
    errors = 0

    users = db.query(User).filter(User.is_active.is_(True)).all()
    for user in users:
        users_checked += 1
        try:
            rows = (
                db.query(Position)
                .filter(
                    Position.user_id == user.id,
                    Position.status == PositionStatus.OPEN,
                )
                .all()
            )
        except Exception as e:  # noqa: BLE001
            errors += 1
            logger.warning(
                "universe coverage: positions query failed for user_id=%s: %s",
                user.id,
                e,
                exc_info=True,
            )
            continue
        for pos in rows:
            if not _quantity_nonzero(pos.quantity):
                continue
            sym = (pos.symbol or "").upper().strip()
            if not sym:
                continue
            positions_total += 1
            if sym not in universe:
                gaps_total += 1
                logger.warning(
                    "universe gap: user=%s symbol=%s held=True tracked=False",
                    user.id,
                    sym,
                )

    if errors:
        state = "error"
    elif gaps_total:
        state = "degraded"
    else:
        state = "healthy"

    out = {
        "state": state,
        "users_checked": users_checked,
        "positions_total": positions_total,
        "gaps_total": gaps_total,
        "errors": errors,
        "error_detail": None,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(
        "universe coverage summary: users_checked=%s positions_total=%s "
        "gaps_total=%s errors=%s state=%s",
        users_checked,
        positions_total,
        gaps_total,
        errors,
        state,
    )
    return out


def persist_universe_coverage_to_redis(payload: Dict[str, Any], *, r: object) -> None:
    """Store last check result for :meth:`read_universe_coverage_for_admin_health`."""
    try:
        body = json.dumps(payload, default=str)
        r.set(UNIVERSE_COVERAGE_REDIS_KEY, body)
    except Exception as e:
        logger.warning("universe coverage: redis persist failed: %s", e, exc_info=True)


def read_universe_coverage_for_admin_health() -> Optional[Dict[str, Any]]:
    """Load last startup check from Redis. Returns None if missing or parse error."""
    from app.services.market.market_data_service import infra

    r = getattr(infra, "redis_client", None)
    if r is None:
        return None
    try:
        raw = r.get(UNIVERSE_COVERAGE_REDIS_KEY)
        if not raw:
            return None
        s = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
        return json.loads(s)
    except Exception as e:
        logger.warning("universe coverage: redis read failed: %s", e, exc_info=True)
        return None
