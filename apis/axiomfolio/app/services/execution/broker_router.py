"""Broker router -- resolves the correct executor for a given broker type.

medallion: execution
"""

from __future__ import annotations

import logging

from app.services.execution.broker_base import BrokerExecutor

logger = logging.getLogger(__name__)


class BrokerRouter:
    """Registry that maps broker type strings to BrokerExecutor instances.

    Usage:
        router = BrokerRouter()
        router.register("ibkr", IBKRExecutor())
        executor = router.get("ibkr")
    """

    def __init__(self):
        self._executors: dict[str, BrokerExecutor] = {}

    def register(self, broker_type: str, executor: BrokerExecutor) -> None:
        self._executors[broker_type.lower()] = executor
        logger.info("Registered broker executor: %s", broker_type)

    def get(self, broker_type: str) -> BrokerExecutor:
        executor = self._executors.get(broker_type.lower())
        if executor is None:
            available = ", ".join(self._executors.keys()) or "(none)"
            raise ValueError(
                f"No executor registered for broker '{broker_type}'. Available: {available}"
            )
        return executor

    @property
    def available_brokers(self) -> list[str]:
        return list(self._executors.keys())


def create_default_router() -> BrokerRouter:
    """Wire up every available broker executor.

    Convention for live brokers:

    * The sandbox/test variant (``<broker>_sandbox``) is always registered so
      preview, place, and reconciliation paths can be exercised without real
      capital.
    * The live variant (``<broker>``) is gated behind a per-broker
      ``<BROKER>_ALLOW_LIVE`` boolean setting. The gate is enforced both at
      the executor constructor (raises ``RuntimeError``) and at registration
      time (skips ``register`` and logs the decision). This double-gate is
      deliberate: an accidental ``broker_type="<broker>"`` cannot route a
      real order until an operator explicitly flips the flag.
    """
    from app.config import settings
    from app.services.execution.coinbase_paper_executor import CoinbasePaperExecutor
    from app.services.execution.etrade_executor import ETradeExecutor
    from app.services.execution.ibkr_executor import IBKRExecutor
    from app.services.execution.paper_executor import PaperExecutor
    from app.services.execution.schwab_executor import SchwabExecutor
    from app.services.execution.tastytrade_executor import TastytradeExecutor
    from app.services.execution.tradier_executor import TradierExecutor

    router = BrokerRouter()

    # Equity / options brokers
    router.register("ibkr", IBKRExecutor())
    router.register("paper", PaperExecutor())

    # Crypto routes through a paper-only executor that rejects non-crypto
    # symbols at the edge. A live Coinbase executor will register under the
    # same broker id once it ships.
    router.register("coinbase", CoinbasePaperExecutor())

    # Schwab live executor. Registered without a context resolver; write
    # paths return a clear "not bound" OrderResult.error until the
    # order_manager integration wires the per-request session and
    # BrokerOAuthConnection. Never silently succeeds.
    router.register("schwab", SchwabExecutor())

    # Tradier: live + sandbox share one executor class, parameterized by
    # environment. Both share the OAuth token-refresh lock.
    router.register("tradier", TradierExecutor(environment="prod"))
    router.register("tradier_sandbox", TradierExecutor(environment="sandbox"))

    # E*TRADE: sandbox always available; live gated by ETRADE_ALLOW_LIVE.
    router.register("etrade_sandbox", ETradeExecutor(environment="sandbox"))
    if bool(getattr(settings, "ETRADE_ALLOW_LIVE", False)):
        router.register("etrade", ETradeExecutor(environment="prod"))
    else:
        logger.info(
            "E*TRADE live executor not registered (ETRADE_ALLOW_LIVE=false); "
            "sandbox remains available as 'etrade_sandbox'"
        )

    # TastyTrade: sandbox always available; live gated by TASTYTRADE_ALLOW_LIVE.
    # Equity orders only today; option-symbol input surfaces an explicit error
    # rather than silently routing through the equity path.
    router.register("tastytrade_sandbox", TastytradeExecutor(environment="sandbox"))
    if bool(getattr(settings, "TASTYTRADE_ALLOW_LIVE", False)):
        router.register("tastytrade", TastytradeExecutor(environment="prod"))
    else:
        logger.info(
            "TastyTrade live executor not registered (TASTYTRADE_ALLOW_LIVE=false); "
            "sandbox remains available as 'tastytrade_sandbox'"
        )

    return router


broker_router = create_default_router()
