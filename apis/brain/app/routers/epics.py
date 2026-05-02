"""Admin CRUD endpoints for the Goal → Epic → Sprint → Task hierarchy.

Brain is the single source of truth; Studio reads these via the admin API.
All endpoints are protected by the shared _require_admin dependency.

medallion: ops
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.epic_hierarchy import Epic, Goal, Sprint, Task
from app.routers.admin import _require_admin
from app.schemas.base import success_response
from app.schemas.epic_hierarchy import (
    EpicCreate,
    EpicResponse,
    EpicUpdate,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    SprintCreate,
    SprintResponse,
    SprintUpdate,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------


@router.get("/goals")
async def list_goals(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """List all goals, optionally filtered by status."""
    stmt = select(Goal).options(selectinload(Goal.epics))
    if status:
        stmt = stmt.where(Goal.status == status)
    stmt = stmt.order_by(Goal.created_at.desc())
    result = await db.execute(stmt)
    goals = result.scalars().all()
    return success_response([GoalResponse.model_validate(g).model_dump() for g in goals])


@router.post("/goals")
async def create_goal(
    body: GoalCreate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Create a new goal."""
    existing = await db.get(Goal, body.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Goal id={body.id!r} already exists")
    goal = Goal(
        id=body.id,
        objective=body.objective,
        horizon=body.horizon,
        metric=body.metric,
        target=body.target,
        status=body.status,
        owner_employee_slug=body.owner_employee_slug,
        written_at=body.written_at,
        review_cadence_days=body.review_cadence_days,
        notes=body.notes,
        metadata_=body.metadata,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return success_response(GoalResponse.model_validate(goal).model_dump(), status_code=201)


@router.patch("/goals/{goal_id}")
async def update_goal(
    goal_id: str,
    body: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Partially update a goal."""
    goal = await db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal id={goal_id!r} not found")
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        attr = "metadata_" if field == "metadata" else field
        setattr(goal, attr, value)
    await db.commit()
    await db.refresh(goal)
    return success_response(GoalResponse.model_validate(goal).model_dump())


# ---------------------------------------------------------------------------
# Epics
# ---------------------------------------------------------------------------


@router.get("/epics")
async def list_epics(
    goal_id: str | None = Query(None),
    status: str | None = Query(None),
    owner: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """List epics with optional filters for goal_id, status, and owner."""
    stmt = select(Epic).options(selectinload(Epic.sprints).selectinload(Sprint.tasks))
    if goal_id:
        stmt = stmt.where(Epic.goal_id == goal_id)
    if status:
        stmt = stmt.where(Epic.status == status)
    if owner:
        stmt = stmt.where(Epic.owner_employee_slug == owner)
    stmt = stmt.order_by(Epic.priority)
    result = await db.execute(stmt)
    epics = result.scalars().all()
    return success_response([EpicResponse.model_validate(e).model_dump() for e in epics])


@router.get("/epics/{epic_id}")
async def get_epic(
    epic_id: str,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Fetch a single epic with its nested sprints and tasks."""
    stmt = (
        select(Epic)
        .where(Epic.id == epic_id)
        .options(selectinload(Epic.sprints).selectinload(Sprint.tasks))
    )
    result = await db.execute(stmt)
    epic = result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail=f"Epic id={epic_id!r} not found")
    return success_response(EpicResponse.model_validate(epic).model_dump())


@router.post("/epics")
async def create_epic(
    body: EpicCreate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Create a new epic."""
    existing = await db.get(Epic, body.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Epic id={body.id!r} already exists")
    epic = Epic(
        id=body.id,
        title=body.title,
        goal_id=body.goal_id,
        owner_employee_slug=body.owner_employee_slug,
        status=body.status,
        priority=body.priority,
        percent_done=body.percent_done,
        brief_tag=body.brief_tag,
        description=body.description,
        related_plan=body.related_plan,
        blockers=body.blockers,
        last_activity=body.last_activity,
        last_dispatched_at=body.last_dispatched_at,
        metadata_=body.metadata,
    )
    db.add(epic)
    await db.commit()
    await db.refresh(epic)
    return success_response(EpicResponse.model_validate(epic).model_dump(), status_code=201)


@router.patch("/epics/{epic_id}")
async def update_epic(
    epic_id: str,
    body: EpicUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Partially update an epic."""
    epic = await db.get(Epic, epic_id)
    if not epic:
        raise HTTPException(status_code=404, detail=f"Epic id={epic_id!r} not found")
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        attr = "metadata_" if field == "metadata" else field
        setattr(epic, attr, value)
    await db.commit()
    await db.refresh(epic)
    return success_response(EpicResponse.model_validate(epic).model_dump())


# ---------------------------------------------------------------------------
# Sprints
# ---------------------------------------------------------------------------


@router.get("/sprints")
async def list_sprints(
    epic_id: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """List sprints with optional filters for epic_id and status."""
    stmt = select(Sprint).options(selectinload(Sprint.tasks))
    if epic_id:
        stmt = stmt.where(Sprint.epic_id == epic_id)
    if status:
        stmt = stmt.where(Sprint.status == status)
    stmt = stmt.order_by(Sprint.epic_id, Sprint.ordinal)
    result = await db.execute(stmt)
    sprints = result.scalars().all()
    return success_response([SprintResponse.model_validate(s).model_dump() for s in sprints])


@router.post("/sprints")
async def create_sprint(
    body: SprintCreate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Create a sprint under an existing epic."""
    epic = await db.get(Epic, body.epic_id)
    if not epic:
        raise HTTPException(status_code=404, detail=f"Epic id={body.epic_id!r} not found")
    existing = await db.get(Sprint, body.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Sprint id={body.id!r} already exists")
    sprint = Sprint(
        id=body.id,
        epic_id=body.epic_id,
        title=body.title,
        goal=body.goal,
        status=body.status,
        start_date=body.start_date,
        end_date=body.end_date,
        lead_employee_slug=body.lead_employee_slug,
        ordinal=body.ordinal,
        metadata_=body.metadata,
    )
    db.add(sprint)
    await db.commit()
    await db.refresh(sprint)
    return success_response(SprintResponse.model_validate(sprint).model_dump(), status_code=201)


@router.patch("/sprints/{sprint_id}")
async def update_sprint(
    sprint_id: str,
    body: SprintUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Partially update a sprint (start, complete, re-order, etc.)."""
    sprint = await db.get(Sprint, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail=f"Sprint id={sprint_id!r} not found")
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        attr = "metadata_" if field == "metadata" else field
        setattr(sprint, attr, value)
    await db.commit()
    await db.refresh(sprint)
    return success_response(SprintResponse.model_validate(sprint).model_dump())


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@router.get("/tasks")
async def list_tasks(
    sprint_id: str | None = Query(None),
    epic_id: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """List tasks with optional filters for sprint_id, epic_id, and status."""
    stmt = select(Task)
    if sprint_id:
        stmt = stmt.where(Task.sprint_id == sprint_id)
    if epic_id:
        stmt = stmt.where(Task.epic_id == epic_id)
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.ordinal.nullslast(), Task.created_at)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return success_response([TaskResponse.model_validate(t).model_dump() for t in tasks])


@router.post("/tasks")
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Create a task, optionally linked to a sprint and/or epic."""
    existing = await db.get(Task, body.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Task id={body.id!r} already exists")
    task = Task(
        id=body.id,
        sprint_id=body.sprint_id,
        epic_id=body.epic_id,
        title=body.title,
        status=body.status,
        github_pr=body.github_pr,
        github_pr_url=body.github_pr_url,
        owner_employee_slug=body.owner_employee_slug,
        assignee=body.assignee,
        brief_tag=body.brief_tag,
        ordinal=body.ordinal,
        estimated_minutes=body.estimated_minutes,
        merged_at=body.merged_at,
        metadata_=body.metadata,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return success_response(TaskResponse.model_validate(task).model_dump(), status_code=201)


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: str,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Partially update a task (status, assignee, PR link, etc.)."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task id={task_id!r} not found")
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        attr = "metadata_" if field == "metadata" else field
        setattr(task, attr, value)
    await db.commit()
    await db.refresh(task)
    return success_response(TaskResponse.model_validate(task).model_dump())
