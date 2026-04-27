"""
AxiomFolio V1 - Notifications routes
Brain webhook delivery and in-app alerts.
"""

from datetime import UTC, datetime
from typing import Any, Dict
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.notification import NotificationType
from app.models.user import User
from app.services.notifications.notification_service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status")
async def get_notification_status(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get notification settings and status."""
    return {
        "user_id": user.id,
        "brain_webhook_configured": notification_service.is_brain_configured(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/test")
async def send_test_notification(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Send a test notification (in-app + Brain webhook when configured)."""
    try:
        await notification_service.notify_user(
            db,
            user.id,
            title="Test notification",
            message=f"Test notification for {user.username}",
            notification_type=NotificationType.USER_ACTION,
            brain_event="user_notification_test",
        )

        return {
            "message": "Test notification sent",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        logger.error("Test notification error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
