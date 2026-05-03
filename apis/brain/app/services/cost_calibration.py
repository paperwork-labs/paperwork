"""Cost calibration service — stub for Wave L.

Phase 2 (post-launch) implementation will:
  1. Pull actual billing data from Anthropic Console export (CSV).
  2. Pull actual billing data from OpenAI Usage API (/v1/usage).
  3. Pull actual billing data from Cursor billing API (pending Cursor exposing this).
  4. Match billing rows to agent_dispatches by dispatched_at + model_used.
  5. Write actual_cost_cents back to matched rows.

See docs/PR_TSHIRT_SIZING.md § Cost Calibration Methodology for full spec.

medallion: ops
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


async def run_calibration_pass() -> int:
    """Stub: returns number of rows that need calibration.

    TODO(phase-h): implement Anthropic Console + OpenAI Usage API polling.
    """
    logger.info("cost_calibration: stub — full billing integration is Phase H")
    return 0


async def find_uncalibrated_rows(db_session: object) -> list[dict]:
    """Query agent_dispatches rows that need actual_cost_cents filled.

    Rows are eligible if:
      - actual_cost_cents IS NULL
      - completed_at < NOW() - 24h
    """
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.agent_dispatch import AgentDispatch

    if not isinstance(db_session, AsyncSession):
        logger.warning("cost_calibration: invalid session type — skipping")
        return []

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    stmt = select(AgentDispatch).where(
        AgentDispatch.actual_cost_cents.is_(None),
        AgentDispatch.completed_at.isnot(None),
        AgentDispatch.completed_at < cutoff,
    )
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    logger.info(
        "cost_calibration: %d rows need calibration (completed > 24h ago, no actual_cost_cents)",
        len(rows),
    )
    return [
        {
            "id": str(r.id),
            "t_shirt_size": r.t_shirt_size,
            "model_used": r.model_used,
            "dispatched_at": r.dispatched_at.isoformat() if r.dispatched_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "estimated_cost_cents": r.estimated_cost_cents,
        }
        for r in rows
    ]
