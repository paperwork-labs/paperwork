from __future__ import annotations

from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func

from . import Base
from .user import UserRole


class UserInvite(Base):
    """Admin-created email invites for onboarding new users."""

    __tablename__ = "user_invites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(
        SQLEnum(
            UserRole,
            values_callable=lambda x: [m.value for m in UserRole],
            native_enum=False,
            length=20,
        ),
        nullable=False,
        server_default=UserRole.VIEWER.value,
        default=UserRole.VIEWER,
    )
    token = Column(String(64), unique=True, nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    accepted_at = Column(TIMESTAMP(timezone=True))
