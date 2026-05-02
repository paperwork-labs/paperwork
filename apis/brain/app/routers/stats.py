"""Aggregated admin dashboard stats and attention items (WS-82).

medallion: ops
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse  # noqa: TC002 — return type
from sqlalchemy import func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — FastAPI DI

import app.services.conversations as conv_svc
from app.config import settings
from app.database import get_db
from app.models.employee import Employee
from app.models.epic_hierarchy import Epic, Goal, Sprint
from app.models.product import Product
from app.schemas.base import success_response

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


def _monorepo_root() -> Path:
    env = os.environ.get("REPO_ROOT", "").strip()
    if env:
        return Path(env)
    current = Path(__file__).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".cursor" / "rules").is_dir() and (candidate / "apis" / "brain").is_dir():
            return candidate
    raise RuntimeError("Paperwork monorepo root not found")


def _agent_dispatch_log_path() -> Path:
    env = os.environ.get("BRAIN_AGENT_DISPATCH_LOG_JSON", "").strip()
    if env:
        return Path(env)
    return _monorepo_root() / "apis" / "brain" / "data" / "agent_dispatch_log.json"


def _load_dispatch_rows() -> list[dict[str, Any]]:
    log_path = _agent_dispatch_log_path()
    if not log_path.is_file():
        return []
    try:
        raw = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    dispatches = raw.get("dispatches") if isinstance(raw, dict) else None
    if not isinstance(dispatches, list):
        return []
    rows = [d for d in dispatches if isinstance(d, dict)]
    rows.sort(key=lambda d: str(d.get("dispatched_at") or ""), reverse=True)
    return rows


def _dispatch_success_flag(row: dict[str, Any]) -> bool | None:
    outcome = row.get("outcome")
    if not isinstance(outcome, dict):
        return None
    merged_at = outcome.get("merged_at")
    if not merged_at:
        return None
    return outcome.get("reverted") is not True


def _dispatch_metrics(rows: list[dict[str, Any]]) -> tuple[int, int, str | None]:
    total = len(rows)
    today_prefix = datetime.now(UTC).strftime("%Y-%m-%d")
    today_n = sum(1 for r in rows if str(r.get("dispatched_at") or "").startswith(today_prefix))
    last = str(rows[0]["dispatched_at"]) if rows and rows[0].get("dispatched_at") else None
    return total, today_n, last


_TERMINAL_SPRINT = ("shipped", "complete", "done", "closed")
_DONE_EPIC = ("completed", "done", "shipped")


@router.get("/stats")
async def admin_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Roll-up counts across Brain DB tables + canonical JSON stores."""
    prod_total = int((await db.scalar(select(func.count()).select_from(Product))) or 0)
    prod_active = int(
        (await db.scalar(select(func.count()).where(Product.status == "active"))) or 0,
    )
    emp_total = int((await db.scalar(select(func.count()).select_from(Employee))) or 0)
    emp_human = int((await db.scalar(select(func.count()).where(Employee.kind == "human"))) or 0)
    emp_ai = max(0, emp_total - emp_human)

    ep_total = int((await db.scalar(select(func.count()).select_from(Epic))) or 0)
    ep_blocked = int(
        (await db.scalar(select(func.count()).where(func.lower(Epic.status) == "blocked"))) or 0,
    )
    ep_prog = int(
        (
            await db.scalar(
                select(func.count()).where(func.lower(Epic.status) == "in_progress"),
            )
        )
        or 0,
    )
    ep_done = int(
        (
            await db.scalar(
                select(func.count()).where(func.lower(Epic.status).in_(_DONE_EPIC)),
            )
        )
        or 0,
    )

    sp_total = int((await db.scalar(select(func.count()).select_from(Sprint))) or 0)
    sp_active = int(
        (
            await db.scalar(
                select(func.count()).where(
                    not_(func.lower(Sprint.status).in_(_TERMINAL_SPRINT)),
                ),
            )
        )
        or 0,
    )

    def _conv_metrics() -> tuple[int, int]:
        return conv_svc.admin_conversation_counts()

    try:
        rows = await asyncio.to_thread(_load_dispatch_rows)
    except Exception:
        rows = []
    try:
        conv_total, conv_today = await asyncio.to_thread(_conv_metrics)
    except Exception:
        conv_total, conv_today = 0, 0
    _, disp_today, last_disp = _dispatch_metrics(rows)

    payload = {
        "products": {"total": prod_total, "active": prod_active},
        "employees": {"total": emp_total, "ai": emp_ai, "human": emp_human},
        "epics": {
            "total": ep_total,
            "in_progress": ep_prog,
            "completed": ep_done,
            "blocked": ep_blocked,
        },
        "sprints": {"total": sp_total, "active": sp_active},
        "conversations": {"total": conv_total, "today": conv_today},
        "dispatches_today": disp_today,
        "last_dispatch_at": last_disp,
    }
    return success_response(payload)


@router.get("/attention")
async def admin_dashboard_attention(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Short lists of blocked work, stale cadence, inbox, and failed dispatches."""
    stale_cutoff = datetime.now(UTC) - timedelta(days=7)

    blocked_res = await db.execute(
        select(Epic, Goal)
        .outerjoin(Goal, Epic.goal_id == Goal.id)
        .where(func.lower(Epic.status) == "blocked")
        .order_by(Epic.created_at.desc())
        .limit(5),
    )
    blocked_epics: list[dict[str, Any]] = []
    for epic, goal in blocked_res.all():
        blocked_epics.append(
            {
                "id": epic.id,
                "title": epic.title,
                "goal_objective": goal.objective if goal else "",
            },
        )

    stale_res = await db.execute(
        select(Sprint, Epic)
        .join(Epic, Sprint.epic_id == Epic.id)
        .where(
            not_(func.lower(Sprint.status).in_(_TERMINAL_SPRINT)),
            or_(Epic.last_activity.is_(None), Epic.last_activity < stale_cutoff),
        )
        .order_by(Epic.last_activity.asc().nulls_first())
        .limit(5),
    )
    stale_sprints: list[dict[str, Any]] = []
    for sp, epic in stale_res.all():
        la = epic.last_activity
        stale_sprints.append(
            {
                "id": sp.id,
                "title": sp.title,
                "epic_title": epic.title,
                "last_activity_at": la.strftime("%Y-%m-%dT%H:%M:%SZ") if la else None,
            },
        )

    unreplied_page = conv_svc.list_conversations(status_filter="needs-action", limit=5)
    unreplied_conversations = [
        {
            "id": c.id,
            "title": c.title,
            "updated_at": c.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        for c in unreplied_page.items
    ]

    try:
        rows = await asyncio.to_thread(_load_dispatch_rows)
    except Exception:
        rows = []
    failed_dispatches: list[dict[str, Any]] = []
    for r in rows:
        if _dispatch_success_flag(r) is not False:
            continue
        failed_dispatches.append(
            {
                "dispatched_at": r.get("dispatched_at"),
                "persona_slug": r.get("persona_slug") or r.get("persona"),
                "task_summary": r.get("task_summary"),
                "pr_number": r.get("pr_number"),
            },
        )
        if len(failed_dispatches) >= 5:
            break

    payload = {
        "blocked_epics": blocked_epics,
        "stale_sprints": stale_sprints,
        "unreplied_conversations": unreplied_conversations,
        "failed_dispatches": failed_dispatches,
    }
    return success_response(payload)
