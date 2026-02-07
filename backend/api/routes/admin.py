"""
AxiomFolio V1 - Clean Admin Routes
System administration endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging
from datetime import datetime

# dependencies
from backend.database import get_db
from backend.models.user import User
from backend.api.dependencies import get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/users")
async def list_users(
    admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List all users (admin only)."""
    try:
        users = db.query(User).all()

        return {
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value,
                    "is_active": user.is_active,
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


@router.get("/system/status")
async def get_system_status(
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Get system status (admin only)."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "uptime": "placeholder",
        "timestamp": datetime.now().isoformat(),
    }
