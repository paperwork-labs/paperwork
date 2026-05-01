"""Admin API — domain-persona PR review for Brain Autopilot cheap-agent output.

Resolves the persona YAML spec, retrieves relevant memory (same hybrid search as
``GET /api/v1/memory/recall-decisions``), and returns a structured review.
LLM synthesis is stubbed until Wave follow-up.

medallion: brain-autopilot
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.personas import PersonaSpec, get_spec, list_specs
from app.redis import get_redis
from app.routers.admin import _require_admin
from app.schemas.base import success_response
from app.schemas.persona_review import (
    MemoryCitation,
    PersonaReviewComment,
    PersonaReviewRequest,
    PersonaReviewResult,
)
from app.services import memory as memory_svc

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin", tags=["admin"])

_DEFAULT_ORG = "paperwork-labs"
_MEMORY_QUERY_LIMIT = 8


def _get_redis_optional() -> Redis | None:
    try:
        return get_redis()
    except RuntimeError:
        return None


def _resolve_persona_spec(persona_id: str) -> PersonaSpec:
    """Return the persona spec or raise 404."""
    try:
        spec = get_spec(persona_id.strip())
    except ValueError:
        spec = None
    if spec is None:
        known = ", ".join(sorted(s.name for s in list_specs()))
        raise HTTPException(
            status_code=404,
            detail=f"Unknown persona_id={persona_id!r}. Registered specs: {known or '(none)'}",
        )
    return spec


def _stub_review(
    *,
    persona_id: str,
    citations: list[MemoryCitation],
) -> PersonaReviewResult:
    """Placeholder until LLM-backed synthesis (provider + prompt TBD).

    TODO(brain-autopilot): Call configured LLM with persona voice + domain,
    diff_summary, and serialized memory citations; validate structured output.
    """
    return PersonaReviewResult(
        persona_id=persona_id,
        verdict="comment",
        comments=[
            PersonaReviewComment(
                file="*",
                line=None,
                body=(
                    "Stub review: wire LLM with persona tone_prefix and domain (description) "
                    "plus memory context."
                ),
                severity="info",
            ),
        ],
        memory_citations=citations,
    )


@router.post("/persona-review")
async def persona_pr_review(
    body: PersonaReviewRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Run a persona-scoped PR review using memory-backed context."""
    spec = _resolve_persona_spec(body.persona_id)
    domain = spec.description
    voice = spec.tone_prefix or ""

    redis_client = _get_redis_optional()
    fatigue_ids = await memory_svc.get_fatigue_ids(redis_client, _DEFAULT_ORG)

    memory_query_parts = [
        f"PR #{body.pr_number}",
        domain,
        voice[:500] if voice else "",
        body.diff_summary,
    ]
    memory_query = "\n".join(p for p in memory_query_parts if p)

    episodes = await memory_svc.search_episodes(
        db,
        organization_id=_DEFAULT_ORG,
        query=memory_query,
        limit=_MEMORY_QUERY_LIMIT,
        fatigue_ids=fatigue_ids,
    )

    citations = [
        MemoryCitation(
            source=str(ep.source or "episode"),
            snippet=(ep.summary or "")[:500],
        )
        for ep in episodes
    ]

    result = _stub_review(persona_id=spec.name, citations=citations)
    return success_response(result.model_dump(mode="json"))
