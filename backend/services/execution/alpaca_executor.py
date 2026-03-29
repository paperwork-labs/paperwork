"""Alpaca broker executor implementing BrokerExecutor protocol."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.services.execution.broker_base import (
    OrderRequest,
    OrderResult,
    PreviewResult,
)

logger = logging.getLogger(__name__)

_ORDER_TYPE_MAP = {
    "MKT": "market",
    "LMT": "limit",
    "STP": "stop",
    "STP_LMT": "stop_limit",
}


class AlpacaExecutor:
    """BrokerExecutor implementation for Alpaca Markets.

    Uses Alpaca's REST API for order management.
    Paper trading via paper-api.alpaca.markets, live via api.alpaca.markets.
    """

    def __init__(self):
        self._client = None

    @property
    def broker_name(self) -> str:
        return "alpaca"

    def _get_base_url(self) -> str:
        mode = getattr(settings, "ALPACA_TRADING_MODE", "paper").lower()
        if mode == "live":
            return "https://api.alpaca.markets"
        return "https://paper-api.alpaca.markets"

    def _get_headers(self) -> Dict[str, str]:
        api_key = getattr(settings, "ALPACA_API_KEY", "") or ""
        api_secret = getattr(settings, "ALPACA_API_SECRET", "") or ""
        return {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
            "Content-Type": "application/json",
        }

    async def connect(self) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._get_base_url()}/v2/account",
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    self._client = True
                    logger.info("Connected to Alpaca (%s)", self._get_base_url())
                    return True
                logger.error("Alpaca connection failed: %s", resp.text)
                return False
        except Exception as e:
            logger.error("Alpaca connection error: %s", e)
            return False

    async def disconnect(self) -> None:
        self._client = None

    async def preview_order(self, req: OrderRequest) -> PreviewResult:
        return PreviewResult(
            estimated_commission=0.0,
            raw={"note": "Alpaca does not support whatIf preview"},
        )

    async def place_order(self, req: OrderRequest) -> OrderResult:
        try:
            import httpx

            order_body: Dict[str, str] = {
                "symbol": req.symbol,
                "qty": str(req.quantity),
                "side": req.side.value.lower(),
                "type": _ORDER_TYPE_MAP.get(req.order_type.value, "market"),
                "time_in_force": "day",
            }
            if req.limit_price is not None:
                order_body["limit_price"] = str(req.limit_price)
            if req.stop_price is not None:
                order_body["stop_price"] = str(req.stop_price)

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._get_base_url()}/v2/orders",
                    headers=self._get_headers(),
                    json=order_body,
                )

                if resp.status_code in (200, 201):
                    data = resp.json()
                    return OrderResult(
                        broker_order_id=data.get("id"),
                        status=data.get("status", "accepted"),
                        raw=data,
                    )
                return OrderResult(
                    error=f"Alpaca order failed: {resp.status_code} {resp.text}",
                    raw={"status_code": resp.status_code},
                )
        except Exception as e:
            return OrderResult(error=str(e))

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.delete(
                    f"{self._get_base_url()}/v2/orders/{broker_order_id}",
                    headers=self._get_headers(),
                )
                if resp.status_code in (200, 204):
                    return OrderResult(
                        broker_order_id=broker_order_id, status="cancelled"
                    )
                return OrderResult(error=f"Cancel failed: {resp.status_code}")
        except Exception as e:
            return OrderResult(error=str(e))

    async def get_order_status(self, broker_order_id: str) -> OrderResult:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._get_base_url()}/v2/orders/{broker_order_id}",
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return OrderResult(
                        broker_order_id=broker_order_id,
                        status=data.get("status", "unknown"),
                        filled_quantity=float(data.get("filled_qty", 0)),
                        avg_fill_price=(
                            float(data["filled_avg_price"])
                            if data.get("filled_avg_price")
                            else None
                        ),
                        raw=data,
                    )
                return OrderResult(
                    error=f"Status check failed: {resp.status_code}"
                )
        except Exception as e:
            return OrderResult(error=str(e))

    def is_paper_trading(self) -> bool:
        return getattr(settings, "ALPACA_TRADING_MODE", "paper").lower() != "live"

    async def get_positions(self) -> list:
        """Get all open positions from Alpaca."""
        try:
            import httpx
            from dataclasses import dataclass

            @dataclass
            class AlpacaPosition:
                symbol: str
                qty: str
                avg_entry_price: str
                market_value: str
                unrealized_pl: str
                side: str

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._get_base_url()}/v2/positions",
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [
                        AlpacaPosition(
                            symbol=p.get("symbol", ""),
                            qty=p.get("qty", "0"),
                            avg_entry_price=p.get("avg_entry_price", "0"),
                            market_value=p.get("market_value", "0"),
                            unrealized_pl=p.get("unrealized_pl", "0"),
                            side=p.get("side", "long"),
                        )
                        for p in data
                    ]
                logger.error("Alpaca get_positions failed: %s", resp.text)
                return []
        except Exception as e:
            logger.error("Alpaca get_positions error: %s", e)
            return []

    async def get_account(self) -> dict:
        """Get account information from Alpaca."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._get_base_url()}/v2/account",
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Account fetch failed: {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    async def get_account_activities(
        self,
        activity_types: str = "FILL",
        after: Optional[str] = None,
        until: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch account activities (trades/fills) from Alpaca.
        
        Args:
            activity_types: Comma-separated activity types (default: FILL)
            after: ISO timestamp for start date
            until: ISO timestamp for end date
            page_size: Results per page (max 100)
            
        Returns:
            List of activity objects with trade details
        """
        import httpx

        all_activities: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                while True:
                    params: Dict[str, Any] = {
                        "activity_types": activity_types,
                        "page_size": page_size,
                    }
                    if after:
                        params["after"] = after
                    if until:
                        params["until"] = until
                    if page_token:
                        params["page_token"] = page_token

                    resp = await client.get(
                        f"{self._get_base_url()}/v2/account/activities",
                        headers=self._get_headers(),
                        params=params,
                    )

                    if resp.status_code != 200:
                        logger.error(
                            "Alpaca activities fetch failed: %s %s",
                            resp.status_code,
                            resp.text[:200],
                        )
                        break

                    data = resp.json()
                    if not data:
                        break

                    all_activities.extend(data)

                    # Alpaca uses last activity ID as cursor
                    if len(data) < page_size:
                        break
                    page_token = data[-1].get("id")
                    if not page_token:
                        break

        except Exception as e:
            logger.error("Alpaca get_account_activities error: %s", e)

        return all_activities
