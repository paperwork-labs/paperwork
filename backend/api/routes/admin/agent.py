"""
Agent Routes
============

API endpoints for the auto-ops agent dashboard:
- View pending approvals
- Approve/reject actions
- View agent action history
- Trigger manual agent run
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db, get_current_user
from backend.models import User
from backend.models.agent_action import AgentAction

router = APIRouter(prefix="/agent", tags=["agent"])


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


@router.get("/actions", response_model=List[AgentActionResponse])
def list_agent_actions(
    status: Optional[str] = Query(None, description="Filter by status"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    session_id: Optional[str] = Query(None, description="Filter by session"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
):
    """List actions pending human approval."""
    actions = (
        db.query(AgentAction)
        .filter(AgentAction.status == "pending_approval")
        .order_by(desc(AgentAction.created_at))
        .all()
    )
    return actions


@router.get("/actions/{action_id}", response_model=AgentActionResponse)
def get_agent_action(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details of a specific agent action."""
    action = db.query(AgentAction).filter(AgentAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.post("/actions/{action_id}/approve", response_model=AgentActionResponse)
def approve_action(
    action_id: int,
    request: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        from backend.services.agent.tools import TOOL_TO_CELERY_TASK
        from backend.tasks.celery_app import celery_app
        
        task_path = TOOL_TO_CELERY_TASK.get(action.action_type)
        if task_path:
            try:
                result = celery_app.send_task(task_path, kwargs=action.payload or {})
                action.task_id = result.id
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
    current_user: User = Depends(get_current_user),
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


@router.get("/stats")
def get_agent_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get agent statistics."""
    from sqlalchemy import func
    
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
