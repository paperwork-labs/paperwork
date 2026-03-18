import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TaxCalculation(TimestampMixin, Base):
    __tablename__ = "tax_calculations"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    adjusted_gross_income: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    standard_deduction: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    taxable_income: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    federal_tax: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state_tax: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_withheld: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    refund_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owed_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_insights: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    filing = relationship("Filing", back_populates="tax_calculation")
