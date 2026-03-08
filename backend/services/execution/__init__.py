"""Broker execution abstraction layer.

Provides a unified interface for order execution across multiple brokerages
(IBKR, Alpaca, TastyTrade, Schwab) with pre-trade risk gating and order
lifecycle management.
"""

from .broker_base import BrokerExecutor, OrderRequest, OrderResult
from .broker_router import BrokerRouter
from .risk_gate import RiskGate, RiskViolation
from .order_manager import OrderManager

__all__ = [
    "BrokerExecutor",
    "OrderRequest",
    "OrderResult",
    "BrokerRouter",
    "RiskGate",
    "RiskViolation",
    "OrderManager",
]
