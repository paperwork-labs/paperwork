"""Circuit breaker simulation tests.

Verifies tier progression, kill switch, and daily reset behavior.
"""
import pytest
from datetime import datetime, timedelta, timezone

from app.services.risk.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)


class MockRedis:
    """In-memory Redis mock for testing."""
    
    def __init__(self):
        self._data = {}
    
    def get(self, key):
        val = self._data.get(key)
        return val.encode() if isinstance(val, str) else val
    
    def set(self, key, value):
        self._data[key] = str(value) if not isinstance(value, str) else value
    
    def delete(self, key):
        self._data.pop(key, None)
    
    def incr(self, key):
        val = int(self._data.get(key, 0) or 0)
        self._data[key] = str(val + 1)
        return val + 1
    
    def scan_iter(self, pattern):
        prefix = pattern.rstrip("*")
        return [k for k in self._data.keys() if k.startswith(prefix)]


@pytest.fixture
def mock_redis():
    return MockRedis()


@pytest.fixture
def circuit_breaker(mock_redis):
    config = CircuitBreakerConfig(
        tier1_loss_pct=2.0,
        tier2_loss_pct=3.0,
        tier3_loss_pct=5.0,
        max_orders_per_day=50,
        max_orders_per_symbol=5,
        consecutive_loss_limit=3,
    )
    cb = CircuitBreaker(config=config, redis_client=mock_redis)
    cb.set_starting_equity(100_000)  # $100k starting equity
    return cb


class TestTierProgression:
    """Test circuit breaker tier progression based on losses."""
    
    def test_tier0_normal_operation(self, circuit_breaker):
        """No losses = tier 0, full trading allowed."""
        allowed, reason, tier = circuit_breaker.can_trade()
        
        assert allowed is True
        assert tier == 0
        assert "OK" in reason
    
    def test_tier1_warning_at_2_percent(self, circuit_breaker):
        """2% loss triggers tier 1 warning."""
        # Simulate $2000 loss on $100k = 2%
        circuit_breaker.record_fill("AAPL", -2000, is_exit=True)
        
        allowed, reason, tier = circuit_breaker.can_trade()
        
        assert allowed is True  # Still allowed but with warning
        assert tier == 1
        assert "WARNING" in reason
        assert "2.0%" in reason
        
        # Size multiplier should be 50%
        assert circuit_breaker.get_size_multiplier() == 0.5
    
    def test_tier2_entries_blocked_at_3_percent(self, circuit_breaker):
        """3% loss triggers tier 2 - entries blocked."""
        # Simulate $3000 loss = 3%
        circuit_breaker.record_fill("AAPL", -3000, is_exit=True)
        
        # New entries blocked
        allowed, reason, tier = circuit_breaker.can_trade(is_exit=False)
        assert allowed is False
        assert tier == 2
        assert "ENTRIES BLOCKED" in reason
        
        # Exits still allowed
        allowed, reason, tier = circuit_breaker.can_trade(is_exit=True)
        assert allowed is True
        assert tier == 2
        assert "EXITS ONLY" in reason
    
    def test_tier3_full_halt_at_5_percent(self, circuit_breaker):
        """5% loss triggers tier 3 - full halt."""
        # Simulate $5000 loss = 5%
        circuit_breaker.record_fill("AAPL", -5000, is_exit=True)
        
        # All trading blocked
        allowed, reason, tier = circuit_breaker.can_trade(is_exit=False)
        assert allowed is False
        assert tier == 3
        assert "HALT" in reason
        
        # Even exits blocked at tier 3
        allowed, reason, tier = circuit_breaker.can_trade(is_exit=True)
        assert allowed is False
        assert tier == 3
    
    def test_progressive_loss_accumulation(self, circuit_breaker):
        """Multiple losses accumulate to higher tiers."""
        # First loss: 1% - still tier 0
        circuit_breaker.record_fill("AAPL", -1000, is_exit=True)
        _, _, tier = circuit_breaker.can_trade()
        assert tier == 0
        
        # Second loss: now at 2% total - tier 1
        circuit_breaker.record_fill("MSFT", -1000, is_exit=True)
        _, _, tier = circuit_breaker.can_trade()
        assert tier == 1
        
        # Third loss: now at 3.5% - tier 2
        circuit_breaker.record_fill("GOOGL", -1500, is_exit=True)
        _, _, tier = circuit_breaker.can_trade()
        assert tier == 2
        
        # Fourth loss: now at 6% - tier 3
        circuit_breaker.record_fill("AMZN", -2500, is_exit=True)
        _, _, tier = circuit_breaker.can_trade()
        assert tier == 3


class TestKillSwitch:
    """Test kill switch behavior."""
    
    def test_kill_switch_blocks_all_trading(self, circuit_breaker):
        """Kill switch blocks all trading regardless of P&L."""
        circuit_breaker.trigger_kill_switch("Emergency stop", user="admin")
        
        allowed, reason, tier = circuit_breaker.can_trade()
        
        assert allowed is False
        assert tier == 3
        assert "KILL SWITCH" in reason
        assert "Emergency stop" in reason
    
    def test_kill_switch_reset(self, circuit_breaker):
        """Kill switch can be reset to resume trading."""
        circuit_breaker.trigger_kill_switch("Test", user="test")
        
        # Verify blocked
        allowed, _, _ = circuit_breaker.can_trade()
        assert allowed is False
        
        # Reset
        was_active = circuit_breaker.reset_kill_switch(user="admin")
        assert was_active is True
        
        # Trading should resume
        allowed, _, tier = circuit_breaker.can_trade()
        assert allowed is True
        assert tier == 0
    
    def test_kill_switch_status_in_get_status(self, circuit_breaker):
        """Status API reflects kill switch state."""
        status = circuit_breaker.get_status()
        assert status["kill_switch_active"] is False
        
        circuit_breaker.trigger_kill_switch("Testing", user="admin")
        
        status = circuit_breaker.get_status()
        assert status["kill_switch_active"] is True


class TestConsecutiveLosses:
    """Test consecutive loss limiting."""
    
    def test_consecutive_losses_trigger_tier2(self, circuit_breaker):
        """3 consecutive losses blocks new entries."""
        # Three losing trades in a row
        for i in range(3):
            circuit_breaker.record_fill(f"SYM{i}", -100, is_exit=True)
        
        # New entries blocked
        allowed, reason, tier = circuit_breaker.can_trade(is_exit=False)
        assert allowed is False
        assert tier == 2
        assert "consecutive losses" in reason
    
    def test_winning_trade_resets_consecutive(self, circuit_breaker):
        """A winning trade resets consecutive loss counter."""
        # Two losses
        circuit_breaker.record_fill("AAPL", -100, is_exit=True)
        circuit_breaker.record_fill("MSFT", -100, is_exit=True)
        
        # One win resets counter
        circuit_breaker.record_fill("GOOGL", 200, is_exit=True)
        
        # Two more losses - should still be at tier 0 (only 2 consecutive)
        circuit_breaker.record_fill("AMZN", -100, is_exit=True)
        circuit_breaker.record_fill("META", -100, is_exit=True)
        
        allowed, _, tier = circuit_breaker.can_trade()
        assert allowed is True
        assert tier < 2  # Not blocked by consecutive losses


class TestOrderLimits:
    """Test order rate limiting."""
    
    def test_max_orders_per_day(self, circuit_breaker):
        """Daily order limit blocks new orders."""
        # Fill 50 orders (the limit)
        for i in range(50):
            circuit_breaker.record_fill(f"SYM{i % 10}", 0, is_exit=False)
        
        # 51st order blocked
        allowed, reason, tier = circuit_breaker.can_trade()
        assert allowed is False
        assert "MAX ORDERS" in reason
        assert "50" in reason
    
    def test_max_orders_per_symbol(self, circuit_breaker):
        """Per-symbol order limit."""
        # Fill 5 orders on same symbol
        for i in range(5):
            circuit_breaker.record_fill("AAPL", 0, is_exit=False)
        
        # 6th order on AAPL blocked
        allowed, reason = circuit_breaker.can_trade_symbol("AAPL")
        assert allowed is False
        assert "AAPL" in reason
        assert "5" in reason
        
        # Different symbol still OK
        allowed, _ = circuit_breaker.can_trade_symbol("MSFT")
        assert allowed is True


class TestDailyReset:
    """Test trading day reset behavior."""
    
    def test_daily_reset_clears_counters(self, circuit_breaker):
        """Manual reset clears all daily counters."""
        # Accumulate losses and orders
        circuit_breaker.record_fill("AAPL", -3000, is_exit=True)
        circuit_breaker.record_fill("MSFT", -1000, is_exit=True)
        
        _, _, tier = circuit_breaker.can_trade()
        assert tier > 0  # Should be tier 2 at 4% loss
        
        # Reset
        circuit_breaker.reset_daily_counters()
        
        # Back to tier 0
        _, _, tier = circuit_breaker.can_trade()
        assert tier == 0
    
    def test_status_reflects_current_state(self, circuit_breaker):
        """Status API returns accurate state."""
        circuit_breaker.record_fill("AAPL", -2500, is_exit=True)
        
        status = circuit_breaker.get_status()
        
        assert status["tier"] == 1  # 2.5% loss = tier 1
        assert status["daily_pnl"] == -2500
        assert 2.0 <= status["daily_pnl_pct"] <= 3.0
        assert status["order_count"] == 1
        assert status["kill_switch_active"] is False


class TestSizeMultiplier:
    """Test position size multiplier behavior."""
    
    def test_size_multiplier_tier0(self, circuit_breaker):
        """Tier 0 = full size (1.0x)."""
        assert circuit_breaker.get_size_multiplier() == 1.0
    
    def test_size_multiplier_tier1(self, circuit_breaker):
        """Tier 1 = half size (0.5x)."""
        circuit_breaker.record_fill("AAPL", -2000, is_exit=True)
        assert circuit_breaker.get_size_multiplier() == 0.5
    
    def test_size_multiplier_tier2(self, circuit_breaker):
        """Tier 2 = no new positions (0x)."""
        circuit_breaker.record_fill("AAPL", -3500, is_exit=True)
        assert circuit_breaker.get_size_multiplier() == 0.0
    
    def test_size_multiplier_tier3(self, circuit_breaker):
        """Tier 3 = no trading (0x)."""
        circuit_breaker.record_fill("AAPL", -5500, is_exit=True)
        assert circuit_breaker.get_size_multiplier() == 0.0


class TestTripRecording:
    """Test circuit breaker trip recording."""
    
    def test_trip_reason_recorded(self, circuit_breaker):
        """Trip reason is stored when breaker trips."""
        circuit_breaker.record_fill("AAPL", -5500, is_exit=True)
        circuit_breaker.can_trade()  # Trigger trip check
        
        status = circuit_breaker.get_status()
        
        assert "trip_reason" in status
        assert "tier3" in status["trip_reason"].lower() or "daily_loss" in status["trip_reason"].lower()
        assert status["trip_time"] != ""


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_positive_pnl_no_tier(self, circuit_breaker):
        """Positive P&L keeps tier at 0."""
        circuit_breaker.record_fill("AAPL", 5000, is_exit=True)
        
        _, _, tier = circuit_breaker.can_trade()
        assert tier == 0
    
    def test_exactly_at_threshold(self, circuit_breaker):
        """Exactly at threshold triggers that tier."""
        # Exactly 2% loss = tier 1
        circuit_breaker.record_fill("AAPL", -2000, is_exit=True)
        _, _, tier = circuit_breaker.can_trade()
        assert tier == 1
    
    def test_zero_starting_equity(self, circuit_breaker, mock_redis):
        """Handle zero starting equity gracefully."""
        circuit_breaker.set_starting_equity(0)
        circuit_breaker.record_fill("AAPL", -1000, is_exit=True)
        
        # Should not crash
        _, _, tier = circuit_breaker.can_trade()
        assert tier == 0  # Can't calculate percentage with 0 equity
    
    def test_non_exit_trades_dont_affect_consecutive(self, circuit_breaker):
        """Entry trades don't affect consecutive loss counter."""
        # These are entries, not exits
        for i in range(5):
            circuit_breaker.record_fill(f"SYM{i}", -100, is_exit=False)
        
        # No consecutive loss trigger
        allowed, _, tier = circuit_breaker.can_trade()
        assert tier == 0  # Only exits count for consecutive


class TestIntegrationScenario:
    """Full integration scenario test."""
    
    def test_realistic_trading_day(self, circuit_breaker):
        """Simulate a realistic bad trading day."""
        # Morning: A few small winners
        circuit_breaker.record_fill("AAPL", 200, is_exit=True)
        circuit_breaker.record_fill("MSFT", 150, is_exit=True)

        _, _, tier = circuit_breaker.can_trade()
        assert tier == 0, "Should be fine after wins"

        # Mid-day: First big loss - 1.5%
        circuit_breaker.record_fill("GOOGL", -1500, is_exit=True)
        _, _, tier = circuit_breaker.can_trade()
        assert tier == 0, "Still under 2%"

        # Afternoon: Second loss - now at 2% (net: 200+150-1500-850 = -2000)
        circuit_breaker.record_fill("AMZN", -850, is_exit=True)
        _, _, tier = circuit_breaker.can_trade()
        assert tier == 1, "Crossed 2% warning"

        # Try to enter new position - should get reduced size
        mult = circuit_breaker.get_size_multiplier()
        assert mult == 0.5, "Should be half size at tier 1"

        # Another loss pushes to 3% (net: -2000-1100 = -3100)
        circuit_breaker.record_fill("META", -1100, is_exit=True)
        allowed, _, tier = circuit_breaker.can_trade()
        assert tier == 2, "Crossed 3% - entries blocked"
        assert allowed is False

        # Exit still allowed
        allowed, _, _ = circuit_breaker.can_trade(is_exit=True)
        assert allowed is True

        # Massive loss triggers kill switch (net: -3100-2000 = -5100)
        circuit_breaker.record_fill("NVDA", -2000, is_exit=True)
        allowed, _, tier = circuit_breaker.can_trade()
        assert tier == 3, "Crossed 5% - full halt"
        assert allowed is False

        # Even exits blocked at tier 3
        allowed, _, _ = circuit_breaker.can_trade(is_exit=True)
        assert allowed is False

        # Next day - reset
        circuit_breaker.reset_daily_counters()
        allowed, _, tier = circuit_breaker.can_trade()
        assert tier == 0, "New day, fresh start"
        assert allowed is True
