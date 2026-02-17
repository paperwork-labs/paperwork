"""
AxiomFolio V1 - Clean Admin Routes
System administration endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import secrets

from pydantic import BaseModel, EmailStr

# dependencies
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.user_invite import UserInvite
from backend.api.dependencies import get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter()


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = "readonly"
    expires_in_days: int = 7


class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


def _parse_role(role: str | None) -> UserRole:
    raw = (role or "").strip().lower()
    if not raw:
        return UserRole.READONLY
    if raw == "viewer":
        return UserRole.READONLY
    if raw == "user":
        # Legacy alias kept for backward compatibility during migration.
        return UserRole.READONLY
    if raw == "analyst":
        return UserRole.ANALYST
    for r in UserRole:
        if raw == r.value or raw == r.name.lower():
            return r
    raise HTTPException(status_code=400, detail=f"Invalid role: {role}")


def _role_value(role_obj: Any) -> str:
    """Normalize role payloads coming from enum, raw string, or legacy rows."""
    if role_obj is None:
        return "readonly"
    if isinstance(role_obj, UserRole):
        if role_obj == UserRole.USER:
            return "readonly"
        return role_obj.value
    # SQLAlchemy enum columns can surface raw strings during legacy drift.
    raw = str(role_obj).strip()
    if not raw:
        return "readonly"
    lowered = raw.lower()
    # Keep API stable even when legacy values still exist.
    if lowered == "user":
        return "readonly"
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
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": _role_value(user.role),
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "full_name": user.full_name,
                    "created_at": user.created_at.isoformat(),
                }
                for user in users
            ],
            "total_users": len(users),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Admin users list error: {e}")
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
                "expires_at": inv.expires_at.isoformat(),
                "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
                "created_at": inv.created_at.isoformat(),
            }
            for inv in invites
        ]
    }


@router.post("/users/invite")
async def invite_user(
    payload: InviteUserRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create an email invite for a user (admin only)."""
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="User already exists")
    role = _parse_role(payload.role)
    expires_at = datetime.utcnow() + timedelta(days=max(1, min(payload.expires_in_days, 30)))
    token = secrets.token_urlsafe(32)
    existing_invite = (
        db.query(UserInvite)
        .filter(UserInvite.email == email)
        .first()
    )
    if existing_invite:
        is_active = (
            existing_invite.accepted_at is None
            and existing_invite.expires_at >= datetime.utcnow()
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

