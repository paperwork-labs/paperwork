"""
Regime Inputs Gatherer
======================

Centralized module for fetching all regime engine inputs:
- VIX, VIX3M, VVIX from yfinance
- NH-NL (New Highs minus New Lows) from yfinance ^NYHILO
- Breadth from MarketSnapshot (% above 200D SMA, % above 50D SMA)
- Sector RS calculation using sector ETFs

medallion: silver
"""

import logging

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.models.market_data import MarketSnapshot
from app.services.market.regime_engine import RegimeInputs

logger = logging.getLogger(__name__)


# Sector ETF tickers for sector RS calculation
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLC": "Communication Services",
}


def fetch_vix_family() -> dict[str, float]:
    """Fetch VIX, VIX3M, and VVIX spot values from yfinance.

    Returns dict with keys: vix_spot, vix3m, vvix
    """
    result = {
        "vix_spot": 20.0,  # Default fallback
        "vix3m": 20.0,
        "vvix": 80.0,
    }

    try:
        import yfinance as yf

        vix_df = yf.download("^VIX", period="5d", progress=False)
        if vix_df is not None and len(vix_df) > 0:
            result["vix_spot"] = float(vix_df["Close"].iloc[-1])

        vix3m_df = yf.download("^VIX3M", period="5d", progress=False)
        if vix3m_df is not None and len(vix3m_df) > 0:
            result["vix3m"] = float(vix3m_df["Close"].iloc[-1])

        vvix_df = yf.download("^VVIX", period="5d", progress=False)
        if vvix_df is not None and len(vvix_df) > 0:
            result["vvix"] = float(vvix_df["Close"].iloc[-1])

    except Exception as exc:
        logger.warning("Failed to fetch VIX family data: %s", exc)

    return result


def fetch_nh_nl() -> int:
    """Fetch NYSE New Highs minus New Lows from yfinance.

    Uses ^NYHILO index which tracks net new highs (NH - NL).
    Positive = more new highs, bullish breadth
    Negative = more new lows, bearish breadth
    """
    try:
        import yfinance as yf

        # ^NYHILO is the NYSE High-Low Index (NH - NL)
        df = yf.download("^NYHILO", period="5d", progress=False)
        if df is not None and len(df) > 0:
            return int(df["Close"].iloc[-1])
    except Exception as exc:
        logger.warning("Failed to fetch NH-NL data: %s", exc)

    return 0  # Default to neutral


def compute_breadth_from_snapshots(db: Session) -> dict[str, float]:
    """Compute breadth metrics from current MarketSnapshot data.

    Returns:
        pct_above_200d: % of symbols above their 200-day SMA
        pct_above_50d: % of symbols above their 50-day SMA
    """
    total = (
        db.query(sqlfunc.count(MarketSnapshot.id))
        .filter(
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.is_valid.is_(True),
        )
        .scalar()
        or 1
    )

    above_200 = (
        db.query(sqlfunc.count(MarketSnapshot.id))
        .filter(
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.is_valid.is_(True),
            MarketSnapshot.sma_200 > 0,
            MarketSnapshot.current_price >= MarketSnapshot.sma_200,
        )
        .scalar()
        or 0
    )

    above_50 = (
        db.query(sqlfunc.count(MarketSnapshot.id))
        .filter(
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.is_valid.is_(True),
            MarketSnapshot.sma_50 > 0,
            MarketSnapshot.current_price >= MarketSnapshot.sma_50,
        )
        .scalar()
        or 0
    )

    return {
        "pct_above_200d": round(100 * above_200 / total, 2) if total > 0 else 50.0,
        "pct_above_50d": round(100 * above_50 / total, 2) if total > 0 else 50.0,
    }


def gather_regime_inputs(db: Session) -> RegimeInputs:
    """Fetch all inputs needed for regime computation in one place.

    This is the single source of truth for regime input gathering.
    """
    # Fetch VIX family
    vix_data = fetch_vix_family()
    vix_spot = vix_data["vix_spot"]
    vix3m = vix_data["vix3m"]
    vvix = vix_data["vvix"]

    # Calculate ratios
    vix3m_vix_ratio = vix3m / vix_spot if vix_spot > 0 else 1.0
    vvix_vix_ratio = vvix / vix_spot if vix_spot > 0 else 1.0

    # Fetch NH-NL
    nh_nl = fetch_nh_nl()

    # Compute breadth from snapshots
    breadth = compute_breadth_from_snapshots(db)

    return RegimeInputs(
        vix_spot=vix_spot,
        vix3m_vix_ratio=vix3m_vix_ratio,
        vvix_vix_ratio=vvix_vix_ratio,
        nh_nl=nh_nl,
        pct_above_200d=breadth["pct_above_200d"],
        pct_above_50d=breadth["pct_above_50d"],
    )


def compute_sector_rs(db: Session, lookback_days: int = 20) -> dict[str, float]:
    """Compute relative strength of sectors vs SPY.

    Returns dict of sector -> RS value (>1 = outperforming, <1 = underperforming)
    """
    sector_rs = {}

    try:
        import yfinance as yf

        # Fetch SPY as benchmark
        spy_df = yf.download("SPY", period=f"{lookback_days + 5}d", progress=False)
        if spy_df is None or len(spy_df) < lookback_days:
            logger.warning("Insufficient SPY data for sector RS calculation")
            return sector_rs

        spy_return = (spy_df["Close"].iloc[-1] / spy_df["Close"].iloc[-lookback_days]) - 1

        # Fetch each sector ETF and compute RS
        for ticker, sector_name in SECTOR_ETFS.items():
            try:
                etf_df = yf.download(ticker, period=f"{lookback_days + 5}d", progress=False)
                if etf_df is None or len(etf_df) < lookback_days:
                    continue

                etf_return = (etf_df["Close"].iloc[-1] / etf_df["Close"].iloc[-lookback_days]) - 1

                # RS = sector return / benchmark return
                # Handle edge cases
                if abs(spy_return) < 0.001:
                    rs = 1.0 + etf_return  # Benchmark flat, use raw return
                else:
                    rs = (1 + etf_return) / (1 + spy_return)

                sector_rs[sector_name] = round(rs, 3)

            except Exception as exc:
                logger.warning("Failed to compute RS for %s: %s", ticker, exc)

    except Exception as exc:
        logger.warning("Sector RS calculation failed: %s", exc)

    return sector_rs


def get_sector_rotation_signal(sector_rs: dict[str, float]) -> dict[str, list[str]]:
    """Identify leading and lagging sectors based on RS values.

    Returns:
        leading: sectors with RS > 1.05 (outperforming by >5%)
        lagging: sectors with RS < 0.95 (underperforming by >5%)
    """
    leading = [name for name, rs in sector_rs.items() if rs > 1.05]
    lagging = [name for name, rs in sector_rs.items() if rs < 0.95]

    # Sort by RS value
    leading = sorted(leading, key=lambda x: sector_rs[x], reverse=True)
    lagging = sorted(lagging, key=lambda x: sector_rs[x])

    return {
        "leading": leading,
        "lagging": lagging,
    }
