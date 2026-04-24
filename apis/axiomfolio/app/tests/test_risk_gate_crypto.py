"""Tests for the RiskGate crypto branch.

Covers:

* ``_is_crypto_symbol`` recognizes bare tickers and pair notation.
* Crypto orders route through ``_check_crypto_sizing`` and enforce
  ``CRYPTO_MAX_POSITION_PCT`` as a hard cap.
* Equity orders still run through the existing stage/regime path and are
  **not** affected by the crypto branch.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.execution.broker_base import OrderRequest
from app.services.execution.risk_gate import (
    RiskGate,
    RiskViolation,
    _is_crypto_symbol,
)


class TestIsCryptoSymbol:
    """Symbol classification used by the risk-gate crypto branch."""

    @pytest.mark.parametrize(
        "sym",
        ["BTC", "ETH", "SOL", "DOGE", "LINK", "ADA", "eth", "btc"],
    )
    def test_bare_tickers_match(self, sym: str) -> None:
        assert _is_crypto_symbol(sym) is True

    @pytest.mark.parametrize(
        "sym",
        ["BTC-USD", "ETH-USDT", "SOL/USD", "ada-usd", "LINK-USDC"],
    )
    def test_pair_notation_matches(self, sym: str) -> None:
        assert _is_crypto_symbol(sym) is True

    @pytest.mark.parametrize(
        "sym",
        ["AAPL", "SPY", "MSFT", "QQQ", "", "   "],
    )
    def test_equities_and_empty_do_not_match(self, sym: str) -> None:
        assert _is_crypto_symbol(sym) is False

    def test_none_symbol_safe(self) -> None:
        assert _is_crypto_symbol(None) is False  # type: ignore[arg-type]

    def test_unknown_pair_does_not_match(self) -> None:
        """Pair notation with a non-crypto base should NOT match."""
        assert _is_crypto_symbol("AAPL-USD") is False
        assert _is_crypto_symbol("SPY/USD") is False


class TestCryptoSizing:
    """Crypto orders skip stage/regime sizing and enforce tighter pct cap."""

    def setup_method(self) -> None:
        self.gate = RiskGate()

    def _req(self, symbol: str, qty: float) -> OrderRequest:
        return OrderRequest.from_user_input(
            symbol=symbol, side="buy", order_type="market", quantity=qty
        )

    def test_crypto_within_cap_passes(self) -> None:
        """$2,000 on $100,000 equity = 2%, under the 5% crypto cap."""
        warnings = self.gate.check(
            self._req("BTC-USD", qty=0.05),
            price_estimate=40_000.0,
            portfolio_equity=100_000.0,
        )
        assert warnings == []

    def test_crypto_exceeds_cap_blocks(self) -> None:
        """$10,000 on $100,000 equity = 10%, over the 5% crypto cap."""
        with pytest.raises(RiskViolation, match="Crypto position"):
            self.gate.check(
                self._req("ETH", qty=5.0),
                price_estimate=2_000.0,
                portfolio_equity=100_000.0,
            )

    def test_crypto_skips_stage_regime_path(self) -> None:
        """Crypto must NOT enter ``_check_stage_regime_sizing`` even when db is provided."""
        db = MagicMock()
        with patch.object(RiskGate, "_check_stage_regime_sizing") as mock_stage:
            warnings = self.gate.check(
                self._req("SOL-USD", qty=10.0),
                price_estimate=100.0,
                db=db,
                portfolio_equity=100_000.0,
                risk_budget=1_000.0,
            )
            assert warnings == []
            mock_stage.assert_not_called()

    def test_crypto_respects_max_order_value(self) -> None:
        """The global $100k MAX_ORDER_VALUE still applies before the crypto branch."""
        with pytest.raises(RiskViolation, match="exceeds"):
            self.gate.check(
                self._req("BTC-USD", qty=10.0),
                price_estimate=50_000.0,  # $500k notional
                portfolio_equity=100_000_000.0,  # huge equity — cap would pass
            )

    def test_crypto_without_equity_context_allows(self) -> None:
        """Missing ``portfolio_equity`` falls back to MAX_ORDER_VALUE only."""
        warnings = self.gate.check(
            self._req("ETH-USD", qty=1.0),
            price_estimate=2_000.0,
            portfolio_equity=None,
        )
        assert warnings == []

    def test_equity_path_unchanged(self) -> None:
        """Equities still hit the 15% cap — crypto branch must not affect them."""
        with pytest.raises(RiskViolation, match="exceeds 15%"):
            self.gate.check(
                self._req("AAPL", qty=500),
                price_estimate=200.0,  # $100k notional on $500k equity = 20%
                portfolio_equity=500_000.0,
            )
