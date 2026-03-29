"""
Pre-trade validation - all checks must pass before order reaches broker.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.order import Order
from backend.models.position import Position
from backend.models.market_data import MarketSnapshot
from backend.services.risk.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)


@dataclass
class ValidationCheck:
    """Result of a single validation check."""

    name: str
    passed: bool
    reason: Optional[str] = None


@dataclass
class ValidationResult:
    """Aggregate result of all pre-trade validations."""

    allowed: bool
    checks: List[ValidationCheck] = field(default_factory=list)
    size_multiplier: float = 1.0

    @property
    def reasons(self) -> List[str]:
        """Get list of failure reasons."""
        return [c.reason for c in self.checks if not c.passed and c.reason]

    @property
    def warnings(self) -> List[str]:
        """Get list of non-blocking warning messages."""
        return [c.reason for c in self.checks if c.passed and c.reason]

    @property
    def summary(self) -> str:
        """Get summary string of validation result."""
        if self.allowed:
            if self.warnings:
                return f"PASSED; {'; '.join(self.warnings)}"
            return "PASSED"
        return f"BLOCKED: {'; '.join(self.reasons)}"


class PreTradeValidator:
    """
    Validates orders BEFORE they reach the broker.
    All checks must pass.
    """

    # Use centralized settings with fallbacks
    MAX_POSITION_PCT = getattr(settings, "MAX_SINGLE_POSITION_PCT", 0.15)
    MAX_SECTOR_PCT = 0.25  # 25% max sector concentration
    PRICE_COLLAR_PCT = 0.05  # 5% from last price

    def __init__(self, db: Session, user_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id
        self._price_cache: dict[str, float] = {}
        self._sector_cache: dict[str, str] = {}

    def validate(
        self,
        order: Order,
        portfolio_equity: float,
        is_exit: bool = False,
    ) -> ValidationResult:
        """
        Run all pre-trade validations.

        Args:
            order: Order to validate
            portfolio_equity: Current portfolio equity
            is_exit: Whether this is an exit/close order

        Returns:
            ValidationResult with all check results
        """
        # Use order's user_id if not set on validator
        if self.user_id is None:
            self.user_id = order.user_id

        checks = [
            self._check_circuit_breaker(is_exit),
            self._check_position_limit(order, portfolio_equity),
            self._check_sector_concentration(order, portfolio_equity),
            self._check_price_collar(order),
            self._check_order_rate_limit(order),
        ]

        # Wash sale check only for sells
        if order.side.lower() == "sell":
            checks.append(self._check_wash_sale_risk(order))

        all_passed = all(c.passed for c in checks)
        size_mult = circuit_breaker.get_size_multiplier(is_exit=is_exit) if all_passed else 0.0

        result = ValidationResult(
            allowed=all_passed,
            checks=checks,
            size_multiplier=size_mult,
        )

        if not all_passed:
            logger.warning(
                "Order validation failed for %s %s %d: %s",
                order.side,
                order.symbol,
                order.quantity,
                result.reasons,
            )

        return result

    def _check_circuit_breaker(self, is_exit: bool) -> ValidationCheck:
        """Check if circuit breaker allows trading.
        
        Also syncs starting equity from AccountBalance if trading day reset.
        """
        # Sync starting equity if needed (lazy sync on first trade of day)
        self._ensure_starting_equity_synced()
        
        allowed, reason, tier = circuit_breaker.can_trade(is_exit=is_exit)
        return ValidationCheck(
            name="circuit_breaker",
            passed=allowed,
            reason=None if allowed else reason,
        )
    
    def _ensure_starting_equity_synced(self) -> None:
        """Sync starting equity to circuit breaker from latest AccountBalance.
        
        Uses Redis key scoped by user_id to track if already synced today.
        This ensures circuit breaker uses real portfolio value for daily loss % calculation.
        """
        if not self.user_id:
            return
        
        try:
            from backend.services.cache import redis_client
            from backend.models.account_balance import AccountBalance
            
            # Scope key by user to prevent cross-user blocking
            sync_key = f"circuit:equity_synced:{self.user_id}"
            if redis_client.exists(sync_key):
                return  # Already synced today for this user
            
            # Get total equity across user's accounts
            balance = (
                self.db.query(AccountBalance)
                .filter(AccountBalance.user_id == self.user_id)
                .order_by(AccountBalance.as_of_date.desc())
                .first()
            )
            if balance and balance.total_value:
                equity = float(balance.total_value)
                circuit_breaker.set_starting_equity(equity)
                # Set flag with TTL until next trading day reset (max 24h)
                redis_client.setex(sync_key, 86400, "1")
                logger.info(
                    "Circuit breaker starting equity synced: $%.2f (user %s)",
                    equity, self.user_id
                )
        except Exception as e:
            logger.warning("Failed to sync starting equity: %s", e)

    def _check_position_limit(
        self, order: Order, portfolio_equity: float
    ) -> ValidationCheck:
        """Check if order would exceed position size limit."""
        if portfolio_equity <= 0:
            return ValidationCheck(name="position_limit", passed=True)

        # Get current position value
        current_value = self._get_position_value(order.symbol)
        price = self._get_price(order.symbol)

        if price <= 0:
            return ValidationCheck(name="position_limit", passed=True)

        # Calculate new position value after order
        if order.side.lower() == "buy":
            new_value = current_value + (order.quantity * price)
        else:
            new_value = current_value - (order.quantity * price)

        position_pct = abs(new_value) / portfolio_equity

        if position_pct > self.MAX_POSITION_PCT:
            return ValidationCheck(
                name="position_limit",
                passed=False,
                reason=f"Position would be {position_pct:.1%} of portfolio (max {self.MAX_POSITION_PCT:.0%})",
            )
        return ValidationCheck(name="position_limit", passed=True)

    def _check_sector_concentration(
        self, order: Order, portfolio_equity: float
    ) -> ValidationCheck:
        """Check if order would exceed sector concentration limit."""
        if portfolio_equity <= 0 or order.side.lower() == "sell":
            return ValidationCheck(name="sector_concentration", passed=True)

        sector = self._get_sector(order.symbol)
        if not sector:
            return ValidationCheck(name="sector_concentration", passed=True)

        # Get current sector exposure
        sector_value = self._get_sector_exposure(sector)
        price = self._get_price(order.symbol)

        if price <= 0:
            return ValidationCheck(name="sector_concentration", passed=True)

        # Calculate new sector exposure
        order_value = order.quantity * price
        new_sector_value = sector_value + order_value
        sector_pct = new_sector_value / portfolio_equity

        if sector_pct > self.MAX_SECTOR_PCT:
            return ValidationCheck(
                name="sector_concentration",
                passed=False,
                reason=f"{sector} sector would be {sector_pct:.1%} of portfolio (max {self.MAX_SECTOR_PCT:.0%})",
            )
        return ValidationCheck(name="sector_concentration", passed=True)

    def _check_price_collar(self, order: Order) -> ValidationCheck:
        """Check if order price is within collar of last traded price."""
        if order.order_type.lower() == "market":
            return ValidationCheck(name="price_collar", passed=True)

        last_price = self._get_price(order.symbol)
        if last_price <= 0:
            return ValidationCheck(name="price_collar", passed=True)

        order_price = order.limit_price or order.stop_price
        if not order_price:
            return ValidationCheck(name="price_collar", passed=True)

        deviation = abs(order_price - last_price) / last_price

        if deviation > self.PRICE_COLLAR_PCT:
            return ValidationCheck(
                name="price_collar",
                passed=False,
                reason=f"Order price ${order_price:.2f} is {deviation:.1%} from last price ${last_price:.2f} (max {self.PRICE_COLLAR_PCT:.0%})",
            )
        return ValidationCheck(name="price_collar", passed=True)

    def _check_order_rate_limit(self, order: Order) -> ValidationCheck:
        """Check if order rate is within limits."""
        # Check symbol-specific rate limit via circuit breaker
        allowed, reason = circuit_breaker.can_trade_symbol(order.symbol)
        if not allowed:
            return ValidationCheck(
                name="order_rate_limit",
                passed=False,
                reason=reason,
            )

        # Could add additional rate limiting logic here
        return ValidationCheck(name="order_rate_limit", passed=True)

    def _check_wash_sale_risk(self, order: Order) -> ValidationCheck:
        """
        Check for potential wash sale risk on sells.

        A wash sale occurs if you sell at a loss and buy the same/substantially
        identical security within 30 days before or after.
        """
        # Check if there was a recent purchase of this symbol
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        recent_buys = (
            self.db.query(Order)
            .filter(
                Order.symbol == order.symbol,
                Order.side == "buy",
                Order.filled_at >= thirty_days_ago,
                Order.user_id == order.user_id,
            )
            .count()
        )

        if recent_buys > 0:
            return ValidationCheck(
                name="wash_sale_risk",
                passed=True,  # Allow but warn
                reason=f"WARNING: {recent_buys} recent buys of {order.symbol} - potential wash sale if sold at loss",
            )

        return ValidationCheck(name="wash_sale_risk", passed=True)

    def _get_position_value(self, symbol: str) -> float:
        """Get current position value for a symbol (scoped by user)."""
        query = self.db.query(Position).filter(
            Position.symbol == symbol,
            Position.quantity != 0,
        )
        if self.user_id:
            query = query.filter(Position.user_id == self.user_id)
        
        position = query.first()

        if position and position.market_value:
            return float(position.market_value)
        return 0.0

    def _get_price(self, symbol: str) -> float:
        """Get last price for a symbol from MarketSnapshot."""
        if symbol in self._price_cache:
            return self._price_cache[symbol]

        snapshot = (
            self.db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == symbol,
                MarketSnapshot.analysis_type == "technical_snapshot",
            )
            .order_by(MarketSnapshot.analysis_timestamp.desc())
            .first()
        )

        if snapshot and snapshot.current_price:
            price = float(snapshot.current_price)
            self._price_cache[symbol] = price
            return price

        return 0.0

    def _get_sector(self, symbol: str) -> Optional[str]:
        """Get sector for a symbol."""
        if symbol in self._sector_cache:
            return self._sector_cache[symbol]

        snapshot = (
            self.db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol)
            .first()
        )

        if snapshot and snapshot.sector:
            self._sector_cache[symbol] = snapshot.sector
            return snapshot.sector

        return None

    def _get_sector_exposure(self, sector: str) -> float:
        """Get total exposure to a sector (scoped by user)."""
        query = self.db.query(Position).filter(Position.quantity != 0)
        if self.user_id:
            query = query.filter(Position.user_id == self.user_id)
        
        positions = query.all()

        total = 0.0
        for pos in positions:
            pos_sector = self._get_sector(pos.symbol)
            if pos_sector == sector and pos.market_value:
                total += float(pos.market_value)

        return total
