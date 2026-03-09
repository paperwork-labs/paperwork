from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Waitlist(TimestampMixin, Base):
    __tablename__ = "waitlist"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="landing", nullable=False)
    attribution: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
