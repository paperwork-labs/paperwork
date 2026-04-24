"""
AxiomFolio V1 - Clean Admin Routes
System administration endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta, timezone
import secrets

from pydantic import BaseModel, EmailStr

# dependencies
from app.database import get_db
from app.models.user import User, UserRole
from app.models.user_invite import UserInvite
from app.api.dependencies import get_admin_user
from app.api.rate_limit import limiter
from app.models.market_data import MarketRegime, MarketSnapshot, JobRun

logger = logging.getLogger(__name__)

router = APIRouter()


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = "viewer"
    expires_in_days: int = 7


class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


def _parse_role(role: str | None) -> UserRole:
    raw = (role or "").strip().lower()
    if not raw:
        return UserRole.VIEWER
    legacy = {
        "admin": UserRole.OWNER,
        "user": UserRole.ANALYST,
        "readonly": UserRole.VIEWER,
    }
    if raw in legacy:
        return legacy[raw]
    for r in UserRole:
        if raw == r.value or raw == r.name.lower():
            return r
    raise HTTPException(status_code=400, detail=f"Invalid role: {role}")


def _role_value(role_obj: Any) -> str:
    """Normalize role payloads coming from enum, raw string, or legacy rows."""
    if role_obj is None:
        return UserRole.VIEWER.value
    if isinstance(role_obj, UserRole):
        return role_obj.value
    raw = str(role_obj).strip()
    if not raw:
        return UserRole.VIEWER.value
    lowered = raw.lower()
    legacy_map = {
        "admin": UserRole.OWNER.value,
        "user": UserRole.ANALYST.value,
        "readonly": UserRole.VIEWER.value,
    }
    if lowered in legacy_map:
        return legacy_map[lowered]
    for r in UserRole:
        if lowered == r.value or lowered == r.name.lower():
            return r.value
    return lowered


@router.get("/users")
async def list_users(
    q: Optional[str] = Query(None, description="Filter by email or username"),
    role: Optional[str] = Query(None, description="Role filter"),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all users (admin only)."""
    try:
        query = db.query(User)
        if q:
            like = f"%{q.strip()}%"
            query = query.filter((User.email.ilike(like)) | (User.username.ilike(like)))
        if role:
            query = query.filter(User.role == _parse_role(role))
        users = query.order_by(User.created_at.desc()).all()

        return {
            "users": [_user_admin_payload(user) for user in users],
            "total_users": len(users),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Admin users list error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/invites")
async def list_user_invites(
    admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List active user invites (admin only)."""
    invites = (
        db.query(UserInvite)
        .order_by(UserInvite.created_at.desc())
        .all()
    )
    return {
        "invites": [
            {
                "id": inv.id,
                "email": inv.email,
                "role": _role_value(inv.role),
                "token": inv.token if not inv.accepted_at and inv.expires_at > datetime.now(timezone.utc) else None,
                "expires_at": inv.expires_at.isoformat(),
                "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
                "created_at": inv.created_at.isoformat(),
            }
            for inv in invites
        ]
    }


@router.post("/users/invite")
@limiter.limit("10/minute")
async def invite_user(
    request: Request,
    payload: InviteUserRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create an email invite for a user (admin only)."""
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="User already exists")
    role = _parse_role(payload.role)
    expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, min(payload.expires_in_days, 30)))
    token = secrets.token_urlsafe(32)
    existing_invite = (
        db.query(UserInvite)
        .filter(UserInvite.email == email)
        .first()
    )
    if existing_invite:
        is_active = (
            existing_invite.accepted_at is None
            and existing_invite.expires_at >= datetime.now(timezone.utc)
        )
        if is_active:
            raise HTTPException(status_code=409, detail="Active invite already exists for this email")
        # Recycle an expired/used invite row so email uniqueness remains intact.
        existing_invite.role = role
        existing_invite.token = token
        existing_invite.created_by_user_id = admin_user.id
        existing_invite.expires_at = expires_at
        existing_invite.accepted_at = None
        invite = existing_invite
    else:
        invite = UserInvite(
            email=email,
            role=role,
            token=token,
            created_by_user_id=admin_user.id,
            expires_at=expires_at,
        )
        db.add(invite)
    db.commit()
    db.refresh(invite)
    return {
        "id": invite.id,
        "email": invite.email,
        "role": _role_value(invite.role),
        "token": invite.token,
        "expires_at": invite.expires_at.isoformat(),
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update user role/active status (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.role is not None:
        user.role = _parse_role(payload.role)
    if payload.is_active is not None:
        user.is_active = bool(payload.is_active)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": _role_value(user.role),
        "is_active": user.is_active,
    }


def _user_admin_payload(user: User) -> Dict[str, Any]:
    """Serialize user for admin user-management responses."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": _role_value(user.role),
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_approved": user.is_approved,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "full_name": user.full_name,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/users/{user_id}/approve")
@limiter.limit("10/minute")
async def approve_user(
    request: Request,
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Approve a user account (admin only). Sets is_approved to True."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = True
    db.commit()
    db.refresh(user)
    return _user_admin_payload(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Fully delete a user from the database (admin only). Cannot delete yourself."""
    if admin_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        db.delete(user)
        db.commit()
    except Exception as exc:
        from sqlalchemy.exc import IntegrityError
        if isinstance(exc, IntegrityError):
            db.rollback()
            logger.warning("delete_user failed for user_id=%d: %s", user_id, exc)
            raise HTTPException(
                status_code=409,
                detail="Cannot delete user: related records exist. Deactivate the account instead.",
            )
        db.rollback()
        raise
    return {
        "message": "User deleted successfully",
        "deleted": True,
        "id": user_id,
    }


@router.get("/system-health")
async def system_health_summary(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Aggregated system health: regime, coverage freshness, pipeline status, recent errors."""
    from sqlalchemy import select, func as sqlfunc

    # Regime
    regime_row = db.execute(
        select(MarketRegime).order_by(MarketRegime.as_of_date.desc()).limit(1)
    ).scalar_one_or_none()
    regime = {
        "state": regime_row.regime_state if regime_row else None,
        "composite": regime_row.composite_score if regime_row else None,
        "as_of": regime_row.as_of_date.isoformat() if regime_row and regime_row.as_of_date else None,
    }

    # Coverage freshness
    latest_snap = db.execute(
        select(sqlfunc.max(MarketSnapshot.analysis_timestamp))
    ).scalar()
    snap_count = db.execute(
        select(sqlfunc.count(MarketSnapshot.id))
    ).scalar() or 0
    coverage_age_min = None
    if latest_snap:
        coverage_age_min = int((datetime.now(timezone.utc) - latest_snap).total_seconds() / 60)

    # Pipeline — recent job runs
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_jobs = db.execute(
        select(JobRun)
        .where(JobRun.started_at >= cutoff)
        .order_by(JobRun.started_at.desc())
        .limit(20)
    ).scalars().all()

    ok_count = sum(1 for j in recent_jobs if j.status == "ok")
    error_count = sum(1 for j in recent_jobs if j.status == "error")
    running_count = sum(1 for j in recent_jobs if j.status == "running")

    errors = [
        {
            "task": j.task_name,
            "error": (j.error or "")[:200],
            "at": j.started_at.isoformat() if j.started_at else None,
        }
        for j in recent_jobs
        if j.status == "error"
    ][:5]

    overall = "healthy"
    if error_count > 2 or (coverage_age_min and coverage_age_min > 60):
        overall = "degraded"
    if error_count > 5 or (coverage_age_min and coverage_age_min > 240):
        overall = "critical"

    return {
        "overall": overall,
        "regime": regime,
        "coverage": {
            "snapshot_count": snap_count,
            "latest_timestamp": latest_snap.isoformat() if latest_snap else None,
            "age_minutes": coverage_age_min,
        },
        "pipeline_24h": {
            "total_jobs": len(recent_jobs),
            "ok": ok_count,
            "errors": error_count,
            "running": running_count,
            "recent_errors": errors,
        },
    }

