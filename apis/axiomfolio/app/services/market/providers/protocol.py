"""
Market Data Provider Protocol
=============================

Abstract base / Protocol for all market data providers.
Ensures consistent interface across FMP, yfinance, Finnhub, Twelve Data, etc.

medallion: silver
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, List, Optional

import pandas as pd


class MarketDataProvider(ABC):
    """Abstract interface all data providers must implement.

    This ensures consistent method signatures across providers
    and enables easy switching or fallback between providers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g., 'FMP', 'yfinance')."""
        ...

    @property
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Whether this provider needs an API key to function."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and reachable.

        Returns True if the provider can be used right now.
        Should check API key presence, network connectivity, etc.
        """
        ...

    @abstractmethod
    async def get_quotes(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for multiple symbols.

        Args:
            symbols: List of ticker symbols (e.g., ['AAPL', 'MSFT'])

        Returns:
            Dict mapping symbol to current price (or None if unavailable)
        """
        ...

    @abstractmethod
    async def get_historical(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Get OHLCV historical data for a symbol.

        Args:
            symbol: Ticker symbol
            start: Start date (inclusive)
            end: End date (inclusive)
            interval: Data interval ('1d', '1h', '5m', etc.)

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
            Index should be DatetimeIndex
        """
        ...

    @abstractmethod
    async def get_fundamentals(self, symbol: str) -> Dict:
        """Get company fundamentals for a symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            Dict with keys like: name, sector, industry, market_cap,
            pe_ratio, eps, revenue_growth, etc.
        """
        ...

    async def get_quote(self, symbol: str) -> Optional[float]:
        """Convenience method: get single quote.

        Default implementation calls get_quotes with single symbol.
        """
        quotes = await self.get_quotes([symbol])
        return quotes.get(symbol)

    def supports_intraday(self) -> bool:
        """Whether this provider supports intraday (minute) data.

        Override in subclass if supported.
        """
        return False

    def rate_limit(self) -> Optional[int]:
        """Requests per minute allowed, or None if unlimited."""
        return None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"
