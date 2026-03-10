import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DocumentType(str, enum.Enum):
    W2 = "w2"
    DRIVERS_LICENSE = "drivers_license"
    MISC_1099 = "1099_misc"
    NEC_1099 = "1099_nec"


class ExtractionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filings.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(
            DocumentType, name="document_type",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(
            ExtractionStatus, name="extraction_status",
            values_callable=lambda e: [x.value for x in e],
        ),
        default=ExtractionStatus.PENDING,
        nullable=False,
    )
    extraction_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    filing = relationship("Filing", back_populates="documents")
