"""Broker execution abstraction layer.

Provides a unified interface for order execution across multiple brokerages
(IBKR, TastyTrade, Schwab) with pre-trade risk gating and order
lifecycle management.

Eager imports are avoided: importing submodules (e.g. ``runner_state_service``)
must not load OrderManager, Redis, or the full broker graph.

medallion: execution
"""

from __future__ import annotations

import importlib
from typing import Any, List

__all__ = [
    "BrokerExecutor",
    "OrderRequest",
    "OrderResult",
    "BrokerRouter",
    "RiskGate",
    "RiskViolation",
    "OrderManager",
    "PaperExecutor",
]


def __getattr__(name: str) -> Any:
    if name in ("BrokerExecutor", "OrderRequest", "OrderResult"):
        m = importlib.import_module("backend.services.execution.broker_base")
        return getattr(m, name)
    if name == "BrokerRouter":
        return importlib.import_module("backend.services.execution.broker_router").BrokerRouter
    if name in ("RiskGate", "RiskViolation"):
        m = importlib.import_module("backend.services.execution.risk_gate")
        return getattr(m, name)
    if name == "OrderManager":
        return importlib.import_module("backend.services.execution.order_manager").OrderManager
    if name == "PaperExecutor":
        return importlib.import_module("backend.services.execution.paper_executor").PaperExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> List[str]:
    return sorted(__all__)
