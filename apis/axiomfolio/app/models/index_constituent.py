from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func

from . import Base


class IndexConstituent(Base):
    __tablename__ = "index_constituents"

    id = Column(Integer, primary_key=True, index=True)
    index_name = Column(
        String(32), nullable=False, index=True
    )  # SP500, NASDAQ100, DOW30
    symbol = Column(String(20), nullable=False, index=True)
    # Optional fundamentals snapshot
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(Integer)

    # Lifecycle
    is_active = Column(Boolean, default=True, index=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    became_inactive_at = Column(DateTime(timezone=True), nullable=True)

    # Housekeeping
    last_refreshed_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("index_name", "symbol", name="uq_index_symbol"),
        Index("idx_index_active", "index_name", "is_active"),
    )
