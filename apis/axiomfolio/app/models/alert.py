from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Float,
    Numeric,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Alert basic info
    name = Column(String(100), nullable=False)
    description = Column(Text)
    symbol = Column(String(20), nullable=False, index=True)
    alert_type = Column(
        String(50), nullable=False
    )  # PRICE, INDICATOR, SIGNAL, PORTFOLIO

    # Alert configuration
    is_active = Column(Boolean, default=True)
    is_repeating = Column(Boolean, default=False)
    max_triggers = Column(Integer, default=1)
    current_triggers = Column(Integer, default=0)

    # Notification settings
    notify_discord = Column(Boolean, default=True)
    notify_email = Column(Boolean, default=False)
    notify_app = Column(Boolean, default=True)

    # Priority and urgency
    priority = Column(String(10), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    sound_enabled = Column(Boolean, default=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_triggered = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))

    # Custom message
    custom_message = Column(Text)

    # Relationships
    user = relationship(
        "User"
    )  # Removed back_populates="alerts" since User.alerts is commented out
    conditions = relationship(
        "AlertCondition", back_populates="alert", cascade="all, delete-orphan"
    )


class AlertCondition(Base):
    __tablename__ = "alert_conditions"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)

    # Condition details
    condition_type = Column(
        String(50), nullable=False
    )  # PRICE, ATR_DISTANCE, RSI, MACD, etc.
    operator = Column(
        String(10), nullable=False
    )  # GT, LT, EQ, CROSSES_ABOVE, CROSSES_BELOW
    target_value = Column(Float, nullable=False)
    current_value = Column(Float)

    # Additional parameters for complex conditions
    indicator_params = Column(JSON)  # Store indicator-specific parameters
    timeframe = Column(String(10), default="1D")  # 1M, 5M, 1H, 1D, etc.

    # Condition state
    is_met = Column(Boolean, default=False)
    last_checked = Column(DateTime(timezone=True))
    times_met = Column(Integer, default=0)

    # For compound conditions
    logical_operator = Column(String(10), default="AND")  # AND, OR
    group_id = Column(Integer)  # Group related conditions

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    alert = relationship("Alert", back_populates="conditions")


# Predefined alert templates for common scenarios
class AlertTemplate(Base):
    __tablename__ = "alert_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50))  # ATR_MATRIX, TECHNICAL, PORTFOLIO, RISK

    # Template configuration
    template_config = Column(JSON)  # Store the complete alert configuration
    is_public = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Alert history for tracking all notifications sent
class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)

    # Trigger details
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    trigger_price = Column(Numeric(10, 4))
    trigger_value = Column(Float)
    condition_met = Column(String(200))

    # Notification status
    discord_sent = Column(Boolean, default=False)
    email_sent = Column(Boolean, default=False)
    app_notification_sent = Column(Boolean, default=False)

    # Message content
    message_title = Column(String(200))
    message_body = Column(Text)

    # Response tracking
    user_acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True))

    # Additional context
    market_conditions = Column(JSON)
    portfolio_impact = Column(JSON)
