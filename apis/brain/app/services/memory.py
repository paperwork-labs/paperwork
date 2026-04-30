"""P11.3: Memory system — store and retrieve episodes with hybrid search.

D5: Hybrid retrieval with RRF fusion:
- Vector similarity (pgvector, weight 0.40)
- Full-text search (Postgres tsvector, weight 0.35)
- Entity graph traversal (weight 0.15) — Phase 2
- Recency bias (weight 0.10)

D11: PII scrubbing on all stored text
D15: Memory fatigue — recently-recalled episodes penalized 0.5x via Redis (24h TTL)

medallion: ops
"""

import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.episode import Episode
from app.services.embeddings import embed_text
from app.services.pii import scrub_pii

logger = logging.getLogger(__name__)

RRF_K = 60

VECTOR_WEIGHT = 0.40
FTS_WEIGHT = 0.35
RECENCY_WEIGHT = 0.10
ENTITY_WEIGHT = 0.15  # Reserved for Phase 2


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
    skip_embedding: bool = False,
) -> Episode:
    scrubbed_summary = scrub_pii(summary)
    scrubbed_context = scrub_pii(full_context) if full_context else None

    embedding: list[float] | None = None
    if not skip_embedding:
        embed_text_input = scrubbed_summary
        if scrubbed_context:
            embed_text_input = f"{scrubbed_summary}\n\n{scrubbed_context[:2000]}"
        embedding = await embed_text(embed_text_input)

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
        embedding=embedding,
    )
    db.add(episode)
    await db.flush()
    logger.info(
        "Stored episode %s (org=%s, source=%s, has_embedding=%s)",
        episode.id,
        organization_id,
        source,
        embedding is not None,
    )
    return episode


async def search_episodes(
    db: AsyncSession,
    *,
    organization_id: str,
    query: str,
    limit: int = 10,
    fatigue_ids: set[int] | None = None,
    skip_embedding: bool = False,
) -> list[Episode]:
    """D5: Hybrid search with RRF fusion.

    Combines:
    - Vector similarity (pgvector cosine distance)
    - Full-text search (Postgres tsvector)
    - Recency bias

    Entity graph traversal (D5 4th path) deferred to Phase 2.

    Args:
        skip_embedding: Skip vector search (for tests or when embeddings unavailable).
    """
    fatigue_ids = fatigue_ids or set()
    candidate_limit = limit * 3

    scores: dict[int, dict[str, float]] = {}

    query_embedding = None if skip_embedding else await embed_text(query)
    if query_embedding:
        vector_query = text("""
            SELECT id,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS similarity,
                   EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0 AS age_days
            FROM agent_episodes
            WHERE organization_id = :org_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit_val
        """)
        result = await db.execute(
            vector_query,
            {
                "embedding": str(query_embedding),
                "org_id": organization_id,
                "limit_val": candidate_limit,
            },
        )
        for rank, row in enumerate(result.fetchall()):
            episode_id = int(row[0])
            similarity = float(row[1] or 0.0)
            age_days = float(row[2] or 0.0)
            if episode_id not in scores:
                scores[episode_id] = {
                    "vector": 0.0,
                    "fts": 0.0,
                    "recency": 0.0,
                    "age_days": age_days,
                }
            scores[episode_id]["vector"] = 1.0 / (RRF_K + rank + 1)
            scores[episode_id]["vector_sim"] = similarity

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
        {"query": query, "org_id": organization_id, "limit_val": candidate_limit},
    )
    for rank, row in enumerate(result.fetchall()):
        episode_id = int(row[0])
        fts_score = float(row[1] or 0.0)
        age_days = float(row[2] or 0.0)
        if episode_id not in scores:
            scores[episode_id] = {"vector": 0.0, "fts": 0.0, "recency": 0.0, "age_days": age_days}
        scores[episode_id]["fts"] = 1.0 / (RRF_K + rank + 1)
        scores[episode_id]["fts_raw"] = fts_score

    scored: list[tuple[int, float]] = []
    for episode_id, components in scores.items():
        age_days = components.get("age_days", 0.0)
        recency_score = 1.0 / (1.0 + age_days * 0.1)

        combined = (
            VECTOR_WEIGHT * components["vector"]
            + FTS_WEIGHT * components["fts"]
            + RECENCY_WEIGHT * recency_score
        )

        if episode_id in fatigue_ids:
            combined *= 0.5

        scored.append((episode_id, combined))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_ids = [eid for eid, _ in scored[:limit]]

    if not top_ids:
        return []

    episodes = await db.execute(
        select(Episode).where(
            Episode.id.in_(top_ids),
            Episode.organization_id == organization_id,
        )
    )
    episode_map = {e.id: e for e in episodes.scalars().all()}
    return [episode_map[eid] for eid in top_ids if eid in episode_map]


async def get_thread_persona(
    db: AsyncSession,
    *,
    organization_id: str,
    thread_key: str,
) -> str | None:
    """Track C: return the persona that last replied in this thread.

    ``thread_key`` is a stable identifier for a conversation thread — e.g.
    ``"conv:<conversation_id>"`` or any caller-provided string. Brain looks
    for a prior episode keyed by this thread and returns the persona slug
    so the caller can pin future replies to it. This makes a persona feel
    like a real employee in a thread: once CPA picks up the conversation,
    CPA stays on it.

    Returns None when the thread is brand-new or memory is cold — caller
    falls back to keyword routing in that case.
    """
    stmt = (
        select(Episode.persona)
        .where(
            Episode.organization_id == organization_id,
            Episode.source_ref == thread_key,
            Episode.persona.is_not(None),
            Episode.persona != "router",
            Episode.persona != "system",
        )
        .order_by(Episode.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.first()
    return row[0] if row else None


async def get_fatigue_ids(redis_client, organization_id: str) -> set[int]:
    """D15: Get recently-recalled episode IDs from Redis."""
    if redis_client is None:
        return set()
    try:
        key = f"brain:fatigue:{organization_id}"
        members = await redis_client.smembers(key)
        return {int(m) for m in members}
    except Exception:
        logger.warning("get_fatigue_ids failed", exc_info=True)
        return set()


async def mark_recalled(redis_client, organization_id: str, episode_ids: list[int]) -> None:
    """D15: Mark episodes as recently recalled (24h TTL)."""
    if not episode_ids or redis_client is None:
        return
    try:
        key = f"brain:fatigue:{organization_id}"
        await redis_client.sadd(key, *[str(eid) for eid in episode_ids])
        await redis_client.expire(key, 86400)
    except Exception:
        logger.warning("Failed to mark fatigue IDs in Redis", exc_info=True)
