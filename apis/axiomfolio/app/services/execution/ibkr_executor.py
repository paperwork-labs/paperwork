"""IBKR executor -- adapts the existing IBKRClient to BrokerExecutor protocol.

medallion: execution
"""

from __future__ import annotations

import logging

from app.services.execution.broker_base import (
    OrderRequest,
    OrderResult,
    PreviewResult,
)

logger = logging.getLogger(__name__)


class IBKRExecutor:
    """BrokerExecutor implementation backed by the existing IBKRClient singleton."""

    def __init__(self):
        self._client = None

    @property
    def _ibkr(self):
        if self._client is None:
            from app.services.clients.ibkr_client import ibkr_client

            self._client = ibkr_client
        return self._client

    @property
    def broker_name(self) -> str:
        return "ibkr"

    async def connect(self) -> bool:
        return await self._ibkr._ensure_connected()

    async def disconnect(self) -> None:
        await self._ibkr.disconnect()

    async def preview_order(self, req: OrderRequest) -> PreviewResult:
        raw = await self._ibkr.what_if_order(
            symbol=req.symbol,
            action=req.side.value,
            quantity=req.quantity,
            order_type=req.order_type.value,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
        )
        if raw.get("error"):
            return PreviewResult(error=raw["error"], raw=raw)
        return PreviewResult(
            estimated_commission=raw.get("estimated_commission"),
            estimated_margin_impact=raw.get("estimated_margin_impact"),
            estimated_equity_with_loan=raw.get("estimated_equity_with_loan"),
            maintenance_margin=raw.get("maintenance_margin"),
            initial_margin=raw.get("initial_margin"),
            raw=raw,
        )

    async def place_order(self, req: OrderRequest) -> OrderResult:
        raw = await self._ibkr.place_order(
            symbol=req.symbol,
            action=req.side.value,
            quantity=req.quantity,
            order_type=req.order_type.value,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
        )
        if raw.get("error"):
            return OrderResult(
                status=raw.get("status", "error"),
                error=raw["error"],
                raw=raw,
            )
        return OrderResult(
            broker_order_id=str(raw.get("broker_order_id", "")),
            status=raw.get("status", "submitted"),
            raw=raw,
        )

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        raw = await self._ibkr.cancel_order(broker_order_id)
        if raw.get("error"):
            return OrderResult(error=raw["error"], raw=raw)
        return OrderResult(
            broker_order_id=broker_order_id,
            status="cancelled",
            raw=raw,
        )

    async def get_order_status(self, broker_order_id: str) -> OrderResult:
        raw = await self._ibkr.get_order_status(broker_order_id)
        return OrderResult(
            broker_order_id=broker_order_id,
            status=raw.get("status", "unknown"),
            filled_quantity=raw.get("filled", 0) or 0,
            avg_fill_price=raw.get("avg_fill_price"),
            raw=raw,
        )

    def is_paper_trading(self) -> bool:
        return self._ibkr._is_paper_trading()
