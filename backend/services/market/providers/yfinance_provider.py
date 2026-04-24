"""
yfinance Provider Implementation
================================

Free market data provider using Yahoo Finance via yfinance library.
No API key required, but has rate limits.

Medallion layer: bronze. See docs/ARCHITECTURE.md and D127.

medallion: silver
"""

import logging
from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from .protocol import MarketDataProvider

logger = logging.getLogger(__name__)


class YFinanceProvider(MarketDataProvider):
    """Market data provider using yfinance (Yahoo Finance)."""

    @property
    def name(self) -> str:
        return "yfinance"

    @property
    def requires_api_key(self) -> bool:
        return False

    def is_available(self) -> bool:
        """yfinance is always available (no API key needed)."""
        try:
            import yfinance
            return True
        except ImportError:
            logger.warning("yfinance package not installed")
            return False

    async def get_quotes(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for multiple symbols."""
        import yfinance as yf

        result = {}
        try:
            # yfinance batch download
            tickers = yf.Tickers(" ".join(symbols))
            for symbol in symbols:
                try:
                    ticker = tickers.tickers.get(symbol)
                    if ticker:
                        info = ticker.fast_info
                        result[symbol] = info.get("lastPrice") or info.get("previousClose")
                except Exception as e:
                    logger.debug("Quote fetch failed for %s: %s", symbol, e)
        except Exception as e:
            logger.warning("Batch quote fetch failed: %s", e)

        return result

    async def get_historical(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Get OHLCV historical data."""
        import yfinance as yf

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start.isoformat(),
                end=end.isoformat(),
                interval=interval,
            )

            if df.empty:
                return pd.DataFrame()

            # Standardize column names
            df = df.rename(columns={
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Volume": "Volume",
            })

            # Select only OHLCV columns
            cols = ["Open", "High", "Low", "Close", "Volume"]
            available_cols = [c for c in cols if c in df.columns]
            return df[available_cols]

        except Exception as e:
            logger.warning("Historical fetch failed for %s: %s", symbol, e)
            return pd.DataFrame()

    async def get_fundamentals(self, symbol: str) -> Dict:
        """Get company fundamentals."""
        import yfinance as yf

        result = {}
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}

            result = {
                "name": info.get("shortName") or info.get("longName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "eps": info.get("trailingEps"),
                "dividend_yield": info.get("dividendYield"),
                "beta": info.get("beta"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
            }

        except Exception as e:
            logger.warning("Fundamentals fetch failed for %s: %s", symbol, e)

        return result

    def supports_intraday(self) -> bool:
        """yfinance supports some intraday data."""
        return True

    def rate_limit(self) -> Optional[int]:
        """yfinance rate limit derived from ProviderPolicy."""
        try:
            from backend.config import settings
            return settings.provider_policy.yfinance_cpm
        except Exception:
            return 30
