"""Multi-tenant hardening models.

Tables that enforce per-tenant isolation across rate limiting, GDPR
data-subject rights, and cost attribution. All tables include a
``user_id`` foreign key that is the unit of isolation; ``TenantRateLimit``
allows ``user_id IS NULL`` for the global default bucket.
"""

from __future__ import annotations

import enum
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from . import Base

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TenantRateLimit(Base):
    """Per-(user, endpoint) rate-limit override.

    A row with ``user_id IS NULL`` defines the global default for an
    endpoint pattern. The most specific match wins
    (``(user_id, endpoint_pattern)`` > ``(NULL, endpoint_pattern)`` >
    ``(user_id, '*')`` > ``(NULL, '*')``).
    """

    __tablename__ = "tenant_rate_limits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    endpoint_pattern = Column(String(200), nullable=False)
    bucket_size_per_minute = Column(Integer, nullable=False)
    burst_capacity = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "endpoint_pattern", name="uq_tenant_rate_limits_user_endpoint"),
        Index("ix_tenant_rate_limits_endpoint", "endpoint_pattern"),
    )


class RateLimitViolation(Base):
    """Audit row for every 429 emitted by the rate limiter."""

    __tablename__ = "rate_limit_violations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    endpoint = Column(String(200), nullable=False, index=True)
    attempted_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    headers = Column(JSON, nullable=True)


# ---------------------------------------------------------------------------
# GDPR / data subject rights
# ---------------------------------------------------------------------------


class GDPRJobStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class GDPRExportJob(Base):
    """Async data-export request (one row per user request)."""

    __tablename__ = "gdpr_export_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String(32), nullable=False, default=GDPRJobStatus.PENDING.value)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    download_url = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    bytes_written = Column(Integer, nullable=True)

    __table_args__ = (Index("ix_gdpr_export_user_status", "user_id", "status"),)


class GDPRDeleteJob(Base):
    """Async account-delete request (two-phase: PENDING -> CONFIRMED -> RUNNING -> COMPLETED)."""

    __tablename__ = "gdpr_delete_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String(32), nullable=False, default=GDPRJobStatus.PENDING.value)
    # SHA-256 hex of the confirmation token; plaintext is delivered out
    # of band (email link). Never stored in plaintext.
    confirmation_token_hash = Column(String(64), nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (Index("ix_gdpr_delete_user_status", "user_id", "status"),)


# ---------------------------------------------------------------------------
# Cost attribution
# ---------------------------------------------------------------------------


class TenantCostRollup(Base):
    """Daily per-tenant cost totals (LLM + provider call + storage).

    Computed by ``app.services.multitenant.cost_attribution``.
    All money fields are ``Numeric(12, 6)`` so we can sum micro-cents
    (LLM token costs) without precision loss.
    """

    __tablename__ = "tenant_cost_rollups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day = Column(Date, nullable=False, index=True)
    llm_cost_usd = Column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    provider_call_cost_usd = Column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    storage_mb = Column(Integer, nullable=False, default=0)
    total_cost_usd = Column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_tenant_cost_rollups_user_day"),
        Index("ix_tenant_cost_rollups_day", "day"),
    )


# ---------------------------------------------------------------------------
# Incident audit (used by GDPR services on failure to fail-loud)
# ---------------------------------------------------------------------------


class IncidentSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentRow(Base):
    """Forensic incident row for non-trivial backend failures.

    Used when a fail-loud trail is required even after the original
    exception has been caught and surfaced to the user. GDPR
    export/delete failures MUST write here so the operator can trace
    every aborted data-subject-rights request.
    """

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default=IncidentSeverity.MEDIUM.value)
    summary = Column(Text, nullable=False)
    context = Column(JSON, nullable=True)
    occurred_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_notes = Column(Text, nullable=True)

    __table_args__ = (Index("ix_incidents_category_occurred", "category", "occurred_at"),)
