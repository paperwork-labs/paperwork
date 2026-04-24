"""Abstract Broker Adapter — unified interface for all broker integrations.

Every broker client (IBKR, Schwab, TastyTrade, etc.) must implement this ABC so that
OrderManager and sync pipelines can interact with them uniformly.

Typed records below (BrokerPosition, BrokerOrder, BrokerBalance, OrderRequest,
OrderResult) are adapter-layer helpers. For the execution order pipeline,
see ``backend.services.execution.broker_base`` for ``OrderRequest`` /
``OrderResult`` (enum-based); those are separate types in another module.

medallion: execution
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional


@dataclass
class BrokerPosition:
    """Open position snapshot (adapter-neutral)."""

    symbol: str
    quantity: Decimal
    average_cost: Decimal
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_pct: Optional[float] = None

    def to_dict(self, account_id: str) -> Dict[str, Any]:
        """Shape aligned with IBKR-style position dicts for sync pipelines."""
        return {
            "account": account_id,
            "symbol": self.symbol,
            "position": float(self.quantity),
            "market_value": float(self.market_value)
            if self.market_value is not None
            else 0.0,
            "avg_cost": float(self.average_cost),
            "unrealized_pnl": float(self.unrealized_pnl)
            if self.unrealized_pnl is not None
            else 0.0,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "contract_type": "STK",
            "currency": "USD",
            "exchange": None,
        }


@dataclass
class BrokerOrder:
    """Order snapshot (adapter-neutral)."""

    order_id: str
    symbol: Optional[str]
    side: str
    quantity: Decimal
    order_type: str
    status: str
    filled_quantity: Decimal
    filled_price: Optional[Decimal] = None
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": str(self.quantity),
            "order_type": self.order_type,
            "status": self.status,
            "filled_quantity": str(self.filled_quantity),
            "filled_price": str(self.filled_price) if self.filled_price is not None else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
        }


@dataclass
class BrokerBalance:
    """Cash and equity snapshot (adapter-neutral)."""

    total_value: Decimal
    cash: Decimal
    buying_power: Decimal
    margin_used: Decimal = Decimal("0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_value": float(self.total_value),
            "cash": float(self.cash),
            "buying_power": float(self.buying_power),
            "margin_used": float(self.margin_used),
            "currency": "USD",
        }


@dataclass(frozen=True)
class OrderRequest:
    """String/Decimal order intent for adapter helpers (not broker_base enums)."""

    symbol: str
    side: str
    quantity: Decimal
    order_type: str
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None


@dataclass
class OrderResult:
    """Outcome of a submit attempt via adapter-layer ``place_order``."""

    success: bool
    order_id: Optional[str] = None
    message: str = ""


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
