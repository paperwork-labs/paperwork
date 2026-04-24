"""Coinbase paper-mode executor.

Coinbase is our first crypto broker and currently ships paper-only so the
full trading path (OrderManager → RiskGate → BrokerRouter) can be
exercised end-to-end without any real crypto custody risk.

Live Coinbase Advanced Trade integration lands in a follow-up. Until
then any attempt to place a real-money Coinbase order routes through
this class and is clearly tagged ``paper_mode=True`` in the
``OrderResult.raw`` payload so downstream accounting cannot confuse it
with a live fill.

Symbol enforcement
------------------
RiskGate already routes recognized crypto symbols to
``_check_crypto_sizing``. This executor adds a second, defense-in-depth guard
at the edge: if the order symbol does not look like crypto we reject it
immediately rather than let a mis-routed equity order appear to fill against
the Coinbase paper book.

medallion: execution
"""

from __future__ import annotations

import logging

from backend.services.execution.broker_base import (
    OrderRequest,
    OrderResult,
    PreviewResult,
)
from backend.services.execution.paper_executor import PaperExecutor
from backend.services.execution.risk_gate import _is_crypto_symbol

logger = logging.getLogger(__name__)


class CoinbasePaperExecutor(PaperExecutor):
    """Paper executor that only accepts crypto symbols.

    Delegates all fill simulation to :class:`PaperExecutor` (shared in-memory
    position book, instant market fills at MarketSnapshot price, limit/stop
    order support). The only behavioral difference is the symbol guard and
    the ``broker_name``/``raw.paper_mode`` tagging so orders are traceable
    back to this executor in the admin UI.
    """

    def __init__(self, starting_cash: float = 100_000.0):
        super().__init__(starting_cash=starting_cash)

    @property
    def broker_name(self) -> str:
        return "coinbase"

    def _reject_non_crypto(self, req: OrderRequest) -> OrderResult:
        logger.warning(
            "CoinbasePaperExecutor rejected non-crypto symbol: %s", req.symbol
        )
        return OrderResult(
            error=(
                f"Coinbase executor only accepts crypto symbols; "
                f"received {req.symbol!r}"
            ),
            raw={"paper_mode": True, "broker": "coinbase", "rejected": "non_crypto"},
        )

    async def preview_order(self, req: OrderRequest) -> PreviewResult:
        if not _is_crypto_symbol(req.symbol):
            return PreviewResult(
                error=(
                    f"Coinbase executor only accepts crypto symbols; "
                    f"received {req.symbol!r}"
                ),
                raw={"paper_mode": True, "broker": "coinbase"},
            )
        preview = await super().preview_order(req)
        preview.raw.update({"broker": "coinbase", "paper_mode": True})
        return preview

    async def place_order(self, req: OrderRequest) -> OrderResult:
        if not _is_crypto_symbol(req.symbol):
            return self._reject_non_crypto(req)
        result = await super().place_order(req)
        result.raw.update({"broker": "coinbase", "paper_mode": True})
        return result

    def is_paper_trading(self) -> bool:
        return True


__all__ = ["CoinbasePaperExecutor"]
