"""Abstract Broker Adapter — unified interface for all broker integrations.

Every broker client (IBKR, Alpaca, etc.) must implement this ABC so that
OrderManager and sync pipelines can interact with them uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BrokerAdapter(ABC):

    @abstractmethod
    async def connect(self, **kwargs) -> bool:
        """Establish connection to the broker. Returns True on success."""
        ...

    @abstractmethod
    async def get_positions(self, account_id: str) -> List[Dict]:
        """Return current positions for the given account."""
        ...

    @abstractmethod
    async def get_balances(self, account_id: str) -> Dict:
        """Return account balance summary."""
        ...

    @abstractmethod
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
        """Submit an order to the broker. Returns dict with broker_order_id + status."""
        ...

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> Dict:
        """Cancel a pending order by its broker-assigned ID."""
        ...

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> Dict:
        """Query current status of a placed order."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the broker cleanly."""
        ...
