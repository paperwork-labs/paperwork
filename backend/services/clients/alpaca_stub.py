"""Alpaca Broker Adapter — stub for next-sprint implementation.

Implements BrokerAdapter ABC but raises NotImplementedError on all methods.
Will be replaced with a full implementation using alpaca-py SDK.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from backend.services.execution.broker_adapter import BrokerAdapter

logger = logging.getLogger(__name__)


class AlpacaAdapter(BrokerAdapter):

    async def connect(self, **kwargs) -> bool:
        raise NotImplementedError("Alpaca adapter not yet implemented")

    async def get_positions(self, account_id: str) -> List[Dict]:
        raise NotImplementedError("Alpaca adapter not yet implemented")

    async def get_balances(self, account_id: str) -> Dict:
        raise NotImplementedError("Alpaca adapter not yet implemented")

    async def submit_order(
        self,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        **kwargs,
    ) -> Dict:
        raise NotImplementedError("Alpaca adapter not yet implemented")

    async def cancel_order(self, broker_order_id: str) -> Dict:
        raise NotImplementedError("Alpaca adapter not yet implemented")

    async def get_order_status(self, broker_order_id: str) -> Dict:
        raise NotImplementedError("Alpaca adapter not yet implemented")

    async def disconnect(self) -> None:
        raise NotImplementedError("Alpaca adapter not yet implemented")
