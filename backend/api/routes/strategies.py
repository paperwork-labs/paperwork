"""
Strategies API -- placeholder.

The composable rules engine (Section 2) will replace the old ATR/DCA strategy
services.  This router is kept so the mount in main.py stays valid.
"""

from fastapi import APIRouter, Depends
from backend.api.dependencies import get_current_user
from backend.models.user import User

router = APIRouter()


@router.get("/status")
async def strategies_status(user: User = Depends(get_current_user)):
    return {
        "status": "coming_soon",
        "message": "Strategy engine is being rebuilt with the composable rules system.",
    }
