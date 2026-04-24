"""
User Management Models
===========================

Multi-user authentication, preferences, and user isolation.
"""

from enum import Enum

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    Column,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
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


class UserRole(str, Enum):
    """Access roles stored as lowercase strings in the database (VARCHAR, not PG enum)."""

    OWNER = "owner"  # Full access, operator/admin routes, can execute trades
    ANALYST = "analyst"  # Read + propose trades (approval flow TBD)
    VIEWER = "viewer"  # Read-only access


# =============================================================================
# USER MANAGEMENT
# =============================================================================


class User(Base):
    """User accounts with authentication and preferences."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255))  # OAuth users may not have password
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))

    # OAuth
    oauth_provider = Column(String(20), nullable=True)  # 'google', 'apple', None for password
    oauth_id = Column(String(255), nullable=True)  # provider's unique user ID
    avatar_url = Column(Text, nullable=True)

    # Authentication & Access (VARCHAR; migrated from PostgreSQL userrole enum)
    role = Column(
        SQLEnum(
            UserRole,
            values_callable=lambda x: [m.value for m in UserRole],
            native_enum=False,
            length=20,
        ),
        nullable=False,
        server_default=UserRole.ANALYST.value,
        default=UserRole.ANALYST,
    )
    # Add DB-level defaults so raw SQL inserts and bulk loads are safe.
    is_active = Column(Boolean, default=True, server_default=sa.text("true"), nullable=False)
    is_verified = Column(Boolean, default=False, server_default=sa.text("false"), nullable=False)
    # Admin approval required for new registrations (existing users default to approved)
    is_approved = Column(Boolean, default=False, server_default=sa.text("false"), nullable=False)
    last_login = Column(TIMESTAMP(timezone=True))
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(TIMESTAMP(timezone=True))
    refresh_token_family = Column(String(36), nullable=True)
    # Immediately prior family + rotation time for benign multi-tab refresh races
    previous_refresh_token_family = Column(String(36), nullable=True)
    previous_refresh_token_rotated_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Preferences
    timezone = Column(String(50), default="UTC")
    currency_preference = Column(String(3), default="USD")
    notification_preferences = Column(JSON)
    # UI Preferences (theme, table density, etc.)
    ui_preferences = Column(JSON)

    # External Integrations (SHA-256 hex digest of TradingView webhook secret)
    tv_webhook_secret = Column(String(64), unique=True, nullable=True, index=True)
    # Fernet-encrypted BYOK payload. Fernet output is ~1.33x the plaintext
    # + 57 bytes of framing, so even a 2048-char plaintext (the API
    # accepts up to that) produces ~2800+ chars of ciphertext. Use Text
    # so we never silently truncate a valid user-supplied key.
    llm_provider_key_encrypted = Column(Text, nullable=True)

    # Audit
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships - Essential ones only to avoid circular imports
    broker_accounts = relationship(
        "BrokerAccount", back_populates="user", cascade="all, delete-orphan"
    )
    positions = relationship("Position", back_populates="user", cascade="all, delete-orphan")
    tax_lots = relationship("TaxLot", back_populates="user", cascade="all, delete-orphan")
    account_balances = relationship(
        "AccountBalance", back_populates="user", cascade="all, delete-orphan"
    )
    margin_interest = relationship(
        "MarginInterest", back_populates="user", cascade="all, delete-orphan"
    )
    transfers = relationship("Transfer", back_populates="user", cascade="all, delete-orphan")
    options = relationship("Option", back_populates="user", cascade="all, delete-orphan")
    strategies = relationship(
        "Strategy",
        back_populates="user",
        foreign_keys="Strategy.user_id",
        cascade="all, delete-orphan",
    )
    strategy_executions = relationship(
        "StrategyExecution", back_populates="user", cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_users_email_active", "email", "is_active"),
        Index("idx_users_last_login", "last_login"),
        UniqueConstraint("oauth_provider", "oauth_id", name="uq_user_oauth"),
    )

    @property
    def full_name(self) -> str:
        first = self.first_name or ""
        last = self.last_name or ""
        name = f"{first} {last}".strip()
        return name or self.username

    @full_name.setter
    def full_name(self, value: str):
        if not value:
            self.first_name = None
            self.last_name = None
            return
        parts = str(value).strip().split()
        self.first_name = parts[0] if parts else None
        self.last_name = " ".join(parts[1:]) if len(parts) > 1 else None
