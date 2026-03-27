"""Broker router -- resolves the correct executor for a given broker type."""

from __future__ import annotations

import logging
from typing import Dict

from backend.services.execution.broker_base import BrokerExecutor

logger = logging.getLogger(__name__)


class BrokerRouter:
    """Registry that maps broker type strings to BrokerExecutor instances.

    Usage:
        router = BrokerRouter()
        router.register("ibkr", IBKRExecutor())
        executor = router.get("ibkr")
    """

    def __init__(self):
        self._executors: Dict[str, BrokerExecutor] = {}

    def register(self, broker_type: str, executor: BrokerExecutor) -> None:
        self._executors[broker_type.lower()] = executor
        logger.info("Registered broker executor: %s", broker_type)

    def get(self, broker_type: str) -> BrokerExecutor:
        executor = self._executors.get(broker_type.lower())
        if executor is None:
            available = ", ".join(self._executors.keys()) or "(none)"
            raise ValueError(
                f"No executor registered for broker '{broker_type}'. "
                f"Available: {available}"
            )
        return executor

    @property
    def available_brokers(self) -> list[str]:
        return list(self._executors.keys())


def create_default_router() -> BrokerRouter:
    """Factory that wires up all available broker executors."""
    from backend.services.execution.ibkr_executor import IBKRExecutor
    from backend.services.execution.alpaca_executor import AlpacaExecutor
    from backend.services.execution.paper_executor import PaperExecutor

    router = BrokerRouter()
    router.register("ibkr", IBKRExecutor())
    router.register("alpaca", AlpacaExecutor())
    router.register("paper", PaperExecutor())
    return router


broker_router = create_default_router()
