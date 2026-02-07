"""
AxiomFolio V1 - Clean Notifications Routes
Handles Discord notifications and in-app alerts.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import logging
from datetime import datetime

# dependencies
from backend.models.user import User
from backend.services.notifications.discord_service import DiscordService
from backend.api.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status")
async def get_notification_status(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get notification settings and status."""
    return {
        "user_id": user.id,
        "discord_enabled": True,  # TODO: Get from user preferences
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/test")
async def send_test_notification(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Send test Discord notification."""
    try:
        discord = DiscordService()
        await discord.send_test_notification(f"Test notification for {user.username}")

        return {
            "message": "Test notification sent",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Test notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
