"""
Tiered circuit breaker with Redis-backed state.
Based on MiFID II / FIA best practices.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, time
from typing import Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python < 3.9

from redis import Redis

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerConfig:
    """Configuration for tiered circuit breaker."""

    # Tiered loss triggers
    tier1_loss_pct: float = 2.0  # Warning + 50% position sizes
    tier2_loss_pct: float = 3.0  # Block new entries, exits only
    tier3_loss_pct: float = 5.0  # Full halt + cancel all open

    # Additional limits
    max_orders_per_day: int = 50
    max_orders_per_symbol: int = 5
    consecutive_loss_limit: int = 3

    # Recovery
    cooldown_hours: int = 24

    # Pre-trade controls
    price_collar_pct: float = 5.0  # Reject orders >5% from last price
    cancel_on_disconnect: bool = True

    # Trading day reset configuration
    # Trading day resets at this hour in the configured timezone
    # Default: 4:00 AM Eastern (after overnight session ends, new trading day)
    trading_day_timezone: str = "US/Eastern"
    trading_day_reset_hour: int = 4  # 4 AM in trading_day_timezone


class CircuitBreaker:
    """
    Redis-backed circuit breaker with tiered response.

    Tiers:
        0: Normal operation
        1: Warning - reduce position sizes 50%
        2: Entries blocked - exits only allowed
        3: Full halt - cancel all open orders

    State keys in Redis:
        circuit:daily_pnl - float, resets at trading_day_reset_hour in trading_day_timezone
        circuit:trading_day - Trading day identifier (YYYY-MM-DD based on trading timezone)
        circuit:consecutive_losses - int
        circuit:order_count - int
        circuit:order_count:{symbol} - int
        circuit:trip_reason - str (if tripped)
        circuit:trip_time - ISO timestamp
        circuit:kill_switch - str (admin override)
    
    Trading Day:
        Default resets at 4:00 AM Eastern (after overnight session ends).
        This aligns with US equity market conventions where the trading day
        spans from ~4AM-8PM ET. Configure via CircuitBreakerConfig.
    """

    REDIS_PREFIX = "circuit:"

    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
        redis_client: Optional[Redis] = None,
    ):
        self.config = config or CircuitBreakerConfig()
        self._redis = redis_client

    @property
    def redis(self) -> Redis:
        """Lazy Redis connection."""
        if self._redis is None:
            self._redis = Redis.from_url(settings.REDIS_URL)
        return self._redis

    def can_trade(self, is_exit: bool = False) -> Tuple[bool, str, int]:
        """
        Check if trading is allowed.

        Args:
            is_exit: True if this is an exit/close order

        Returns:
            (allowed, reason, tier)
        """
        # Check kill switch first
        kill_reason = self.redis.get(f"{self.REDIS_PREFIX}kill_switch")
        if kill_reason:
            return False, f"KILL SWITCH: {kill_reason.decode()}", 3

        # Reset daily counters if needed
        self._maybe_reset_daily_counters()

        # Check daily loss tiers
        daily_loss = self._get_daily_loss_pct()

        if daily_loss >= self.config.tier3_loss_pct:
            self._trip("tier3_daily_loss", f"{daily_loss:.1f}% daily loss")
            return (
                False,
                f"HALT: {daily_loss:.1f}% daily loss exceeds {self.config.tier3_loss_pct}%",
                3,
            )

        if daily_loss >= self.config.tier2_loss_pct:
            if is_exit:
                return True, f"EXITS ONLY: {daily_loss:.1f}% daily loss", 2
            return False, f"ENTRIES BLOCKED: {daily_loss:.1f}% daily loss", 2

        if daily_loss >= self.config.tier1_loss_pct:
            return (
                True,
                f"WARNING: {daily_loss:.1f}% daily loss - sizes reduced 50%",
                1,
            )

        # Check consecutive losses
        consec = int(self.redis.get(f"{self.REDIS_PREFIX}consecutive_losses") or 0)
        if consec >= self.config.consecutive_loss_limit:
            if is_exit:
                return True, f"EXITS ONLY: {consec} consecutive losses", 2
            return False, f"ENTRIES BLOCKED: {consec} consecutive losses", 2

        # Check order rate limits
        order_count = int(self.redis.get(f"{self.REDIS_PREFIX}order_count") or 0)
        if order_count >= self.config.max_orders_per_day:
            return (
                False,
                f"MAX ORDERS: {order_count} orders today (limit {self.config.max_orders_per_day})",
                2,
            )

        return True, "OK", 0

    def can_trade_symbol(self, symbol: str) -> Tuple[bool, str]:
        """Check if trading a specific symbol is allowed."""
        key = f"{self.REDIS_PREFIX}order_count:{symbol}"
        count = int(self.redis.get(key) or 0)

        if count >= self.config.max_orders_per_symbol:
            return (
                False,
                f"Symbol {symbol}: {count} orders today (limit {self.config.max_orders_per_symbol})",
            )
        return True, "OK"

    def get_size_multiplier(self, is_exit: bool = False) -> float:
        """
        Get position size multiplier based on current tier.

        Args:
            is_exit: True if this is an exit/close order. At Tier 2 (entries blocked),
                     exits are still allowed so multiplier should be 1.0 for exits.

        Returns:
            1.0 for normal (or exits at tier 2), 0.5 for tier 1, 0.0 for tier 2+ entries
        """
        allowed, _, tier = self.can_trade(is_exit=is_exit)

        if tier >= 3:
            return 0.0  # Full halt - no trades at all
        if tier == 2:
            # Tier 2: entries blocked, exits allowed
            return 1.0 if is_exit else 0.0
        if tier == 1:
            return 0.5
        return 1.0

    def record_fill(
        self,
        symbol: str,
        pnl: float,
        is_exit: bool = False,
    ) -> None:
        """
        Record a fill and update circuit breaker state.

        Args:
            symbol: Ticker symbol
            pnl: P&L from this fill (negative = loss)
            is_exit: Whether this was closing a position
        """
        self._maybe_reset_daily_counters()

        # Update daily P&L
        current_pnl = float(self.redis.get(f"{self.REDIS_PREFIX}daily_pnl") or 0)
        new_pnl = current_pnl + pnl
        self.redis.set(f"{self.REDIS_PREFIX}daily_pnl", str(new_pnl))

        # Update order counts
        self.redis.incr(f"{self.REDIS_PREFIX}order_count")
        self.redis.incr(f"{self.REDIS_PREFIX}order_count:{symbol}")

        # Update consecutive losses
        if is_exit and pnl < 0:
            self.redis.incr(f"{self.REDIS_PREFIX}consecutive_losses")
        elif is_exit and pnl >= 0:
            self.redis.set(f"{self.REDIS_PREFIX}consecutive_losses", "0")

        logger.info(
            "CircuitBreaker recorded fill: %s pnl=%.2f daily=%.2f",
            symbol,
            pnl,
            new_pnl,
        )

    def trigger_kill_switch(self, reason: str, user: str = "system") -> None:
        """
        Activate kill switch - blocks all trading until manually reset.

        Args:
            reason: Why the kill switch was triggered
            user: Who triggered it
        """
        self.redis.set(f"{self.REDIS_PREFIX}kill_switch", reason)
        self.redis.set(
            f"{self.REDIS_PREFIX}kill_switch_time",
            datetime.now(timezone.utc).isoformat(),
        )
        self.redis.set(f"{self.REDIS_PREFIX}kill_switch_user", user)

        logger.critical(
            "KILL SWITCH ACTIVATED by %s: %s",
            user,
            reason,
        )

    def reset_kill_switch(self, user: str = "admin") -> bool:
        """
        Reset the kill switch to allow trading.

        Args:
            user: Who is resetting

        Returns:
            True if kill switch was active and reset
        """
        was_active = self.redis.get(f"{self.REDIS_PREFIX}kill_switch") is not None

        self.redis.delete(f"{self.REDIS_PREFIX}kill_switch")
        self.redis.delete(f"{self.REDIS_PREFIX}kill_switch_time")
        self.redis.delete(f"{self.REDIS_PREFIX}kill_switch_user")

        if was_active:
            logger.warning("Kill switch reset by %s", user)

        return was_active

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        self._maybe_reset_daily_counters()

        allowed, reason, tier = self.can_trade(is_exit=False)

        return {
            "tier": tier,
            "allowed": allowed,
            "reason": reason,
            "daily_pnl": float(self.redis.get(f"{self.REDIS_PREFIX}daily_pnl") or 0),
            "daily_pnl_pct": self._get_daily_loss_pct(),
            "order_count": int(self.redis.get(f"{self.REDIS_PREFIX}order_count") or 0),
            "consecutive_losses": int(
                self.redis.get(f"{self.REDIS_PREFIX}consecutive_losses") or 0
            ),
            "kill_switch_active": self.redis.get(f"{self.REDIS_PREFIX}kill_switch")
            is not None,
            "trip_reason": (
                self.redis.get(f"{self.REDIS_PREFIX}trip_reason") or b""
            ).decode(),
            "trip_time": (
                self.redis.get(f"{self.REDIS_PREFIX}trip_time") or b""
            ).decode(),
        }

    def reset_daily_counters(self) -> None:
        """Manually reset daily counters (for testing or scheduled reset)."""
        keys_to_delete = [
            f"{self.REDIS_PREFIX}daily_pnl",
            f"{self.REDIS_PREFIX}daily_pnl_date",
            f"{self.REDIS_PREFIX}order_count",
            f"{self.REDIS_PREFIX}consecutive_losses",
            f"{self.REDIS_PREFIX}trip_reason",
            f"{self.REDIS_PREFIX}trip_time",
        ]

        # Also delete symbol-specific order counts
        for key in self.redis.scan_iter(f"{self.REDIS_PREFIX}order_count:*"):
            keys_to_delete.append(key)

        for key in keys_to_delete:
            self.redis.delete(key)

        logger.info("CircuitBreaker daily counters reset")

    def _get_daily_loss_pct(self) -> float:
        """Get daily loss as percentage of starting equity."""
        daily_pnl = float(self.redis.get(f"{self.REDIS_PREFIX}daily_pnl") or 0)
        if daily_pnl >= 0:
            return 0.0

        starting_equity = float(
            self.redis.get(f"{self.REDIS_PREFIX}starting_equity") or 100_000
        )
        if starting_equity <= 0:
            return 0.0

        return abs(daily_pnl) / starting_equity * 100

    def set_starting_equity(self, equity: float) -> None:
        """Set starting equity for percentage calculations."""
        self.redis.set(f"{self.REDIS_PREFIX}starting_equity", str(equity))

    def _maybe_reset_daily_counters(self) -> None:
        """
        Reset counters when trading day changes.
        
        Trading day is determined by the configured timezone and reset hour.
        Default: 4:00 AM Eastern - a new trading day starts at this time.
        
        Example: At 3:59 AM ET, we're still in "yesterday's" trading day.
                 At 4:00 AM ET, a new trading day begins.
        """
        try:
            tz = ZoneInfo(self.config.trading_day_timezone)
        except Exception:
            logger.warning(
                "Invalid timezone '%s', falling back to US/Eastern",
                self.config.trading_day_timezone,
            )
            tz = ZoneInfo("US/Eastern")
        
        now_local = datetime.now(tz)
        reset_time = time(hour=self.config.trading_day_reset_hour)
        
        # Determine current trading day
        # If before reset hour, we're still in previous day's trading session
        if now_local.time() < reset_time:
            trading_day = (now_local - timedelta(days=1)).date()
        else:
            trading_day = now_local.date()
        
        trading_day_str = trading_day.isoformat()
        stored_day = self.redis.get(f"{self.REDIS_PREFIX}trading_day")

        if stored_day is None or stored_day.decode() != trading_day_str:
            self.reset_daily_counters()
            self.redis.set(f"{self.REDIS_PREFIX}trading_day", trading_day_str)
            logger.info(
                "Trading day reset: %s (tz=%s, reset_hour=%d)",
                trading_day_str,
                self.config.trading_day_timezone,
                self.config.trading_day_reset_hour,
            )

    def _trip(self, reason_code: str, message: str) -> None:
        """Record a circuit breaker trip."""
        self.redis.set(f"{self.REDIS_PREFIX}trip_reason", f"{reason_code}: {message}")
        self.redis.set(
            f"{self.REDIS_PREFIX}trip_time",
            datetime.now(timezone.utc).isoformat(),
        )
        logger.warning("CircuitBreaker tripped: %s - %s", reason_code, message)


# Module-level singleton
circuit_breaker = CircuitBreaker()
