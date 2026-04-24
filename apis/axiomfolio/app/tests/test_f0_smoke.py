"""Trading-parity foundation smoke tests.

Verifies the foundational trading-parity wiring is in place:

* ``BrokerType`` enum exposes the new brokers.
* The default ``BrokerRouter`` registers ``ibkr``, ``paper``, and ``coinbase``.
* ``CoinbasePaperExecutor`` rejects non-crypto symbols at the edge.
* ``CoinbasePaperExecutor`` accepts recognized crypto symbols and tags
  the result as ``paper_mode=True``.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.models.order import BrokerType
from app.services.execution.broker_base import OrderRequest
from app.services.execution.broker_router import create_default_router
from app.services.execution.coinbase_paper_executor import (
    CoinbasePaperExecutor,
)


class TestBrokerTypeEnum:
    """BrokerType enum must expose the live-broker identifiers."""

    @pytest.mark.parametrize(
        "name, value",
        [
            ("IBKR", "ibkr"),
            ("TASTYTRADE", "tastytrade"),
            ("SCHWAB", "schwab"),
            ("ETRADE", "etrade"),
            ("TRADIER", "tradier"),
            ("TRADIER_SANDBOX", "tradier_sandbox"),
            ("COINBASE", "coinbase"),
        ],
    )
    def test_enum_member(self, name: str, value: str) -> None:
        assert BrokerType[name].value == value


class TestDefaultRouter:
    """``create_default_router`` wires up the paper crypto executor for F0."""

    def test_registers_ibkr_paper_coinbase(self) -> None:
        router = create_default_router()
        available = set(router.available_brokers)
        assert {"ibkr", "paper", "coinbase"} <= available

    def test_coinbase_resolves_to_paper_executor(self) -> None:
        router = create_default_router()
        executor = router.get("coinbase")
        assert isinstance(executor, CoinbasePaperExecutor)
        assert executor.is_paper_trading() is True
        assert executor.broker_name == "coinbase"


class TestCoinbasePaperExecutorSymbolGuard:
    """Defense-in-depth: reject non-crypto at the Coinbase edge."""

    def setup_method(self) -> None:
        self.executor = CoinbasePaperExecutor(starting_cash=100_000.0)

    @pytest.mark.asyncio
    async def test_rejects_equity_place_order(self) -> None:
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=10
        )
        result = await self.executor.place_order(req)
        assert result.error is not None
        assert "crypto" in result.error.lower()
        assert result.raw.get("broker") == "coinbase"
        assert result.raw.get("paper_mode") is True

    @pytest.mark.asyncio
    async def test_rejects_equity_preview(self) -> None:
        req = OrderRequest.from_user_input(
            symbol="SPY", side="buy", order_type="market", quantity=1
        )
        preview = await self.executor.preview_order(req)
        assert preview.error is not None
        assert "crypto" in preview.error.lower()

    @pytest.mark.asyncio
    async def test_accepts_crypto_and_tags_paper_mode(self) -> None:
        """Crypto orders should flow through the paper fill path with broker/paper tags."""
        req = OrderRequest.from_user_input(
            symbol="BTC-USD", side="buy", order_type="market", quantity=0.1
        )

        # Stub the MarketSnapshot price lookup used by PaperExecutor._get_current_price.
        with patch.object(
            CoinbasePaperExecutor, "_get_current_price", return_value=Decimal("40000")
        ):
            result = await self.executor.place_order(req)

        assert result.error is None, result.error
        assert result.status == "filled"
        assert result.raw.get("broker") == "coinbase"
        assert result.raw.get("paper_mode") is True
