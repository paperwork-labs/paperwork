"""Closed option tax lots (FIFO-matched) for Tax Center realized options."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models import Base


class OptionTaxLot(Base):
    """One closed slice of an option position (matched open → close)."""

    __tablename__ = "option_tax_lots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_account_id = Column(
        Integer, ForeignKey("broker_accounts.id"), nullable=False
    )
    symbol = Column(String(64), nullable=False)
    underlying = Column(String(32), nullable=False)
    option_type = Column(String(8), nullable=False)  # "call" | "put"
    strike = Column(Numeric(12, 4), nullable=False)
    expiry = Column(Date, nullable=False)
    multiplier = Column(Integer, nullable=False, default=100)

    quantity_opened = Column(Numeric(15, 4), nullable=False)
    cost_basis_per_contract = Column(Numeric(12, 4), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=False)

    closed_at = Column(DateTime(timezone=True), nullable=False)
    quantity_closed = Column(Numeric(15, 4), nullable=False)
    proceeds_per_contract = Column(Numeric(12, 4), nullable=True)
    realized_pnl = Column(Numeric(14, 4), nullable=True)
    holding_class = Column(String(16), nullable=True)  # "short_term" | "long_term"

    opening_trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False)
    closing_trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    opening_trade = relationship("Trade", foreign_keys=[opening_trade_id])
    closing_trade = relationship("Trade", foreign_keys=[closing_trade_id])

    __table_args__ = (
        Index("ix_option_tax_lots_user_symbol", "user_id", "symbol"),
        Index("ix_option_tax_lots_user_closed", "user_id", "closed_at"),
        UniqueConstraint(
            "opening_trade_id",
            "closing_trade_id",
            name="uq_option_tax_lots_opening_trade_id_closing_trade_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<OptionTaxLot({self.symbol} opened={self.quantity_opened} "
            f"closed={self.quantity_closed})>"
        )
