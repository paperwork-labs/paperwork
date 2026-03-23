"""P11.3: Memory system — store and retrieve episodes with hybrid search.

Retrieval uses Reciprocal Rank Fusion (RRF) combining:
- Vector similarity (weight 0.4) via pgvector
- Full-text search (weight 0.35) via tsvector
- Recency bias (weight 0.25)

D15: Memory fatigue — recently-recalled episodes penalized 0.5x via Redis (24h TTL).
D11: PII scrubbing on all stored text.
"""

import logging
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.episode import Episode
from app.services.pii import scrub_pii

logger = logging.getLogger(__name__)

RRF_K = 60


async def store_episode(
    db: AsyncSession,
    *,
    organization_id: str,
    source: str,
    summary: str,
    full_context: str | None = None,
    user_id: str | None = None,
    channel: str | None = None,
    persona: str | None = None,
    product: str | None = None,
    source_ref: str | None = None,
    importance: float = 0.5,
    model_used: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    metadata: dict | None = None,
) -> Episode:
    scrubbed_summary = scrub_pii(summary)
    scrubbed_context = scrub_pii(full_context) if full_context else None

    episode = Episode(
        organization_id=organization_id,
        source=source,
        summary=scrubbed_summary,
        full_context=scrubbed_context,
        user_id=user_id,
        channel=channel,
        persona=persona,
        product=product,
        source_ref=source_ref,
        importance=importance,
        model_used=model_used,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        metadata_=metadata or {},
    )
    db.add(episode)
    await db.flush()
    logger.info("Stored episode %s (org=%s, source=%s)", episode.id, organization_id, source)
    return episode


async def search_episodes(
    db: AsyncSession,
    *,
    organization_id: str,
    query: str,
    limit: int = 10,
    fatigue_ids: set[int] | None = None,
) -> list[Episode]:
    """Hybrid search: full-text + recency, ranked by RRF.
    Vector search requires embeddings (Phase 2). For P1, FTS + recency."""

    scrubbed_query = scrub_pii(query)
    fatigue_ids = fatigue_ids or set()

    fts_query = text("""
        SELECT id,
               ts_rank_cd(search_vector, websearch_to_tsquery('english', :query)) AS fts_score,
               EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0 AS age_days
        FROM agent_episodes
        WHERE organization_id = :org_id
          AND search_vector @@ websearch_to_tsquery('english', :query)
        ORDER BY fts_score DESC
        LIMIT :limit_val
    """)

    result = await db.execute(
        fts_query,
        {"query": scrubbed_query, "org_id": organization_id, "limit_val": limit * 3},
    )
    rows = result.fetchall()

    scored: list[tuple[int, float]] = []
    for rank, row in enumerate(rows):
        episode_id = row[0]
        fts_score = row[1] or 0.0
        age_days = row[2] or 0.0

        fts_rrf = 0.35 * (1.0 / (RRF_K + rank + 1))
        recency_rrf = 0.25 * (1.0 / (1.0 + age_days * 0.1))
        combined = fts_rrf + recency_rrf

        if episode_id in fatigue_ids:
            combined *= 0.5

        scored.append((episode_id, combined))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_ids = [eid for eid, _ in scored[:limit]]

    if not top_ids:
        return []

    episodes = await db.execute(
        select(Episode).where(Episode.id.in_(top_ids))
    )
    episode_map = {e.id: e for e in episodes.scalars().all()}
    return [episode_map[eid] for eid in top_ids if eid in episode_map]


async def get_fatigue_ids(redis_client, organization_id: str) -> set[int]:
    """D15: Get recently-recalled episode IDs from Redis."""
    try:
        key = f"brain:fatigue:{organization_id}"
        members = await redis_client.smembers(key)
        return {int(m) for m in members}
    except Exception:
        return set()


async def mark_recalled(redis_client, organization_id: str, episode_ids: list[int]) -> None:
    """D15: Mark episodes as recently recalled (24h TTL)."""
    if not episode_ids:
        return
    try:
        key = f"brain:fatigue:{organization_id}"
        await redis_client.sadd(key, *[str(eid) for eid in episode_ids])
        await redis_client.expire(key, 86400)
    except Exception:
        logger.warning("Failed to mark fatigue IDs in Redis", exc_info=True)
