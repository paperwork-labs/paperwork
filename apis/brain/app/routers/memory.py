"""Memory API — REST surface for Autopilot to consume Brain's memory primitives.

Wires existing Brain memory services into 6 REST endpoints:
- D5  hybrid retrieval (vector + FTS + RRF) via recall-decisions + cross-context
- D15 memory fatigue (penalises recently-recalled episodes)
- D23 three-tier classification (episodic / semantic / procedural) via remember
- D40 procedural memory (procedural_memory.yaml + pr_outcomes.json)
- D55 cross-context queries (parallel retrieval across org scopes)

Auth: X-Brain-Secret header (BRAIN_API_SECRET). Same guard used by /admin/*.

medallion: ops
"""

from __future__ import annotations

import asyncio
import hmac
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.episode import Episode
from app.redis import get_redis
from app.schemas.base import success_response
from app.services import memory as memory_svc
from app.services import procedural_memory as proc_mem_svc
from app.services import pr_outcomes as pr_outcomes_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])

_DEFAULT_ORG = "paperwork-labs"

# Source prefixes used when Autopilot writes memories via POST /remember.
_TYPE_SOURCE = {
    "episodic": "autopilot:episodic",
    "semantic": "autopilot:semantic",
    "procedural": "autopilot:procedural",
}


# ---------------------------------------------------------------------------
# Auth guard — identical pattern to admin router's _require_admin
# ---------------------------------------------------------------------------


def _require_internal(
    x_brain_secret: str | None = Header(None, alias="X-Brain-Secret"),
) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        if settings.ENVIRONMENT == "development":
            return
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Brain-Secret")


def _get_redis_optional():
    try:
        return get_redis()
    except RuntimeError:
        return None


# ---------------------------------------------------------------------------
# GET /v1/memory/recall-decisions
# D5 hybrid retrieval — semantic memory (decisions, conclusions, lessons)
# ---------------------------------------------------------------------------


@router.get("/recall-decisions")
async def recall_decisions(
    query: str = Query(..., description="Search text for semantic memory lookup"),
    limit: int = Query(5, ge=1, le=20),
    organization_id: str = Query(_DEFAULT_ORG),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_internal),
) -> Any:
    """D5 hybrid retrieval — decisions and conclusions from semantic memory.

    Calls search_episodes() with RRF fusion (vector + FTS + recency).
    D15 memory fatigue: recently-recalled episodes are penalised 0.5x via Redis.
    """
    redis_client = _get_redis_optional()
    fatigue_ids = await memory_svc.get_fatigue_ids(redis_client, organization_id)

    episodes = await memory_svc.search_episodes(
        db,
        organization_id=organization_id,
        query=query,
        limit=limit,
        fatigue_ids=fatigue_ids,
    )

    if episodes:
        await memory_svc.mark_recalled(redis_client, organization_id, [e.id for e in episodes])

    return success_response({
        "query": query,
        "organization_id": organization_id,
        "results": [
            {
                "id": ep.id,
                "summary": ep.summary,
                "source": ep.source,
                "persona": ep.persona,
                "importance": ep.importance,
                "created_at": ep.created_at.isoformat() if ep.created_at else None,
                "metadata": ep.metadata_ or {},
            }
            for ep in episodes
        ],
        "count": len(episodes),
    })


# ---------------------------------------------------------------------------
# GET /v1/memory/recall-pr-history
# D40 procedural memory — PR outcomes by keyword + recency
# ---------------------------------------------------------------------------


@router.get("/recall-pr-history")
async def recall_pr_history(
    keywords: str = Query(
        ..., description="Comma-separated keywords to match against PR branch / workstream"
    ),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    _auth: None = Depends(_require_internal),
) -> Any:
    """D40 procedural memory — PR outcomes matching keywords from pr_outcomes.json.

    Filters by recency (days) and keyword match on branch + workstream IDs.
    Returns h1/h24 outcome flags (CI, deploy, revert) per PR.
    """
    kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    cutoff = datetime.now(UTC) - timedelta(days=days)

    all_outcomes = pr_outcomes_svc.list_pr_outcomes_for_query(limit=500)
    matched: list[dict[str, Any]] = []

    for outcome in all_outcomes:
        # Recency filter
        try:
            merged_ts_str = str(outcome.merged_at)
            if merged_ts_str.endswith("Z"):
                merged_ts_str = merged_ts_str[:-1] + "+00:00"
            merged_ts = datetime.fromisoformat(merged_ts_str)
            if merged_ts.tzinfo is None:
                merged_ts = merged_ts.replace(tzinfo=UTC)
            if merged_ts < cutoff:
                continue
        except Exception:
            pass  # include outcomes whose timestamp can't be parsed

        # Keyword match
        searchable = " ".join(
            filter(
                None,
                [
                    outcome.branch or "",
                    " ".join(outcome.workstream_ids or []),
                    " ".join(outcome.workstream_types or []),
                ],
            )
        ).lower()

        if kw_list and not any(kw in searchable for kw in kw_list):
            continue

        entry: dict[str, Any] = {
            "pr_number": outcome.pr_number,
            "branch": outcome.branch,
            "merged_at": outcome.merged_at,
            "merged_by_agent": outcome.merged_by_agent,
            "agent_model": outcome.agent_model,
            "ci_status_at_merge": outcome.ci_status_at_merge,
            "workstream_ids": outcome.workstream_ids or [],
            "workstream_types": outcome.workstream_types or [],
            "outcome_h1": (
                outcome.outcomes.h1.model_dump() if outcome.outcomes and outcome.outcomes.h1 else None
            ),
            "outcome_h24": (
                outcome.outcomes.h24.model_dump()
                if outcome.outcomes and outcome.outcomes.h24
                else None
            ),
        }
        matched.append(entry)
        if len(matched) >= limit:
            break

    return success_response({
        "keywords": kw_list,
        "days": days,
        "results": matched,
        "count": len(matched),
    })


# ---------------------------------------------------------------------------
# GET /v1/memory/episodic-themes
# D23 episodic memory — theme clusters from recent episodes
# ---------------------------------------------------------------------------


@router.get("/episodic-themes")
async def episodic_themes(
    days: int = Query(7, ge=1, le=90),
    organization_id: str = Query(_DEFAULT_ORG),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_internal),
) -> Any:
    """D23 episodic memory — theme clusters from the past N days.

    Groups recent episodes by source prefix (e.g. 'conv', 'seed', 'merged_pr')
    as a lightweight D23 classification surface.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)

    stmt = (
        select(Episode)
        .where(
            Episode.organization_id == organization_id,
            Episode.created_at >= cutoff,
        )
        .order_by(Episode.created_at.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    episodes = list(result.scalars().all())

    themes: dict[str, list[dict[str, Any]]] = {}
    for ep in episodes:
        # D23 classification via source prefix
        theme = (ep.source or "unknown").split(":")[0]
        themes.setdefault(theme, []).append({
            "id": ep.id,
            "summary": ep.summary,
            "persona": ep.persona,
            "importance": ep.importance,
            "created_at": ep.created_at.isoformat() if ep.created_at else None,
            "source": ep.source,
        })

    return success_response({
        "days": days,
        "organization_id": organization_id,
        "episode_count": len(episodes),
        "themes": {
            theme: {"count": len(items), "top": items[:5]}
            for theme, items in sorted(themes.items(), key=lambda x: -len(x[1]))
        },
    })


# ---------------------------------------------------------------------------
# GET /v1/memory/procedural-rules
# D40 procedural memory — rules for a persona domain
# ---------------------------------------------------------------------------


@router.get("/procedural-rules")
async def procedural_rules(
    domain: str = Query(
        ..., description="Persona domain or space/comma-separated keywords to match rules against"
    ),
    _auth: None = Depends(_require_internal),
) -> Any:
    """D40 procedural memory — procedural rules for a persona's domain.

    Reads apis/brain/data/procedural_memory.yaml via find_rules_for_context().
    Results sorted high → medium → low confidence.
    """
    keywords = [k.strip() for k in domain.replace(",", " ").split() if k.strip()]
    matched = proc_mem_svc.find_rules_for_context(keywords)

    return success_response({
        "domain": domain,
        "keywords_used": keywords,
        "rules": [
            {
                "id": r.id,
                "when": r.when,
                "do": r.do,
                "confidence": r.confidence,
                "applies_to": list(r.applies_to),
                "learned_at": r.learned_at.isoformat() if r.learned_at else None,
                "source": r.source,
            }
            for r in matched
        ],
        "count": len(matched),
    })


# ---------------------------------------------------------------------------
# GET /v1/memory/cross-context
# D55 cross-context — parallel retrieval across multiple org scopes
# ---------------------------------------------------------------------------


@router.get("/cross-context")
async def cross_context(
    query: str = Query(..., description="Search text"),
    contexts: str = Query(
        ..., description="Comma-separated organization IDs to search in parallel"
    ),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_internal),
) -> Any:
    """D55 cross-context — parallel retrieval across multiple organization scopes.

    Runs search_episodes() for each context in parallel via asyncio.gather.
    Scope-aware: results attributed per org_id so callers can apply RRF weights.
    """
    context_list = [c.strip() for c in contexts.split(",") if c.strip()]
    if not context_list:
        raise HTTPException(
            status_code=422, detail="contexts must be a non-empty comma-separated list"
        )

    async def _search_one(org_id: str) -> tuple[str, list[dict[str, Any]]]:
        try:
            results = await memory_svc.search_episodes(
                db,
                organization_id=org_id,
                query=query,
                limit=limit,
            )
            return org_id, [
                {
                    "id": ep.id,
                    "summary": ep.summary,
                    "source": ep.source,
                    "persona": ep.persona,
                    "importance": ep.importance,
                    "created_at": ep.created_at.isoformat() if ep.created_at else None,
                }
                for ep in results
            ]
        except Exception:
            logger.warning("cross-context search failed for org=%s", org_id, exc_info=True)
            return org_id, []

    pairs = await asyncio.gather(*[_search_one(org_id) for org_id in context_list])
    results_by_context = dict(pairs)

    return success_response({
        "query": query,
        "contexts": context_list,
        "results_by_context": results_by_context,
        "total_results": sum(len(v) for v in results_by_context.values()),
    })


# ---------------------------------------------------------------------------
# POST /v1/memory/remember
# D23 three-tier write — store a new memory entry
# ---------------------------------------------------------------------------


class RememberRequest(BaseModel):
    type: str = Field(..., pattern="^(episodic|semantic|procedural)$")
    content: dict[str, Any] = Field(
        ...,
        description="Must include 'summary' or 'text'. May include 'full_context', 'importance'.",
    )
    persona_id: str | None = None
    organization_id: str = _DEFAULT_ORG


@router.post("/remember")
async def remember(
    body: RememberRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_internal),
) -> Any:
    """D23 three-tier write — store a new memory entry of the specified type.

    Maps type → source prefix:
      episodic   → autopilot:episodic
      semantic   → autopilot:semantic
      procedural → autopilot:procedural
    """
    summary = (body.content.get("summary") or body.content.get("text") or "").strip()
    if not summary:
        raise HTTPException(status_code=422, detail="content must include 'summary' or 'text'")

    source = _TYPE_SOURCE[body.type]
    full_context = body.content.get("full_context") or body.content.get("context")
    importance = float(body.content.get("importance", 0.6))

    # Pass remaining content keys as metadata
    skip_keys = {"summary", "text", "full_context", "context", "importance"}
    extra_meta = {k: v for k, v in body.content.items() if k not in skip_keys}

    episode = await memory_svc.store_episode(
        db,
        organization_id=body.organization_id,
        source=source,
        summary=summary,
        full_context=full_context,
        persona=body.persona_id,
        importance=importance,
        metadata={"memory_type": body.type, **extra_meta},
    )
    await db.commit()

    return success_response(
        {
            "episode_id": episode.id,
            "type": body.type,
            "source": source,
            "organization_id": body.organization_id,
        },
        status_code=201,
    )
