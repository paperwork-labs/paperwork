"""Admin CRUD endpoints for the unified employees table (WS-82 PR-2a).

medallion: brain
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.employee import Employee
from app.schemas.base import error_response, success_response
from app.schemas.employee import EmployeeCreate, EmployeeListItem, EmployeeResponse, EmployeeUpdate

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
        daily_cost_ceiling_usd=float(emp.daily_cost_ceiling_usd) if emp.daily_cost_ceiling_usd is not None else None,
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
) -> "JSONResponse":
    result = await db.execute(select(Employee).order_by(Employee.team, Employee.slug))
    employees = result.scalars().all()
    return success_response({"employees": [_employee_to_list_item(e) for e in employees]})


@router.get("/{slug}")
async def get_employee(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> "JSONResponse":
    emp = await db.get(Employee, slug)
    if emp is None:
        return error_response(f"Employee '{slug}' not found", status_code=404)
    return success_response({"employee": _employee_to_response(emp)})


@router.post("")
async def create_employee(
    body: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> "JSONResponse":
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


@router.patch("/{slug}")
async def update_employee(
    slug: str,
    body: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> "JSONResponse":
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
