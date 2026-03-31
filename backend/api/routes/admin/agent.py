"""
Agent Routes
============

API endpoints for the auto-ops agent dashboard:
- View pending approvals
- Approve/reject actions
- View agent action history
- Trigger manual agent run

Autonomy level (GET/PATCH /settings) is stored in Redis under
``agent:settings:autonomy_level`` so all API workers share one value.
Celery workers and other processes that need the live level should read
that key (UTF-8 string: full | safe | ask) or fall back to
``settings.AGENT_AUTONOMY_LEVEL`` from env when the key is unset.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import desc, distinct, func
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db, get_admin_user
from backend.models import User
from backend.models.agent_action import AgentAction

router = APIRouter(prefix="/agent", tags=["agent"])

logger = logging.getLogger(__name__)

AGENT_AUTONOMY_LEVELS: tuple[str, ...] = ("full", "safe", "ask")


class AgentActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    action_type: str
    action_name: str
    payload: Optional[dict]
    risk_level: str
    status: str
    reasoning: Optional[str]
    context_summary: Optional[str]
    task_id: Optional[str]
    result: Optional[dict]
    error: Optional[str]
    created_at: datetime
    approved_at: Optional[datetime]
    executed_at: Optional[datetime]
    completed_at: Optional[datetime]
    auto_approved: bool
    session_id: Optional[str]


class ApprovalRequest(BaseModel):
    approved: bool
    reason: Optional[str] = None


class AgentRunResponse(BaseModel):
    mode: str
    session_id: Optional[str]
    analysis: Optional[str]
    actions_taken: List[dict]
    actions_pending: List[dict]
    health_input: Optional[str]


class AgentSessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    started_at: datetime
    last_action_at: datetime
    action_count: int
    statuses: List[str]


class AgentSettingsResponse(BaseModel):
    autonomy_level: str
    available_levels: List[str]


class AgentSettingsUpdate(BaseModel):
    autonomy_level: Optional[str] = None


REDIS_KEY_AUTONOMY_LEVEL = "agent:settings:autonomy_level"


def _get_autonomy_level() -> str:
    """Get autonomy level from Redis, falling back to config default."""
    from backend.config import settings
    from backend.services.market.market_data_service import market_data_service

    redis = market_data_service.redis_client
    if redis:
        try:
            raw = redis.get(REDIS_KEY_AUTONOMY_LEVEL)
            if raw:
                level = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if level in AGENT_AUTONOMY_LEVELS:
                    return level
        except Exception as e:
            logger.warning("Failed to read agent autonomy level from Redis: %s", e)
    return settings.AGENT_AUTONOMY_LEVEL


def _set_autonomy_level(level: str) -> None:
    """Persist autonomy level to Redis for cross-worker consistency."""
    from backend.services.market.market_data_service import market_data_service

    redis = market_data_service.redis_client
    if redis:
        redis.set(REDIS_KEY_AUTONOMY_LEVEL, level)


@router.get("/settings", response_model=AgentSettingsResponse)
def get_agent_settings(
    _admin: User = Depends(get_admin_user),
):
    """Get current agent settings (reads from Redis for cross-worker consistency)."""
    return AgentSettingsResponse(
        autonomy_level=_get_autonomy_level(),
        available_levels=list(AGENT_AUTONOMY_LEVELS),
    )


@router.patch("/settings", response_model=AgentSettingsResponse)
def update_agent_settings(
    update: AgentSettingsUpdate,
    _admin: User = Depends(get_admin_user),
):
    """Update agent settings (persists to Redis for cross-worker consistency)."""
    if update.autonomy_level is not None:
        if update.autonomy_level not in AGENT_AUTONOMY_LEVELS:
            raise HTTPException(
                status_code=400, detail="Invalid autonomy level"
            )
        _set_autonomy_level(update.autonomy_level)

    return AgentSettingsResponse(
        autonomy_level=_get_autonomy_level(),
        available_levels=list(AGENT_AUTONOMY_LEVELS),
    )


@router.get("/actions", response_model=List[AgentActionResponse])
def list_agent_actions(
    status: Optional[str] = Query(None, description="Filter by status"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    session_id: Optional[str] = Query(None, description="Filter by session"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """List agent actions with optional filters."""
    query = db.query(AgentAction).order_by(desc(AgentAction.created_at))
    
    if status:
        query = query.filter(AgentAction.status == status)
    if risk_level:
        query = query.filter(AgentAction.risk_level == risk_level)
    if session_id:
        query = query.filter(AgentAction.session_id == session_id)
    
    actions = query.offset(offset).limit(limit).all()
    return actions


@router.get("/actions/pending", response_model=List[AgentActionResponse])
def list_pending_approvals(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """List actions pending human approval."""
    actions = (
        db.query(AgentAction)
        .filter(AgentAction.status == "pending_approval")
        .order_by(desc(AgentAction.created_at))
        .all()
    )
    return actions


@router.get("/sessions", response_model=List[AgentSessionSummary])
def list_agent_sessions(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """List distinct agent sessions with summary."""
    rows = (
        db.query(
            AgentAction.session_id.label("session_id"),
            func.min(AgentAction.created_at).label("started_at"),
            func.max(AgentAction.created_at).label("last_action_at"),
            func.count(AgentAction.id).label("action_count"),
            func.array_agg(distinct(AgentAction.status)).label("statuses"),
        )
        .filter(AgentAction.session_id.isnot(None))
        .group_by(AgentAction.session_id)
        .order_by(desc(func.min(AgentAction.created_at)))
        .limit(limit)
        .all()
    )
    return [
        AgentSessionSummary(
            session_id=row.session_id,
            started_at=row.started_at,
            last_action_at=row.last_action_at,
            action_count=int(row.action_count),
            statuses=list(row.statuses) if row.statuses is not None else [],
        )
        for row in rows
    ]


class SessionMessagesResponse(BaseModel):
    """Response for session messages endpoint."""
    session_id: str
    messages: List[dict]
    found: bool


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Get conversation messages for a specific session.

    Checks Redis first (for active sessions), then falls back to PostgreSQL
    (for sessions where the Redis cache has expired).

    Returns the full message history for resuming a past conversation.
    """
    from backend.services.market.market_data_service import market_data_service
    from backend.models.agent_message import load_conversation_from_db
    import json

    redis = market_data_service.redis_client
    if redis:
        try:
            redis_key = f"agent:conversation:{session_id}"
            raw = redis.get(redis_key)
            if raw:
                data = json.loads(
                    raw.decode("utf-8") if isinstance(raw, bytes) else raw
                )
                messages = data if isinstance(data, list) else []
                return SessionMessagesResponse(
                    session_id=session_id,
                    messages=messages,
                    found=True,
                )
        except Exception:
            logger.warning("Failed to load conversation from Redis for %s", session_id)

    try:
        messages = load_conversation_from_db(db, session_id)
        if messages:
            return SessionMessagesResponse(
                session_id=session_id,
                messages=messages,
                found=True,
            )
        return SessionMessagesResponse(
            session_id=session_id,
            messages=[],
            found=False,
        )
    except Exception:
        logger.exception("Failed to load conversation for session %s", session_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to load conversation",
        )


@router.get("/actions/{action_id}", response_model=AgentActionResponse)
def get_agent_action(
    action_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Get details of a specific agent action."""
    action = db.query(AgentAction).filter(AgentAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.post("/actions/{action_id}/approve", response_model=AgentActionResponse)
async def approve_action(
    action_id: int,
    request: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """Approve or reject a pending action."""
    action = db.query(AgentAction).filter(AgentAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    if action.status != "pending_approval":
        raise HTTPException(
            status_code=400, 
            detail=f"Action is not pending approval (status: {action.status})"
        )
    
    action.approved_at = datetime.utcnow()
    action.approved_by_id = current_user.id
    
    if request.approved:
        action.status = "approved"
        from backend.services.agent.brain import AgentBrain
        from backend.services.agent.tools import INLINE_ONLY_AGENT_TOOLS, TOOL_TO_CELERY_TASK
        from backend.tasks.celery_app import celery_app

        if action.action_type in INLINE_ONLY_AGENT_TOOLS:
            brain = AgentBrain(db=db)
            payload = action.payload if isinstance(action.payload, dict) else {}
            result = await brain._execute_safe_tool(action.action_type, payload)
            action.status = "completed"
            action.result = result
            action.executed_at = datetime.utcnow()
            action.completed_at = datetime.utcnow()
        else:
            task_path = TOOL_TO_CELERY_TASK.get(action.action_type)
            if task_path:
                try:
                    celery_result = celery_app.send_task(
                        task_path, kwargs=action.payload or {}
                    )
                    action.task_id = celery_result.id
                    action.status = "executing"
                    action.executed_at = datetime.utcnow()
                except Exception as e:
                    action.error = str(e)
                    action.status = "failed"
                    action.completed_at = datetime.utcnow()
            else:
                action.error = f"No Celery task mapped for action type: {action.action_type}"
                action.status = "failed"
                action.completed_at = datetime.utcnow()
    else:
        action.status = "rejected"
        if request.reason:
            action.error = f"Rejected: {request.reason}"
    
    db.commit()
    db.refresh(action)
    return action


@router.post("/run", response_model=AgentRunResponse)
async def trigger_agent_run(
    context: Optional[str] = Query(None, description="Additional context for the agent"),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Manually trigger an agent analysis and remediation run."""
    from backend.services.market.admin_health_service import AdminHealthService
    from backend.services.agent.brain import AgentBrain
    from backend.config import settings
    
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="LLM agent not configured (OPENAI_API_KEY missing)"
        )
    
    health_svc = AdminHealthService()
    health = health_svc.get_composite_health(db)
    
    brain = AgentBrain(db=db)
    result = await brain.analyze_and_act(health, context=context)
    
    return AgentRunResponse(
        mode="llm",
        session_id=result.get("session_id"),
        analysis=result.get("analysis"),
        actions_taken=result.get("actions_taken", []),
        actions_pending=result.get("actions_pending", []),
        health_input=result.get("health_input"),
    )


class ChatRequest(BaseModel):
    """Request body for agent chat."""

    message: str
    session_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def message_non_empty_stripped(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("message must be a string")
        s = v.strip()
        if not s:
            raise ValueError("message must not be empty")
        return s


class ChatResponse(BaseModel):
    """Response from agent chat."""
    session_id: str
    response: str
    tool_calls: List[dict]
    actions: List[dict]


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """
    Send a message to the agent and get a response.
    
    This endpoint supports multi-turn conversations. Pass the session_id
    from a previous response to continue the conversation.
    """
    from backend.services.agent.brain import AgentBrain
    from backend.config import settings
    
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="LLM agent not configured (OPENAI_API_KEY missing)"
        )
    
    brain = AgentBrain(db=db)

    if request.session_id:
        load_outcome = brain._load_conversation(request.session_id)
        if load_outcome == "unavailable":
            raise HTTPException(
                status_code=503,
                detail="Conversation store unavailable; try again later",
            )
        if load_outcome == "missing":
            raise HTTPException(
                status_code=404,
                detail="Conversation session not found or has expired",
            )

    try:
        result = await brain.chat(request.message)
    except Exception as e:
        logger.exception("Agent chat failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Agent processing error: {type(e).__name__}",
        )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    # New chat (no client session) or brain ended on a different session id: persist
    # a row so /agent/sessions and the session sidebar include this conversation.
    if not request.session_id or brain.session_id != request.session_id:
        try:
            now = datetime.utcnow()
            session_action = AgentAction(
                action_type="session_start",
                action_name="Chat session started",
                payload=None,
                risk_level="safe",
                status="completed",
                context_summary="Chat session started",
                session_id=brain.session_id,
                completed_at=now,
            )
            db.add(session_action)
            db.commit()
        except Exception as e:
            logger.warning("Failed to create session action: %s", e)
            db.rollback()

    return ChatResponse(
        session_id=result["session_id"],
        response=result.get("response", ""),
        tool_calls=result.get("tool_calls", []),
        actions=result.get("actions", []),
    )


@router.get("/stats")
def get_agent_stats(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Get agent statistics."""
    total = db.query(func.count(AgentAction.id)).scalar()
    pending = db.query(func.count(AgentAction.id)).filter(
        AgentAction.status == "pending_approval"
    ).scalar()
    completed = db.query(func.count(AgentAction.id)).filter(
        AgentAction.status == "completed"
    ).scalar()
    failed = db.query(func.count(AgentAction.id)).filter(
        AgentAction.status == "failed"
    ).scalar()
    auto_approved = db.query(func.count(AgentAction.id)).filter(
        AgentAction.auto_approved == True
    ).scalar()
    
    by_risk = dict(
        db.query(AgentAction.risk_level, func.count(AgentAction.id))
        .group_by(AgentAction.risk_level)
        .all()
    )
    
    by_action = dict(
        db.query(AgentAction.action_type, func.count(AgentAction.id))
        .group_by(AgentAction.action_type)
        .order_by(desc(func.count(AgentAction.id)))
        .limit(10)
        .all()
    )
    
    return {
        "total_actions": total,
        "pending_approval": pending,
        "completed": completed,
        "failed": failed,
        "auto_approved_rate": (auto_approved / total * 100) if total > 0 else 0,
        "by_risk_level": by_risk,
        "top_actions": by_action,
    }
