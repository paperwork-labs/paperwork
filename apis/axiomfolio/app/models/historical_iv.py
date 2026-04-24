"""
Historical Implied Volatility Model
====================================

Daily IV snapshots for IV rank calculation and options analysis.
"""

from datetime import date
from sqlalchemy import Column, Integer, String, Float, Date, Index, UniqueConstraint
from app.models import Base


class HistoricalIV(Base):
    """Daily implied volatility snapshots for IV rank and percentile calculations.

    Table name: historical_iv
    Primary source: IB Gateway live queries

    Used for:
    - IV Rank calculation (percentile over trailing 252 days)
    - IV premium analysis (IV vs HV spread)
    - Options strategy selection
    """

    __tablename__ = "historical_iv"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # IV metrics (from IB Gateway)
    iv_30d = Column(Float)  # 30-day ATM implied volatility
    iv_60d = Column(Float)  # 60-day ATM implied volatility (if available)

    # IV Rank/Percentile
    iv_rank_252 = Column(Float)  # Percentile rank over trailing 252 days (0-100)
    iv_high_252 = Column(Float)  # Highest IV in past 252 days
    iv_low_252 = Column(Float)  # Lowest IV in past 252 days

    # Historical volatility comparison
    hv_20d = Column(Float)  # 20-day historical (realized) volatility
    hv_60d = Column(Float)  # 60-day historical volatility
    iv_hv_spread = Column(Float)  # IV - HV premium (positive = IV > HV)

    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_historical_iv_symbol_date"),
        Index("ix_historical_iv_symbol_date", "symbol", "date"),
    )

    def __repr__(self) -> str:
        return f"<HistoricalIV {self.symbol} {self.date} iv_30d={self.iv_30d}>"
