"""
Institutional Holdings Model
============================

13F filings data from SEC EDGAR for institutional ownership tracking.
"""

from datetime import date
from sqlalchemy import Column, Integer, String, BigInteger, Float, Date, Index, UniqueConstraint
from app.models import Base


class InstitutionalHolding(Base):
    """Institutional holdings from SEC 13F filings.

    Table name: institutional_holdings
    Primary source: SEC EDGAR (free, quarterly, 45-day delay)

    Used for:
    - Tracking institutional ownership changes
    - Identifying accumulation/distribution patterns
    - Smart money flow analysis
    """

    __tablename__ = "institutional_holdings"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    filing_date = Column(Date, nullable=False, index=True)
    period_date = Column(Date, nullable=False)  # Quarter end date

    # Institution info
    institution_cik = Column(String(20), nullable=False, index=True)
    institution_name = Column(String(200))

    # Position data
    shares = Column(BigInteger)  # Number of shares held
    value_usd = Column(BigInteger)  # Market value in USD (SEC reports in thousands)
    share_class = Column(String(20))  # COM, CL A, CL B, etc.

    # Change metrics (vs prior quarter)
    change_shares = Column(BigInteger)  # Delta in shares
    change_pct = Column(Float)  # Percentage change

    # Filing metadata
    accession_number = Column(String(40))  # SEC accession number for audit

    __table_args__ = (
        UniqueConstraint(
            "symbol", "filing_date", "institution_cik",
            name="uq_institutional_holding_symbol_date_inst"
        ),
        Index("ix_institutional_holdings_symbol_period", "symbol", "period_date"),
    )

    def __repr__(self) -> str:
        return f"<InstitutionalHolding {self.symbol} {self.institution_name[:30] if self.institution_name else 'N/A'}>"
