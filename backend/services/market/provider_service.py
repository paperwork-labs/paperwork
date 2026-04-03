from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session


class MarketDataProviderService:
    """Provider access facade for MarketDataService."""

    def __init__(self, service) -> None:
        self._service = service

    async def get_current_price(self, symbol: str) -> Optional[float]:
        return await self._service.get_current_price(symbol)

    async def get_historical_data(
        self,
        symbol: str,
        *,
        period: str = "1y",
        interval: str = "1d",
        max_bars: int | None = None,
        return_provider: bool = False,
        db: Optional[Session] = None,
    ):
        return await self._service.get_historical_data(
            symbol,
            period=period,
            interval=interval,
            max_bars=max_bars,
            return_provider=return_provider,
            db=db,
        )

    def get_fundamentals_info(self, symbol: str) -> Dict[str, Any]:
        return self._service.get_fundamentals_info(symbol)
