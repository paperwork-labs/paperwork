from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from . import Base


class MarketTrackedPlan(Base):
    """Analyst/admin-maintained entry and exit annotations for tracked symbols."""

    __tablename__ = "market_tracked_plan"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", name="uq_market_tracked_plan_symbol"),
    )
