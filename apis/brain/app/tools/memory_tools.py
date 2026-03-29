"""MCP / agent tool: search Brain episodic memory."""

import contextvars
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services import memory
from app.tools import trim_output

logger = logging.getLogger(__name__)

_db_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis_client: Any | None = None

# Set from the request/tool runner so search is scoped to the correct tenant.
_organization_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "brain_memory_tool_organization_id", default=None
)


def configure(
    db_session_factory: async_sessionmaker[AsyncSession],
    redis_client: Any,
    default_organization_id: str = "paperwork-labs",
) -> None:
    """Called during app startup to inject dependencies."""
    global _db_session_factory, _redis_client
    _db_session_factory = db_session_factory
    _redis_client = redis_client
    _organization_id.set(default_organization_id)


def set_organization_id(organization_id: str) -> contextvars.Token:
    """Bind organization for the current async task; reset the returned token when done."""
    return _organization_id.set(organization_id)


def reset_organization_id(token: contextvars.Token) -> None:
    """Reset organization binding from set_organization_id."""
    _organization_id.reset(token)


async def search_memory(query: str, limit: int = 5) -> str:
    """Search Brain's episodic memory for relevant past conversations and knowledge."""
    if _db_session_factory is None or _redis_client is None:
        logger.warning("search_memory called before configure()")
        return "Memory search is not configured."

    org_id = _organization_id.get()
    if not org_id:
        logger.warning("search_memory called without organization context")
        return "Memory search requires an organization context."

    try:
        async with _db_session_factory() as db:
            fatigue_ids = await memory.get_fatigue_ids(_redis_client, org_id)
            episodes = await memory.search_episodes(
                db,
                organization_id=org_id,
                query=query,
                limit=limit,
                fatigue_ids=fatigue_ids,
            )

            if not episodes:
                return "No relevant memories found."

            recalled_ids = [e.id for e in episodes]
            await memory.mark_recalled(_redis_client, org_id, recalled_ids)

            lines = [
                f"[{e.source} | {e.created_at.strftime('%Y-%m-%d')}] {e.summary}" for e in episodes
            ]
            return trim_output("\n".join(lines))
    except Exception as e:
        logger.error("search_memory failed for org=%s: %s", org_id, e, exc_info=True)
        return "Memory search failed. Please try again."
