"""Pre-trade risk gate — validates orders before they reach any broker.

Includes Stage Analysis spec position sizing (ATR-based with Regime Multiplier x Stage Cap).
See Stage_Analysis.docx Section 9.

DANGER ZONE: This file affects capital protection. See .cursor/rules/protected-regions.mdc
Related docs: docs/TRADING_PRINCIPLES.md, Stage_Analysis.docx Section 9
Related rules: portfolio-manager.mdc, risk-manager.mdc
IRON LAW: Single execution path - OrderManager → RiskGate → BrokerRouter. Never bypass.

medallion: execution
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.broker_account import BrokerAccount
from app.models.market_data import MarketSnapshot
from app.services.execution.broker_base import OrderRequest
from app.services.gold.position_sizing import (
    DEFAULT_STOP_MULTIPLIER,
    compute_position_size,
)
from app.services.gold.strategy.account_strategy import get_strategy_profile

logger = logging.getLogger(__name__)

MAX_ORDER_VALUE = 100_000
MAX_SINGLE_POSITION_PCT = app_settings.MAX_SINGLE_POSITION_PCT

# Crypto recognition for the risk-gate branch.
# Weinstein Stage Analysis does not apply to crypto (no fundamentals,
# 24/7 markets, no earnings/sector context), so crypto orders skip the
# stage/regime sizing path and instead enforce a tighter
# CRYPTO_MAX_POSITION_PCT cap. This list is intentionally conservative —
# crypto assets not recognized here fall through to the equity path and
# are blocked by missing MarketSnapshot/stage data, which is the safer
# failure mode.
CRYPTO_SYMBOLS_CORE = frozenset({
    "BTC", "ETH", "ADA", "SOL", "MATIC", "DOGE", "LTC", "XRP", "DOT", "AVAX",
    "LINK", "UNI", "ATOM", "BCH",
})


def _is_crypto_symbol(symbol: str) -> bool:
    """Return True if ``symbol`` should route through the crypto risk branch.

    Recognizes:
      * Bare crypto tickers in ``CRYPTO_SYMBOLS_CORE`` (e.g. ``"BTC"``)
      * Coinbase-style pair notation with USD/USDT quote (``"BTC-USD"``,
        ``"ETH-USDT"``, ``"SOL/USD"``) where the base is in the core set.

    Intentionally conservative: unknown aliases fall through to the equity
    path, which fails closed for lack of MarketSnapshot data.
    """
    s = (symbol or "").upper().strip()
    if not s:
        return False
    if s in CRYPTO_SYMBOLS_CORE:
        return True
    for sep in ("-", "/"):
        if sep in s:
            base, _, quote = s.partition(sep)
            if quote in ("USD", "USDT", "USDC") and base in CRYPTO_SYMBOLS_CORE:
                return True
    return False


class RiskViolation(Exception):
    """Hard block: order cannot proceed."""


class RiskGate:
    """Stateless pre-trade risk checker.

    Raises RiskViolation for hard blocks.
    Returns a list of soft warnings for advisory concerns.
    """

    def __init__(
        self,
        max_order_value: float = MAX_ORDER_VALUE,
        max_position_pct: float = MAX_SINGLE_POSITION_PCT,
    ):
        self.max_order_value = max_order_value
        self.max_position_pct = max_position_pct

    def check(
        self,
        req: OrderRequest,
        price_estimate: float,
        db: Optional[Session] = None,
        portfolio_equity: Optional[float] = None,
        risk_budget: Optional[float] = None,
    ) -> List[str]:
        """Run all risk checks. Raises on hard block, returns soft warnings."""
        warnings: List[str] = []
        est_value = req.quantity * price_estimate

        if est_value > self.max_order_value:
            raise RiskViolation(
                f"Order value ${est_value:,.0f} exceeds "
                f"${self.max_order_value:,.0f} maximum"
            )

        # Crypto orders use a tighter, Weinstein-agnostic path. Rationale:
        # Stage Analysis relies on SMA150 / sector / regime context that does
        # not apply to 24/7 crypto markets. Enforce CRYPTO_MAX_POSITION_PCT
        # (default 5%) in lieu of the 15% equity cap and skip the
        # stage/regime sizing path entirely.
        if _is_crypto_symbol(req.symbol):
            self._check_crypto_sizing(req, price_estimate, portfolio_equity)
            return warnings

        if portfolio_equity and portfolio_equity > 0:
            pct = est_value / portfolio_equity
            if pct > self.max_position_pct:
                raise RiskViolation(
                    f"Position would be {pct:.1%} of equity, "
                    f"exceeds {self.max_position_pct:.0%} maximum"
                )

        if db and price_estimate > 0 and risk_budget and risk_budget > 0:
            if app_settings.ENABLE_ACCOUNT_AWARE_RISK:
                self._load_account_strategy_profile(db, req)
            sizing_warning = self._check_stage_regime_sizing(
                db, req, price_estimate, risk_budget
            )
            if sizing_warning:
                warnings.append(sizing_warning)

        return warnings

    def _check_crypto_sizing(
        self,
        req: OrderRequest,
        price_estimate: float,
        portfolio_equity: Optional[float],
    ) -> None:
        """Crypto-specific sizing: enforce CRYPTO_MAX_POSITION_PCT as a hard cap.

        Skips Weinstein stage / Market Regime gating (those are equity concepts).
        Still applies the global ``max_order_value`` check — that is handled
        upstream in :meth:`check` before this method is called.

        Raises :class:`RiskViolation` if the order exceeds the crypto cap.
        Returns ``None`` silently when no equity context is available — the
        upstream ``max_order_value`` check remains the fail-safe in that case,
        matching how the equity path treats missing ``portfolio_equity``.
        """
        if portfolio_equity is None or portfolio_equity <= 0:
            return

        est_value = req.quantity * price_estimate
        cap_pct = float(
            getattr(app_settings, "CRYPTO_MAX_POSITION_PCT", 0.05) or 0.05
        )
        cap_value = portfolio_equity * cap_pct
        if est_value > cap_value:
            logger.warning(
                "Crypto sizing cap BLOCKED: %s est_value=$%.0f cap=$%.0f (%.1f%%)",
                req.symbol, est_value, cap_value, cap_pct * 100,
            )
            raise RiskViolation(
                f"Crypto position ${est_value:,.0f} exceeds "
                f"{cap_pct:.0%} of equity cap (${cap_value:,.0f}) for {req.symbol}"
            )

    def _check_stage_regime_sizing(
        self,
        db: Session,
        req: OrderRequest,
        price_estimate: float,
        risk_budget: float,
    ) -> Optional[str]:
        """Enforce Stage Analysis spec position sizing as a hard cap.

        Raises RiskViolation if requested quantity exceeds stage cap.
        Returns None if sizing is within limits.
        """
        from app.services.silver.regime.regime_engine import get_current_regime

        snap = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == req.symbol.upper(),
                MarketSnapshot.analysis_type == "technical_snapshot",
            )
            .order_by(MarketSnapshot.analysis_timestamp.desc())
            .first()
        )
        if not snap or not snap.stage_label or not snap.atrp_14:
            return None

        regime = get_current_regime(db)
        regime_state = regime.regime_state if regime else "R3"

        result = compute_position_size(
            risk_budget=risk_budget,
            atrp_14=float(snap.atrp_14),
            stop_multiplier=DEFAULT_STOP_MULTIPLIER,
            regime_state=regime_state,
            stage_label=snap.stage_label,
            current_price=price_estimate,
        )

        if result.shares <= 0:
            raise RiskViolation(
                f"Position sizing: {snap.stage_label} in {regime_state} has 0% stage cap "
                f"— no new longs allowed"
            )

        if req.quantity > result.shares:
            logger.warning(
                "Position sizing cap BLOCKED: %s requested %d shares, max is %d "
                "(stage=%s, regime=%s, cap=%.0f%%)",
                req.symbol, req.quantity, result.shares,
                snap.stage_label, regime_state, result.stage_cap * 100,
            )
            raise RiskViolation(
                f"Position sizing: requested {req.quantity} shares exceeds "
                f"max of {result.shares} "
                f"(stage {snap.stage_label}, regime {regime_state}, "
                f"cap {result.stage_cap:.0%})"
            )

        return None

    @staticmethod
    def _load_account_strategy_profile(db: Session, req: OrderRequest) -> None:
        """Read-only hook for G24 feature-flag rollout (no behavior changes yet)."""
        account_id = getattr(req, "account_id", None)
        if account_id is None:
            return
        if not isinstance(account_id, str) or not account_id.isdigit():
            return
        account = db.query(BrokerAccount).filter(BrokerAccount.id == int(account_id)).first()
        if account is None:
            return
        get_strategy_profile(account)

    def estimate_price(
        self,
        db: Session,
        symbol: str,
        limit_price: Optional[float],
        stop_price: Optional[float],
    ) -> float:
        """Estimate order price for risk checks.

        Raises RiskViolation if no valid price can be determined — conservative
        fail-safe to prevent understated risk checks when price is unknown.
        """
        price = limit_price or stop_price or 0.0
        if not price:
            snap = (
                db.query(MarketSnapshot.current_price)
                .filter(MarketSnapshot.symbol == symbol.upper())
                .order_by(MarketSnapshot.analysis_timestamp.desc())
                .first()
            )
            if snap and snap[0] is not None:
                try:
                    price = float(snap[0])
                except (TypeError, ValueError):
                    raise RiskViolation(
                        f"Cannot parse price for {symbol} from snapshot — "
                        f"order rejected (conservative fail-safe)"
                    )
            else:
                raise RiskViolation(
                    f"No price available for {symbol} — "
                    f"order rejected (conservative fail-safe)"
                )
        return price
