"""Shadow (paper) order model — intended orders persisted without broker routing.

Populated by ``backend.services.execution.shadow_order_recorder.ShadowOrderRecorder``
whenever ``settings.SHADOW_TRADING_MODE`` is True (default-ON safety; see D137).
Never touched by any broker executor; mark-to-market P&L is updated by the
``backend.services.execution.shadow_mark_to_market.run`` Celery task.

All monetary amounts use ``Numeric`` to preserve ``Decimal`` precision end-to-end
(Iron Law: monetary values use Decimal, never float).
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
)
from sqlalchemy.sql import func

from . import Base


class ShadowOrderStatus(str, enum.Enum):
    """Lifecycle of a shadow (paper) order."""

    INTENDED = "intended"
    WOULD_DENY_BY_RISK_GATE = "would_deny_by_risk_gate"
    EXECUTED_AT_SIMULATION_TIME = "executed_at_simulation_time"
    MARKED_TO_MARKET = "marked_to_market"
    CLOSED = "closed"


class ShadowOrder(Base):
    """Intended order that would have hit the broker if shadow mode were off.

    Status transitions (set by :class:`ShadowOrderRecorder` + MtM task):
      INTENDED -> WOULD_DENY_BY_RISK_GATE (recorder, when risk_gate raises)
      INTENDED -> EXECUTED_AT_SIMULATION_TIME (recorder, on healthy record)
      EXECUTED_AT_SIMULATION_TIME -> MARKED_TO_MARKET (MtM task, periodic update)
    """

    __tablename__ = "shadow_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id = Column(String(100), nullable=True)

    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # buy | sell
    order_type = Column(String(20), nullable=False, default="market")
    qty = Column(Numeric(18, 6), nullable=False)
    limit_price = Column(Numeric(18, 6), nullable=True)
    tif = Column(String(10), nullable=True)  # day | gtc | ioc | fok

    status = Column(
        String(40),
        nullable=False,
        default=ShadowOrderStatus.INTENDED.value,
        index=True,
    )

    risk_gate_verdict = Column(JSON, nullable=True)

    intended_fill_price = Column(Numeric(18, 6), nullable=True)
    intended_fill_at = Column(DateTime(timezone=True), nullable=True)

    simulated_pnl = Column(Numeric(18, 6), nullable=True)
    simulated_pnl_as_of = Column(DateTime(timezone=True), nullable=True)
    last_mark_price = Column(Numeric(18, 6), nullable=True)

    source_order_id = Column(
        Integer,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    error_message = Column(String(500), nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_shadow_orders_user_status", "user_id", "status"),
        Index("ix_shadow_orders_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"<ShadowOrder id={self.id} user={self.user_id} {self.side} "
            f"{self.qty} {self.symbol} status={self.status}>"
        )
