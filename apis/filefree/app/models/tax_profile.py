import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TaxProfile(TimestampMixin, Base):
    __tablename__ = "tax_profiles"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    ssn_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_encrypted: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    date_of_birth_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_wages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_federal_withheld: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_state_withheld: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)

    filing = relationship("Filing", back_populates="tax_profile")
