"""Persist in-app notifications and relay events to the Brain webhook.

medallion: ops
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    Priority,
)
from app.services.brain.webhook_client import BrainWebhookClient, brain_webhook

logger = logging.getLogger(__name__)


class NotificationService:
    """Create in-app notification rows and send parallel events to Brain."""

    def __init__(self, brain: Optional[BrainWebhookClient] = None) -> None:
        self._brain = brain or brain_webhook

    @staticmethod
    def is_brain_configured() -> bool:
        return bool(settings.BRAIN_WEBHOOK_URL)

    async def notify_user(
        self,
        db: Session,
        user_id: int,
        title: str,
        message: str,
        *,
        notification_type: NotificationType = NotificationType.USER_ACTION,
        priority: Priority = Priority.NORMAL,
        brain_event: str = "user_notification",
        brain_extra: Optional[Dict[str, Any]] = None,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        commit: bool = True,
    ) -> Dict[str, Any]:
        row = Notification(
            user_id=user_id,
            type=notification_type,
            channel=NotificationChannel.IN_APP,
            priority=priority,
            title=title[:200],
            message=message,
            status=NotificationStatus.SENT,
            sent_at=datetime.now(timezone.utc),
            source_type=source_type,
            source_id=source_id,
        )
        db.add(row)
        if commit:
            db.commit()
            db.refresh(row)
        else:
            db.flush()

        data: Dict[str, Any] = {
            "title": title,
            "message": message,
            "notification_id": row.id,
        }
        if brain_extra:
            data.update(brain_extra)

        brain_ok = await self._brain.notify(brain_event, data, user_id=user_id)
        return {"notification_id": row.id, "brain_delivered": brain_ok}

    def notify_system_sync(
        self,
        title: str,
        message: str,
        *,
        brain_event: str = "system_alert",
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        data: Dict[str, Any] = {"title": title, "message": message}
        if extra_data:
            data.update(extra_data)
        return self._brain.notify_sync(brain_event, data, user_id=None)


notification_service = NotificationService()

__all__ = ["NotificationService", "notification_service"]
