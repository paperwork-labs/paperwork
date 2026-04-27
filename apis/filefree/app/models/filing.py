import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FilingStatusType(enum.StrEnum):
    SINGLE = "single"
    MARRIED_JOINT = "married_joint"
    MARRIED_SEPARATE = "married_separate"
    HEAD_OF_HOUSEHOLD = "head_of_household"


class FilingStatus(enum.StrEnum):
    DRAFT = "draft"
    DOCUMENTS_UPLOADED = "documents_uploaded"
    DATA_CONFIRMED = "data_confirmed"
    CALCULATED = "calculated"
    REVIEW = "review"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Filing(TimestampMixin, Base):
    __tablename__ = "filings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tax_year: Mapped[int] = mapped_column(Integer, nullable=False)
    filing_status_type: Mapped[FilingStatusType | None] = mapped_column(
        Enum(
            FilingStatusType,
            name="filing_status_type",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=True,
    )
    status: Mapped[FilingStatus] = mapped_column(
        Enum(
            FilingStatus,
            name="filing_status",
            values_callable=lambda e: [x.value for x in e],
        ),
        default=FilingStatus.DRAFT,
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="filings")
    documents = relationship("Document", back_populates="filing", cascade="all, delete-orphan")
    tax_profile = relationship(
        "TaxProfile", back_populates="filing", uselist=False, cascade="all, delete-orphan"
    )
    tax_calculation = relationship(
        "TaxCalculation", back_populates="filing", uselist=False, cascade="all, delete-orphan"
    )
    submission = relationship(
        "Submission", back_populates="filing", uselist=False, cascade="all, delete-orphan"
    )
