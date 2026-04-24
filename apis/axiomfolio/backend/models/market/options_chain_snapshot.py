"""Time-series snapshots of options chain surface metrics (IV, liquidity, spread)."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from backend.models import Base


class OptionsChainSnapshot(Base):
    """Per-contract options chain row at a point in time (gold-layer snapshot)."""

    __tablename__ = "options_chain_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    expiry = Column(Date, nullable=False, index=True)
    strike = Column(Numeric(12, 4), nullable=False)
    option_type = Column(String(4), nullable=False)  # CALL / PUT
    bid = Column(Numeric(12, 4), nullable=True)
    ask = Column(Numeric(12, 4), nullable=True)
    mid = Column(Numeric(12, 4), nullable=True)
    spread_abs = Column(Numeric(12, 4), nullable=True)
    spread_rel = Column(Numeric(6, 4), nullable=True)
    open_interest = Column(Integer, nullable=True)
    volume = Column(Integer, nullable=True)
    implied_vol = Column(Numeric(6, 4), nullable=True)  # 0-1
    iv_pctile_1y = Column(Numeric(6, 4), nullable=True)  # 0-1
    iv_rank_1y = Column(Numeric(6, 4), nullable=True)  # 0-1
    liquidity_score = Column(Numeric(6, 4), nullable=True)  # 0-1
    delta = Column(Numeric(6, 4), nullable=True)
    gamma = Column(Numeric(8, 6), nullable=True)
    theta = Column(Numeric(8, 4), nullable=True)
    vega = Column(Numeric(6, 4), nullable=True)
    snapshot_taken_at = Column(
        DateTime(timezone=True), nullable=False, index=True
    )  # UTC
    source = Column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "expiry",
            "strike",
            "option_type",
            "snapshot_taken_at",
            name="uq_ocs_sym_exp_strike_type_ts",
        ),
        Index("ix_ocs_sym_ts", "symbol", "snapshot_taken_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<OptionsChainSnapshot {self.symbol} {self.expiry} K={self.strike} "
            f"{self.option_type} @ {self.snapshot_taken_at}>"
        )
