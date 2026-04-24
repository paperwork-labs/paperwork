"""Conviction pick persistence model.

One row per (user, symbol, generation run). ``generated_at`` partitions
runs: the latest generation for a given user is served by the public
``GET /api/v1/picks/conviction`` route.

Design notes
------------

* Scoped to ``user_id`` even though the nightly generator reads a shared
  ``MarketSnapshot`` universe — every user gets their own row set so
  tier gating and per-user ranking are easy later (D122 pricing model).
* Stores the ``score_breakdown`` JSON for explainability: we never want
  a customer to see "AxiomFolio recommends NVDA" without being able to
  answer "why?".
* No monetary columns here — this is a discovery-layer artifact.
  Anything execution-related flows through ``OrderManager`` ->
  ``RiskGate`` -> ``BrokerRouter`` (iron law).
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


class ConvictionPick(Base):
    """Nightly conviction-pick generator output persisted for user read."""

    __tablename__ = "conviction_picks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol = Column(String(20), nullable=False)
    rank = Column(Integer, nullable=False)
    score = Column(Numeric(10, 4), nullable=False)
    score_breakdown = Column(JSON, nullable=True)
    rationale = Column(Text, nullable=True)
    stage_label = Column(String(10), nullable=True)
    generated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    generator_version = Column(String(32), nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User")

    __table_args__ = (
        Index("idx_conviction_picks_user_generated", "user_id", "generated_at"),
        Index("idx_conviction_picks_user_rank", "user_id", "rank"),
    )
