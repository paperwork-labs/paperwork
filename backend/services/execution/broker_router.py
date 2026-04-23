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
    from backend.config import settings
    from backend.services.execution.ibkr_executor import IBKRExecutor
    from backend.services.execution.paper_executor import PaperExecutor
    from backend.services.execution.coinbase_paper_executor import CoinbasePaperExecutor
    from backend.services.execution.schwab_executor import SchwabExecutor
    from backend.services.execution.tradier_executor import TradierExecutor
    from backend.services.execution.etrade_executor import ETradeExecutor

    router = BrokerRouter()
    router.register("ibkr", IBKRExecutor())
    router.register("paper", PaperExecutor())
    # Wave F Phase 0: crypto goes through a dedicated paper executor that
    # rejects non-crypto symbols at the edge (issue #473). Live Coinbase lands
    # in a later phase.
    router.register("coinbase", CoinbasePaperExecutor())
    # Wave F Phase F3: Schwab live executor. The singleton is registered
    # without a context_resolver; the order_manager integration (wiring the
    # per-request Session + BrokerOAuthConnection) lands in a follow-up PR.
    # Until then, any write call raises a clear "not bound" error via
    # OrderResult.error -- never a silent fallback.
    router.register("schwab", SchwabExecutor())
    # Wave F Phase 1: Tradier live + sandbox share one executor class,
    # parameterized by environment. Both registrations use the same OAuth
    # token-refresh lock from the F0 mixin.
    router.register("tradier", TradierExecutor(environment="prod"))
    router.register("tradier_sandbox", TradierExecutor(environment="sandbox"))
    # Wave F Phase 2: E*TRADE live executor. Sandbox is always registered so
    # the rest of the stack can exercise the 2-step preview → place flow
    # against the provider sandbox. Prod is gated behind ETRADE_ALLOW_LIVE
    # so an accidental `broker_type="etrade"` cannot route real orders until
    # a founder explicitly flips the flag. See etrade_executor.py docstring.
    router.register("etrade_sandbox", ETradeExecutor(environment="sandbox"))
    if bool(getattr(settings, "ETRADE_ALLOW_LIVE", False)):
        router.register("etrade", ETradeExecutor(environment="prod"))
    else:
        logger.info(
            "E*TRADE prod executor NOT registered (ETRADE_ALLOW_LIVE=%s); "
            "sandbox remains available as 'etrade_sandbox'",
            bool(getattr(settings, "ETRADE_ALLOW_LIVE", False)),
        )
    return router


broker_router = create_default_router()
