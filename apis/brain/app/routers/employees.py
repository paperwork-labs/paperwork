"""Admin CRUD endpoints for the unified employees table (WS-82 PR-2a).

medallion: ops
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — used at runtime by FastAPI DI

from app.config import settings
from app.database import get_db
from app.models.conversation_mirror import ConversationMessageRecord, ConversationRecord
from app.models.employee import Employee
from app.models.epic_hierarchy import Epic
from app.models.transcript_episode import TranscriptEpisode
from app.models.workstream_board import WorkstreamDispatchLog
from app.schemas.base import error_response, success_response
from app.schemas.employee import EmployeeCreate, EmployeeListItem, EmployeeResponse, EmployeeUpdate
from app.services.naming_ceremony import run_naming_ceremony

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

router = APIRouter(prefix="/admin/employees", tags=["employees"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


def _employee_to_response(emp: Employee) -> dict[str, Any]:
    return EmployeeResponse(
        slug=emp.slug,
        kind=emp.kind,
        role_title=emp.role_title,
        team=emp.team,
        display_name=emp.display_name,
        tagline=emp.tagline,
        avatar_emoji=emp.avatar_emoji,
        voice_signature=emp.voice_signature,
        named_at=emp.named_at,
        named_by_self=emp.named_by_self,
        reports_to=emp.reports_to,
        manages=emp.manages or [],
        description=emp.description,
        default_model=emp.default_model,
        escalation_model=emp.escalation_model,
        escalate_if=emp.escalate_if or [],
        requires_tools=emp.requires_tools,
        daily_cost_ceiling_usd=(
            float(emp.daily_cost_ceiling_usd) if emp.daily_cost_ceiling_usd is not None else None
        ),
        owner_channel=emp.owner_channel,
        mode=emp.mode,
        tone_prefix=emp.tone_prefix,
        proactive_cadence=emp.proactive_cadence,
        max_output_tokens=emp.max_output_tokens,
        requests_per_minute=emp.requests_per_minute,
        cursor_description=emp.cursor_description,
        cursor_globs=emp.cursor_globs or [],
        cursor_always_apply=emp.cursor_always_apply,
        owned_rules=emp.owned_rules or [],
        owned_runbooks=emp.owned_runbooks or [],
        owned_workflows=emp.owned_workflows or [],
        owned_skills=emp.owned_skills or [],
        body_markdown=emp.body_markdown,
        created_at=emp.created_at,
        updated_at=emp.updated_at,
        metadata=emp.metadata_ or {},
    ).model_dump(mode="json")


def _employee_to_list_item(emp: Employee) -> dict[str, Any]:
    return EmployeeListItem(
        slug=emp.slug,
        kind=emp.kind,
        role_title=emp.role_title,
        team=emp.team,
        display_name=emp.display_name,
        tagline=emp.tagline,
        avatar_emoji=emp.avatar_emoji,
        named_at=emp.named_at,
        named_by_self=emp.named_by_self,
        reports_to=emp.reports_to,
    ).model_dump(mode="json")


@router.get("")
async def list_employees(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    result = await db.execute(select(Employee).order_by(Employee.team, Employee.slug))
    employees = result.scalars().all()
    return success_response({"employees": [_employee_to_list_item(e) for e in employees]})


def _transcript_activity_title(summary: str | None, user_message: str) -> str:
    s = (summary or "").strip()
    if s:
        return s
    text = user_message.strip().replace("\n", " ")
    if not text:
        return "(no title)"
    suf = "…" if len(text) > 120 else ""
    return text[:120] + suf


@router.get("/{slug}/activity")
async def get_employee_activity(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Recent dispatch log, mirrored conversations, and transcript mentions."""
    emp = await db.get(Employee, slug)
    if emp is None:
        return error_response(f"Employee '{slug}' not found", status_code=404)

    ddispatch = WorkstreamDispatchLog.dispatched_at
    dq = (
        select(Epic.id, Epic.title, Epic.status, ddispatch)
        .join(WorkstreamDispatchLog, WorkstreamDispatchLog.workstream_id == Epic.id)
        .where(Epic.owner_employee_slug == slug)
        .order_by(ddispatch.desc())
        .limit(20)
    )
    drows = (await db.execute(dq)).all()
    dispatches = [
        {
            "epic_id": rid,
            "title": ttl,
            "dispatched_at": ts.isoformat() if ts else None,
            "status": st,
        }
        for rid, ttl, st, ts in drows
    ]

    lcm = ConversationMessageRecord.created_at
    cq = (
        select(
            ConversationMessageRecord.conversation_id,
            ConversationRecord.title,
            func.max(lcm).label("last_message_at"),
            func.count().label("message_count"),
        )
        .join(
            ConversationRecord,
            ConversationRecord.id == ConversationMessageRecord.conversation_id,
        )
        .where(ConversationMessageRecord.persona_slug == slug)
        .group_by(ConversationMessageRecord.conversation_id, ConversationRecord.title)
        .order_by(func.max(lcm).desc())
        .limit(20)
    )
    crows = (await db.execute(cq)).all()
    conversations = [
        {
            "conversation_id": str(cid),
            "title": ttl,
            "last_message_at": last_at.isoformat() if last_at else None,
            "message_count": int(mc or 0),
        }
        for cid, ttl, last_at, mc in crows
    ]

    tq = (
        select(
            TranscriptEpisode.transcript_id,
            TranscriptEpisode.summary,
            TranscriptEpisode.user_message,
            TranscriptEpisode.ingested_at,
        )
        .where(TranscriptEpisode.persona_slugs.contains([slug]))
        .order_by(TranscriptEpisode.ingested_at.desc())
        .limit(20)
    )
    trows = (await db.execute(tq)).all()
    transcript_episodes = [
        {
            "transcript_id": tid,
            "title": _transcript_activity_title(summ, usr),
            "role": "mentioned",
            "created_at": ing.isoformat() if ing else None,
        }
        for tid, summ, usr, ing in trows
    ]

    payload = {
        "dispatches": dispatches,
        "conversations": conversations,
        "transcript_episodes": transcript_episodes,
    }
    return success_response(payload)


@router.get("/{slug}")
async def get_employee(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    emp = await db.get(Employee, slug)
    if emp is None:
        return error_response(f"Employee '{slug}' not found", status_code=404)
    return success_response({"employee": _employee_to_response(emp)})


@router.post("")
async def create_employee(
    body: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    existing = await db.get(Employee, body.slug)
    if existing is not None:
        return error_response(f"Employee '{body.slug}' already exists", status_code=409)

    emp = Employee(
        slug=body.slug,
        kind=body.kind,
        role_title=body.role_title,
        team=body.team,
        description=body.description,
        default_model=body.default_model,
        display_name=body.display_name,
        tagline=body.tagline,
        avatar_emoji=body.avatar_emoji,
        voice_signature=body.voice_signature,
        named_by_self=body.named_by_self,
        reports_to=body.reports_to,
        manages=body.manages,
        escalation_model=body.escalation_model,
        escalate_if=body.escalate_if,
        requires_tools=body.requires_tools,
        daily_cost_ceiling_usd=body.daily_cost_ceiling_usd,
        owner_channel=body.owner_channel,
        mode=body.mode,
        tone_prefix=body.tone_prefix,
        proactive_cadence=body.proactive_cadence,
        max_output_tokens=body.max_output_tokens,
        requests_per_minute=body.requests_per_minute,
        cursor_description=body.cursor_description,
        cursor_globs=body.cursor_globs,
        cursor_always_apply=body.cursor_always_apply,
        owned_rules=body.owned_rules,
        owned_runbooks=body.owned_runbooks,
        owned_workflows=body.owned_workflows,
        owned_skills=body.owned_skills,
        body_markdown=body.body_markdown,
        metadata_=body.metadata,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return success_response({"employee": _employee_to_response(emp)}, status_code=201)


@router.post("/{slug}/name-ceremony")
async def run_name_ceremony_for_employee(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Run LLM naming for an ai_persona; writes display_name, tagline, avatar_emoji."""
    emp = await db.get(Employee, slug)
    if emp is None:
        return error_response(f"Employee '{slug}' not found", status_code=404)
    if emp.kind == "human":
        return error_response(
            "Naming ceremony is not available for human employees.",
            status_code=400,
        )
    if emp.kind != "ai_persona":
        return error_response(
            "Naming ceremony only applies to ai_persona employees.",
            status_code=400,
        )
    try:
        result = await run_naming_ceremony(emp, db)
    except RuntimeError as exc:
        return error_response(str(exc), status_code=502)
    return success_response({"naming": result.model_dump(mode="json")})


@router.patch("/{slug}")
async def update_employee(
    slug: str,
    body: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    emp = await db.get(Employee, slug)
    if emp is None:
        return error_response(f"Employee '{slug}' not found", status_code=404)

    update_data = body.model_dump(exclude_unset=True)

    # metadata arrives as "metadata" but the column attr is metadata_
    if "metadata" in update_data:
        update_data["metadata_"] = update_data.pop("metadata")

    for field, value in update_data.items():
        setattr(emp, field, value)

    emp.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(emp)
    return success_response({"employee": _employee_to_response(emp)})
