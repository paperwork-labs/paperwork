"""
FMP (Financial Modeling Prep) Provider Implementation
=====================================================

Market data provider using Financial Modeling Prep API.
Requires API key, has generous free tier (250 calls/day).

Medallion layer: bronze. See docs/ARCHITECTURE.md and D127.

medallion: silver
"""

import logging
from datetime import date

import httpx
import pandas as pd

from app.config import settings

from .protocol import MarketDataProvider

logger = logging.getLogger(__name__)

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"
_FMP_HTTP_TIMEOUT = httpx.Timeout(30.0)


class FMPProvider(MarketDataProvider):
    """Market data provider using Financial Modeling Prep API."""

    def __init__(self):
        self.api_key = getattr(settings, "FMP_API_KEY", None)

    @property
    def name(self) -> str:
        return "FMP"

    @property
    def requires_api_key(self) -> bool:
        return True

    def is_available(self) -> bool:
        """Check if FMP API key is configured."""
        return bool(self.api_key)

    async def get_quotes(self, symbols: list[str]) -> dict[str, float]:
        """Get current prices for multiple symbols."""
        if not self.is_available():
            return {}

        result = {}
        try:
            # FMP supports batch quote endpoint
            symbols_str = ",".join(symbols)
            url = f"{FMP_BASE_URL}/quote/{symbols_str}?apikey={self.api_key}"

            async with httpx.AsyncClient(timeout=_FMP_HTTP_TIMEOUT) as client:
                response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    symbol = item.get("symbol")
                    price = item.get("price")
                    if symbol and price:
                        result[symbol] = price

        except Exception as e:
            logger.warning("FMP batch quote failed: %s", e)

        return result

    async def get_historical(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Get OHLCV historical data."""
        if not self.is_available():
            return pd.DataFrame()

        try:
            url = f"{FMP_BASE_URL}/historical-price-full/{symbol}"
            params = {
                "from": start.isoformat(),
                "to": end.isoformat(),
                "apikey": self.api_key,
            }

            async with httpx.AsyncClient(timeout=_FMP_HTTP_TIMEOUT) as client:
                response = await client.get(url, params=params)
            if response.status_code != 200:
                return pd.DataFrame()

            data = response.json()
            historical = data.get("historical", [])

            if not historical:
                return pd.DataFrame()

            df = pd.DataFrame(historical)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

            # Standardize column names
            df = df.rename(
                columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                }
            )

            cols = ["Open", "High", "Low", "Close", "Volume"]
            available_cols = [c for c in cols if c in df.columns]
            return df[available_cols].sort_index()

        except Exception as e:
            logger.warning("FMP historical fetch failed for %s: %s", symbol, e)
            return pd.DataFrame()

    async def get_fundamentals(self, symbol: str) -> dict:
        """Get company fundamentals."""
        if not self.is_available():
            return {}

        result = {}
        try:
            url = f"{FMP_BASE_URL}/profile/{symbol}?apikey={self.api_key}"
            async with httpx.AsyncClient(timeout=_FMP_HTTP_TIMEOUT) as client:
                response = await client.get(url)

            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    profile = data[0]
                    result = {
                        "name": profile.get("companyName"),
                        "sector": profile.get("sector"),
                        "industry": profile.get("industry"),
                        "market_cap": profile.get("mktCap"),
                        "pe_ratio": profile.get("pe"),
                        "eps": profile.get("eps"),
                        "beta": profile.get("beta"),
                        "dividend_yield": profile.get("lastDiv"),
                        "exchange": profile.get("exchange"),
                        "ceo": profile.get("ceo"),
                        "description": profile.get("description"),
                    }

        except Exception as e:
            logger.warning("FMP fundamentals fetch failed for %s: %s", symbol, e)

        return result

    def supports_intraday(self) -> bool:
        """FMP supports intraday data on paid plans."""
        return True

    def rate_limit(self) -> int | None:
        """FMP rate limit (calls/min) derived from ProviderPolicy."""
        try:
            from app.config import settings

            return settings.provider_policy.fmp_cpm
        except Exception:
            return 700
