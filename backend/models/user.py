"""
User Management Models
===========================

Multi-user authentication, preferences, and user isolation.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Index,
    TIMESTAMP,
    Enum as SQLEnum,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import sqlalchemy as sa

from . import Base

# =============================================================================
# ENUMS
# =============================================================================


class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"
    ANALYST = "analyst"


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

    # Authentication & Access
    # Add a DB-level default so raw SQL inserts (and migrations/bulk loads) are safe.
    role = Column(
        SQLEnum(UserRole),
        default=UserRole.USER,
        # SQLAlchemy Enum(UserRole) stores the *name* (e.g. 'USER') by default.
        server_default=UserRole.USER.name,
        nullable=False,
    )
    # Add DB-level defaults so raw SQL inserts and bulk loads are safe.
    is_active = Column(Boolean, default=True, server_default=sa.text("true"), nullable=False)
    is_verified = Column(Boolean, default=False, server_default=sa.text("false"), nullable=False)
    last_login = Column(TIMESTAMP(timezone=True))
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(TIMESTAMP(timezone=True))

    # Preferences
    timezone = Column(String(50), default="UTC")
    currency_preference = Column(String(3), default="USD")
    notification_preferences = Column(JSON)
    # UI Preferences (theme, table density, etc.)
    ui_preferences = Column(JSON)

    # Audit
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships - Essential ones only to avoid circular imports
    broker_accounts = relationship(
        "BrokerAccount", back_populates="user", cascade="all, delete-orphan"
    )
    positions = relationship(
        "Position", back_populates="user", cascade="all, delete-orphan"
    )
    tax_lots = relationship(
        "TaxLot", back_populates="user", cascade="all, delete-orphan"
    )
    account_balances = relationship(
        "AccountBalance", back_populates="user", cascade="all, delete-orphan"
    )
    margin_interest = relationship(
        "MarginInterest", back_populates="user", cascade="all, delete-orphan"
    )
    transfers = relationship(
        "Transfer", back_populates="user", cascade="all, delete-orphan"
    )
    options = relationship(
        "Option", back_populates="user", cascade="all, delete-orphan"
    )
    strategies = relationship(
        "Strategy",
        back_populates="user",
        foreign_keys="Strategy.user_id",
        cascade="all, delete-orphan",
    )
    strategy_executions = relationship(
        "StrategyExecution", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_users_email_active", "email", "is_active"),
        Index("idx_users_last_login", "last_login"),
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
