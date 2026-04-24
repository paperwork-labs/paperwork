"""
Audit Trail System
================================

Comprehensive audit logging for compliance, security, and debugging.
Tracks all user actions, system events, and data changes.
"""

import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base

# =============================================================================
# ENUMS
# =============================================================================


class AuditEventType(enum.Enum):
    USER_LOGIN = "user_login"  # User authentication
    USER_LOGOUT = "user_logout"
    USER_REGISTER = "user_register"

    PORTFOLIO_VIEW = "portfolio_view"  # Portfolio access
    PORTFOLIO_SYNC = "portfolio_sync"

    TRADE_EXECUTE = "trade_execute"  # Trading actions
    TRADE_CANCEL = "trade_cancel"

    STRATEGY_START = "strategy_start"  # Strategy execution
    STRATEGY_STOP = "strategy_stop"
    STRATEGY_MODIFY = "strategy_modify"

    DATA_IMPORT = "data_import"  # Data operations
    DATA_EXPORT = "data_export"
    DATA_MODIFY = "data_modify"
    DATA_DELETE = "data_delete"

    SYSTEM_START = "system_start"  # System events
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"

    API_CALL = "api_call"  # API access
    SETTINGS_CHANGE = "settings_change"  # Configuration changes


class AuditLevel(enum.Enum):
    DEBUG = "debug"  # Detailed debugging info
    INFO = "info"  # General information
    WARNING = "warning"  # Warning conditions
    ERROR = "error"  # Error conditions
    CRITICAL = "critical"  # Critical system events


class AuditStatus(enum.Enum):
    SUCCESS = "success"  # Operation succeeded
    FAILURE = "failure"  # Operation failed
    PARTIAL = "partial"  # Partially completed
    PENDING = "pending"  # Still in progress


# =============================================================================
# AUDIT MODELS
# =============================================================================


class AuditLog(Base):
    """
    Comprehensive audit log for all system events.
    """

    __tablename__ = "audit_logs"

    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Event identification
    event_type = Column(SQLEnum(AuditEventType), nullable=False, index=True)
    event_id = Column(String(100))  # Unique event identifier
    correlation_id = Column(String(100), index=True)  # Groups related events

    # Actor information
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    session_id = Column(String(100))
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(Text)

    # Event details
    level = Column(SQLEnum(AuditLevel), default=AuditLevel.INFO, nullable=False)
    status = Column(SQLEnum(AuditStatus), default=AuditStatus.SUCCESS, nullable=False)
    message = Column(Text, nullable=False)

    # Context data
    resource_type = Column(String(50))  # "position", "trade", "strategy"
    resource_id = Column(String(100))  # ID of affected resource
    action = Column(String(100))  # Specific action taken

    # Request/response data
    request_data = Column(JSON)  # Input parameters
    response_data = Column(JSON)  # Output/results
    error_details = Column(JSON)  # Error information

    # Performance metrics
    duration_ms = Column(Integer)  # Operation duration

    # Timestamps
    occurred_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    user = relationship("User")

    # Indexes for performance
    __table_args__ = (
        Index("idx_audit_user_date", "user_id", "occurred_at"),
        Index("idx_audit_event_date", "event_type", "occurred_at"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_correlation", "correlation_id"),
    )

    @property
    def is_error(self) -> bool:
        """Check if this is an error event."""
        return self.level in [AuditLevel.ERROR, AuditLevel.CRITICAL]

    @property
    def is_user_action(self) -> bool:
        """Check if this is a user-initiated action."""
        return self.user_id is not None


class DataChangeLog(Base):
    """
    Detailed logging of data changes for critical tables.
    """

    __tablename__ = "data_change_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_log_id = Column(Integer, ForeignKey("audit_logs.id"), index=True)

    # Change details
    table_name = Column(String(100), nullable=False, index=True)
    record_id = Column(String(100), nullable=False)
    operation = Column(String(20), nullable=False)  # INSERT, UPDATE, DELETE

    # Change data
    old_values = Column(JSON)  # Previous values
    new_values = Column(JSON)  # New values
    changed_fields = Column(JSON)  # List of changed field names

    # Context
    changed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    change_reason = Column(Text)

    # Timestamps
    changed_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    audit_log = relationship("AuditLog")
    changed_by_user = relationship("User")

    # Indexes
    __table_args__ = (
        Index("idx_changes_table_record", "table_name", "record_id"),
        Index("idx_changes_date", "changed_at"),
    )


class SecurityEvent(Base):
    """
    Security-related events and anomalies.
    """

    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_log_id = Column(Integer, ForeignKey("audit_logs.id"), index=True)

    # Security event details
    event_category = Column(
        String(50), nullable=False
    )  # "authentication", "authorization", "anomaly"
    severity = Column(SQLEnum(AuditLevel), nullable=False)

    # Threat information
    threat_indicators = Column(JSON)  # IOCs, patterns, etc.
    risk_score = Column(Integer)  # 0-100 risk score

    # Response
    action_taken = Column(Text)  # What was done
    requires_investigation = Column(Boolean, default=False)
    investigated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    investigation_notes = Column(Text)

    # Resolution
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)

    # Timestamps
    detected_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    audit_log = relationship("AuditLog")
    investigator = relationship("User")

    # Indexes
    __table_args__ = (
        Index("idx_security_category", "event_category"),
        Index("idx_security_severity", "severity"),
        Index("idx_security_unresolved", "resolved_at"),  # NULL for unresolved
    )
