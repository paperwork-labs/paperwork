import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AuthProvider(str, enum.Enum):
    LOCAL = "local"
    GOOGLE = "google"
    APPLE = "apple"


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class AdvisorTier(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    referral_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    referred_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [x.value for x in e]),
        default=UserRole.USER,
        nullable=False,
    )
    advisor_tier: Mapped[AdvisorTier] = mapped_column(
        Enum(AdvisorTier, name="advisor_tier", values_callable=lambda e: [x.value for x in e]),
        default=AdvisorTier.FREE,
        nullable=False,
    )
    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, name="auth_provider", values_callable=lambda e: [x.value for x in e]),
        default=AuthProvider.LOCAL,
        nullable=False,
    )
    auth_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attribution: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    filings = relationship("Filing", back_populates="user", cascade="all, delete-orphan")
    referrals = relationship("User", backref="referred_by", remote_side="User.id")
