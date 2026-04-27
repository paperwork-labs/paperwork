"""Brain learning observability routes (`/api/v1/admin/brain/learning/*`)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, and_, case, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.episode import Episode
from app.routers.admin import _require_admin, _require_learning_dashboard
from app.schemas.base import success_response

router = APIRouter(prefix="/admin/brain/learning", tags=["admin-learning"])
_ORG = "paperwork-labs"

def _base(org: str) -> Any:
    return and_(Episode.organization_id == org, Episode.source != "model_router")

def _lesson() -> Any:
    return or_(
        Episode.metadata_.contains({"tags": ["lesson_extracted"]}),
        Episode.metadata_.has_key("lesson_extracted"),
    )

def _topic() -> Any:
    mt = Episode.metadata_.op("->>")("topic")
    return func.coalesce(
        func.nullif(mt, ""),
        Episode.product,
        func.nullif(func.split_part(Episode.source, ":", 1), ""),
        literal("uncategorized"),
    )

def _actor() -> Any:
    return func.coalesce(Episode.persona, Episode.user_id, Episode.channel, literal("unknown"))

def _tags(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("tags")
    if isinstance(raw, list):
        return [str(x) for x in raw if x is not None]
    return [raw] if isinstance(raw, str) and raw else []

def _row(ep: Episode) -> dict[str, Any]:
    meta = ep.metadata_ or {}
    topic = meta.get("topic") or ep.product or (ep.source.split(":", 1)[0] if ep.source else "") or "uncategorized"
    return {
        "id": ep.id,
        "created_at": ep.created_at.isoformat() if ep.created_at else None,
        "actor": ep.persona or ep.user_id or ep.channel or "unknown",
        "event_type": ep.source,
        "summary": ep.summary,
        "tags": _tags(meta),
        "topic": str(topic),
        "persona": ep.persona,
        "product": ep.product,
        "verified": ep.verified,
    }

@router.get("/summary")
async def learning_summary(
    organization_id: str = Query(_ORG),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
    _learning: None = Depends(_require_learning_dashboard),
):
    now = datetime.now(UTC)
    start = now - timedelta(days=7)
    base = and_(_base(organization_id), Episode.created_at >= start)

    total = int((await db.execute(select(func.count()).select_from(Episode).where(base))).scalar() or 0)
    tagged = int(
        (await db.execute(select(func.count()).select_from(Episode).where(and_(base, _lesson())))).scalar() or 0
    )
    rate = round(100.0 * tagged / total, 2) if total else 0.0

    te, ae = _topic(), _actor()
    tops = (
        await db.execute(
            select(te, func.count())
            .where(base)
            .group_by(te)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    ags = (
        await db.execute(
            select(ae, func.count())
            .where(base)
            .group_by(ae)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    distinct = int((await db.execute(select(func.count(func.distinct(ae))).where(base))).scalar() or 0)

    return success_response(
        {
            "as_of": now.isoformat(),
            "window_days": 7,
            "episodes_7d": total,
            "lessons_captured_7d": tagged,
            "lesson_rate_pct": rate,
            "distinct_agents_7d": distinct,
            "top_topics": [{"topic": r[0], "count": int(r[1])} for r in tops],
            "top_agents": [{"agent": r[0], "count": int(r[1])} for r in ags],
        }
    )

@router.get("/episodes")
async def learning_episodes(
    limit: int = Query(50, ge=1, le=50),
    offset: int = Query(0, ge=0),
    topic: str | None = Query(None),
    organization_id: str = Query(_ORG),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
    _learning: None = Depends(_require_learning_dashboard),
):
    te = _topic()
    filt: Any = _base(organization_id)
    if topic and topic.strip():
        filt = and_(filt, te == topic.strip())
    total = int((await db.execute(select(func.count()).select_from(Episode).where(filt))).scalar() or 0)
    rows = (
        await db.execute(
            select(Episode).where(filt).order_by(Episode.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return success_response(
        {"total": total, "limit": limit, "offset": offset, "episodes": [_row(e) for e in rows]}
    )

@router.get("/lessons")
async def learning_lessons(
    organization_id: str = Query(_ORG),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
    _learning: None = Depends(_require_learning_dashboard),
):
    key = func.coalesce(
        func.nullif(Episode.metadata_.op("->>")("lesson_id"), ""),
        func.md5(cast(Episode.summary, String)),
    )
    filt = and_(_base(organization_id), _lesson())
    if search and search.strip():
        filt = and_(filt, func.lower(Episode.summary).like(f"%{search.strip().lower()}%"))
    fs = func.min(Episode.created_at).label("first_seen")
    ls = func.max(Episode.created_at).label("last_seen")
    lc = func.max(case((Episode.verified.is_(True), Episode.created_at), else_=None)).label("last_confirmed")
    stmt = (
        select(key, func.min(Episode.summary), fs, ls, lc)
        .where(filt)
        .group_by(key)
        .order_by(ls.desc())
        .limit(limit)
    )
    out: list[dict[str, Any]] = []
    for r in (await db.execute(stmt)).all():
        txt, a, b, c = r[1], r[2], r[3], r[4]
        out.append(
            {
                "lesson_key": str(r[0]),
                "lesson": (txt or "")[:2000],
                "first_seen_at": a.isoformat() if a else None,
                "last_seen_at": b.isoformat() if b else None,
                "last_confirmed_at": c.isoformat() if c else None,
            }
        )
    return success_response({"count": len(out), "lessons": out})

@router.get("/timeline")
async def learning_timeline(
    days: int = Query(30, ge=1, le=90),
    organization_id: str = Query(_ORG),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
    _learning: None = Depends(_require_learning_dashboard),
):
    today = datetime.now(UTC).date()
    start_d = today - timedelta(days=days - 1)
    rs = datetime(start_d.year, start_d.month, start_d.day, tzinfo=UTC)
    re = datetime(today.year, today.month, today.day, tzinfo=UTC) + timedelta(days=1)
    bucket = func.date_trunc("day", Episode.created_at)
    b = _base(organization_id)

    async def counts(extra: Any | None = None) -> dict[date | None, int]:
        stmt = select(bucket, func.count()).where(and_(b, Episode.created_at >= rs, Episode.created_at < re))
        if extra is not None:
            stmt = stmt.where(extra)
        stmt = stmt.group_by(bucket)
        return {x[0].date() if x[0] else None: int(x[1]) for x in (await db.execute(stmt)).all()}

    ep = await counts()
    les = await counts(_lesson())
    ae = _actor()
    ag_stmt = (
        select(bucket, func.count(func.distinct(ae)))
        .where(and_(b, Episode.created_at >= rs, Episode.created_at < re))
        .group_by(bucket)
    )
    ag = {x[0].date() if x[0] else None: int(x[1]) for x in (await db.execute(ag_stmt)).all()}
    series = [
        {
            "date": (d := start_d + timedelta(days=i)).isoformat(),
            "episodes": ep.get(d, 0),
            "lessons": les.get(d, 0),
            "agents_involved": ag.get(d, 0),
        }
        for i in range(days)
    ]
    return success_response({"days": days, "series": series})
