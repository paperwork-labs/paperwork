import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class IrsStatus(enum.StrEnum):
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    transmitter_partner: Mapped[str] = mapped_column(String(50), nullable=False)
    submission_id_external: Mapped[str | None] = mapped_column(String(255), nullable=True)
    irs_status: Mapped[IrsStatus] = mapped_column(
        Enum(IrsStatus, name="irs_status", values_callable=lambda e: [x.value for x in e]),
        default=IrsStatus.SUBMITTED,
        nullable=False,
    )
    rejection_codes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    filing = relationship("Filing", back_populates="submission")
