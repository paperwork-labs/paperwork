"""
Notifications System
==================================

In-app notifications and optional Brain webhook relay for portfolio events, strategy execution, and system status.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import UTC, datetime
import enum

from . import Base

# =============================================================================
# ENUMS
# =============================================================================


class NotificationType(enum.Enum):
    PORTFOLIO_ALERT = "portfolio_alert"  # Portfolio-related alerts
    STRATEGY_EXECUTION = "strategy_execution"  # Strategy execution results
    TRADE_CONFIRMATION = "trade_confirmation"  # Trade confirmations
    MARKET_ALERT = "market_alert"  # Market-based alerts
    SYSTEM_STATUS = "system_status"  # System health/status
    USER_ACTION = "user_action"  # User-triggered notifications


class NotificationChannel(enum.Enum):
    DISCORD = "discord"  # Legacy channel value (prefer IN_APP + Brain webhook for new code)
    EMAIL = "email"  # Email notification
    IN_APP = "in_app"  # In-app notification
    SMS = "sms"  # SMS notification


class NotificationStatus(enum.Enum):
    PENDING = "pending"  # Not yet sent
    SENT = "sent"  # Successfully sent
    FAILED = "failed"  # Failed to send
    DELIVERED = "delivered"  # Confirmed delivered


class Priority(enum.Enum):
    LOW = "low"  # Low priority
    NORMAL = "normal"  # Normal priority
    HIGH = "high"  # High priority
    URGENT = "urgent"  # Urgent notification


# =============================================================================
# NOTIFICATION MODELS
# =============================================================================


class Notification(Base):
    """
    Individual notification to be sent to user.
    """

    __tablename__ = "notifications"

    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Notification details
    type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)
    priority = Column(SQLEnum(Priority), default=Priority.NORMAL, nullable=False)

    # Content
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    formatted_message = Column(Text)  # Channel-specific formatting

    # Status
    status = Column(
        SQLEnum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False
    )

    # Metadata
    source_type = Column(String(50))  # "strategy", "portfolio", "system"
    source_id = Column(String(100))  # ID of source object
    reference_data = Column(JSON)  # Additional context data

    # Delivery tracking
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Scheduling
    scheduled_for = Column(DateTime)  # When to send (null = immediate)
    expires_at = Column(DateTime)  # When notification expires

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="notifications")

    # Indexes
    __table_args__ = (
        Index("idx_notifications_user_status", "user_id", "status"),
        Index("idx_notifications_type", "type"),
        Index("idx_notifications_channel", "channel"),
        Index("idx_notifications_scheduled", "scheduled_for"),
    )

    @property
    def is_urgent(self) -> bool:
        """Check if notification is urgent."""
        return self.priority == Priority.URGENT

    @property
    def can_retry(self) -> bool:
        """Check if notification can be retried."""
        return (
            self.status == NotificationStatus.FAILED
            and self.retry_count < self.max_retries
        )

    @property
    def is_expired(self) -> bool:
        """Check if notification has expired."""
        return self.expires_at is not None and datetime.now(UTC) > self.expires_at


class NotificationTemplate(Base):
    """
    Templates for common notification types.
    """

    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Template identification
    name = Column(String(100), unique=True, nullable=False)
    type = Column(SQLEnum(NotificationType), nullable=False)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)

    # Template content
    title_template = Column(String(200), nullable=False)
    message_template = Column(Text, nullable=False)

    # Settings
    default_priority = Column(SQLEnum(Priority), default=Priority.NORMAL)
    is_active = Column(Boolean, default=True)

    # Metadata
    description = Column(Text)
    variables = Column(JSON)  # Available template variables

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class NotificationPreference(Base):
    """
    User preferences for notification delivery.
    """

    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Preferences by type and channel
    notification_type = Column(SQLEnum(NotificationType), nullable=False)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)

    # Settings
    is_enabled = Column(Boolean, default=True)
    min_priority = Column(SQLEnum(Priority), default=Priority.NORMAL)

    # Channel-specific settings
    channel_settings = Column(JSON)  # Channel-specific configuration

    # Quiet hours
    quiet_hours_start = Column(String(5))  # "22:00"
    quiet_hours_end = Column(String(5))  # "08:00"
    quiet_hours_timezone = Column(String(50), default="UTC")

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User")

    # Constraints
    __table_args__ = (
        Index("idx_preferences_user_type", "user_id", "notification_type"),
    )


class NotificationDelivery(Base):
    """
    Delivery log for notifications.
    """

    __tablename__ = "notification_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_id = Column(
        Integer, ForeignKey("notifications.id"), nullable=False, index=True
    )

    # Delivery attempt details
    attempt_number = Column(Integer, nullable=False)
    attempted_at = Column(DateTime, default=func.now(), nullable=False)

    # Result
    status = Column(SQLEnum(NotificationStatus), nullable=False)
    response_data = Column(JSON)  # Response from delivery service
    error_details = Column(Text)

    # Channel-specific data
    external_id = Column(String(200))  # External service message ID
    delivery_metadata = Column(JSON)

    # Relationships
    notification = relationship("Notification")

    # Indexes
    __table_args__ = (
        Index("idx_deliveries_notification", "notification_id"),
        Index("idx_deliveries_attempted", "attempted_at"),
    )
