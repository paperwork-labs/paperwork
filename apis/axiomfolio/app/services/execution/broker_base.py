"""Abstract broker executor protocol and shared data types.

medallion: execution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ActionSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class IBOrderType(str, Enum):
    MKT = "MKT"
    LMT = "LMT"
    STP = "STP"
    STP_LMT = "STP_LMT"


ORDER_TYPE_MAP = {
    "market": IBOrderType.MKT,
    "limit": IBOrderType.LMT,
    "stop": IBOrderType.STP,
    "stop_limit": IBOrderType.STP_LMT,
}


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: ActionSide
    order_type: IBOrderType
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None
    account_id: str | None = None

    @classmethod
    def from_user_input(
        cls,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        limit_price: float | None = None,
        stop_price: float | None = None,
        account_id: str | None = None,
    ) -> OrderRequest:
        return cls(
            symbol=symbol.upper(),
            side=ActionSide.BUY if side.lower() == "buy" else ActionSide.SELL,
            order_type=ORDER_TYPE_MAP.get(order_type.lower(), IBOrderType.MKT),
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            account_id=account_id,
        )


@dataclass
class OrderResult:
    broker_order_id: str | None = None
    status: str = "error"
    error: str | None = None
    filled_quantity: float = 0
    avg_fill_price: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and self.status != "error"


@dataclass
class PreviewResult:
    estimated_commission: float | None = None
    estimated_margin_impact: float | None = None
    estimated_equity_with_loan: float | None = None
    maintenance_margin: float | None = None
    initial_margin: float | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None


@runtime_checkable
class BrokerExecutor(Protocol):
    """Protocol that all broker implementations must satisfy."""

    @property
    def broker_name(self) -> str: ...

    async def connect(self) -> bool: ...

    async def disconnect(self) -> None: ...

    async def preview_order(self, req: OrderRequest) -> PreviewResult: ...

    async def place_order(self, req: OrderRequest) -> OrderResult: ...

    async def cancel_order(self, broker_order_id: str) -> OrderResult: ...

    async def get_order_status(self, broker_order_id: str) -> OrderResult: ...

    def is_paper_trading(self) -> bool: ...
