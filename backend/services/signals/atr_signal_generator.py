#!/usr/bin/env python3
"""
AxiomFolio V1 - SINGLE ATR Signal Generator
===========================================

CONSOLIDATES ALL ATR logic into ONE service:
- Uses the sophisticated atr_calculator.py engine
- Adds signal generation logic from atr_matrix.py  
- Saves signals to database (signals.py model)
- Sends Discord alerts
- Runs on cron schedule

REPLACES:
❌ backend/core/strategies/atr_matrix.py (17KB)
❌ backend/services/strategies/atr_options_service.py (31KB)  
❌ Multiple scattered ATR calculations

NOW: ONE place for ALL ATR signals with database persistence!
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

# Import the SINGLE ATR calculator
from backend.services.analysis.atr_calculator import (
    atr_calculator,
    ATRResult,
    ATRMatrixData,
)

# Database models
from backend.models.signals import Signal, SignalType, SignalStatus, DiscordChannel
from backend.models.user import User
from backend.models.market_data import Instrument
from backend.database import SessionLocal

# Services
from backend.services.notifications.discord_notifier import discord_notifier

logger = logging.getLogger(__name__)


class ATRSignalGenerator:
    """
    SINGLE ATR Signal Generator for AxiomFolio V1.

    Combines:
    - Sophisticated ATR calculations (from atr_calculator.py)
    - TradingView ATR Matrix signal logic (from atr_matrix.py)
    - Database persistence (signals.py)
    - Discord notifications
    - Scheduled execution
    """

    def __init__(self):
        self.atr_calculator = atr_calculator

        # ATR Matrix Strategy Parameters (from TradingView script)
        self.entry_max_distance = 4.0  # Max ATR distance for entry
        self.scale_out_levels = [7.0, 8.0, 9.0, 10.0]  # ATR distances for scale-out
        self.stop_loss_multiplier = 1.5  # ATR multiplier for stop loss
        self.min_atr_percent = 3.0  # Minimum ATR % for volatility
        self.min_price_position = 50.0  # Min position in 20D range
        self.min_risk_reward = 2.0  # Minimum R:R ratio
        self.min_confidence = 0.65  # Minimum confidence for signal generation

        # Discord channels for different signal types
        self.signal_channels = {
            SignalType.ENTRY: DiscordChannel.SIGNALS,
            SignalType.SCALE_OUT: DiscordChannel.SIGNALS,
            SignalType.EXIT: DiscordChannel.ALERTS,
            SignalType.RISK_WARNING: DiscordChannel.ALERTS,
        }

    async def generate_portfolio_signals(
        self, user_id: int, symbols: Optional[List[str]] = None
    ) -> Dict[str, any]:
        """
        Generate ATR signals for user's portfolio or specified symbols.

        Main entry point for scheduled signal generation.
        """
        db = SessionLocal()

        try:
            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User {user_id} not found")
                return {"error": "User not found"}

            # Get symbols to analyze
            if not symbols:
                symbols = await self._get_user_portfolio_symbols(db, user_id)

            if not symbols:
                logger.warning(f"No symbols found for user {user_id}")
                return {"symbols_analyzed": 0, "signals_generated": 0}

            logger.info(
                f"🔍 Generating ATR signals for {len(symbols)} symbols for user {user.username}"
            )

            # Generate signals for all symbols
            results = {
                "user_id": user_id,
                "symbols_analyzed": len(symbols),
                "signals_generated": 0,
                "entry_signals": 0,
                "scale_out_signals": 0,
                "exit_signals": 0,
                "risk_warnings": 0,
                "notifications_sent": 0,
                "execution_time": datetime.now().isoformat(),
            }

            # Process symbols in batches for performance
            batch_size = 10
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i : i + batch_size]

                # Process batch concurrently
                batch_tasks = [
                    self._generate_symbol_signals(db, user_id, symbol)
                    for symbol in batch
                ]
                batch_results = await asyncio.gather(
                    *batch_tasks, return_exceptions=True
                )

                # Collect results
                for symbol, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"Error generating signals for {symbol}: {result}")
                        continue

                    if result:
                        results["signals_generated"] += len(result)

                        # Count by signal type
                        for signal in result:
                            if signal.signal_type == SignalType.ENTRY:
                                results["entry_signals"] += 1
                            elif signal.signal_type == SignalType.SCALE_OUT:
                                results["scale_out_signals"] += 1
                            elif signal.signal_type == SignalType.EXIT:
                                results["exit_signals"] += 1
                            elif signal.signal_type == SignalType.RISK_WARNING:
                                results["risk_warnings"] += 1

                        # Send Discord notifications
                        for signal in result:
                            notification_sent = await self._send_signal_notification(
                                signal
                            )
                            if notification_sent:
                                results["notifications_sent"] += 1

            db.commit()

            logger.info(f"✅ Signal generation complete: {results}")
            return results

        except Exception as e:
            db.rollback()
            logger.error(f"Error generating portfolio signals: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    async def _generate_symbol_signals(
        self, db: Session, user_id: int, symbol: str
    ) -> List[Signal]:
        """Generate ATR signals for a single symbol."""
        try:
            # Get comprehensive ATR data
            atr_result = await self.atr_calculator._calculate_single_atr_result(symbol)
            matrix_data = await self.atr_calculator.calculate_matrix_atr(symbol)

            if atr_result.atr_value == 0 or atr_result.confidence < self.min_confidence:
                logger.warning(
                    f"⚠️ Insufficient ATR data for {symbol} (confidence: {atr_result.confidence:.2f})"
                )
                return []

            # Get market data for additional analysis
            market_data = await self._get_enhanced_market_data(symbol)

            if not market_data:
                logger.warning(f"⚠️ No market data for {symbol}")
                return []

            # Generate signals based on ATR Matrix strategy
            signals = []

            # 1. Check for ENTRY signals
            entry_signal = await self._check_entry_signal(
                db, user_id, symbol, atr_result, matrix_data, market_data
            )
            if entry_signal:
                signals.append(entry_signal)

            # 2. Check for SCALE_OUT signals
            scale_signals = await self._check_scale_out_signals(
                db, user_id, symbol, atr_result, matrix_data, market_data
            )
            signals.extend(scale_signals)

            # 3. Check for EXIT/RISK signals
            exit_signal = await self._check_exit_signals(
                db, user_id, symbol, atr_result, matrix_data, market_data
            )
            if exit_signal:
                signals.append(exit_signal)

            # Save valid signals to database
            valid_signals = []
            for signal in signals:
                # Validate signal quality
                if self._validate_signal_quality(signal, atr_result):
                    db.add(signal)
                    valid_signals.append(signal)
                    logger.info(
                        f"💡 Generated {signal.signal_type.value} signal for {symbol}: strength={signal.signal_strength}"
                    )

            return valid_signals

        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {e}")
            return []

    async def _check_entry_signal(
        self,
        db: Session,
        user_id: int,
        symbol: str,
        atr_result: ATRResult,
        matrix_data: ATRMatrixData,
        market_data: Dict,
    ) -> Optional[Signal]:
        """Check for ATR Matrix ENTRY signal conditions."""
        try:
            current_price = market_data.get("close", 0)
            sma_21 = market_data.get("sma_21", market_data.get("sma_20", 0))
            sma_50 = market_data.get("sma_50", 0)
            atr_distance = market_data.get("atr_distance", 0)
            ma_aligned = market_data.get("ma_aligned", False)
            price_position_20d = market_data.get("price_position_20d", 0)

            # ATR Matrix Entry Conditions (from TradingView script)
            conditions_met = []
            strength = 0.0

            # 1. Core condition: ATR Distance between 0 and 4 (buy zone)
            if 0 <= atr_distance <= self.entry_max_distance:
                conditions_met.append(f"ATR distance {atr_distance:.1f}x in buy zone")
                strength += 0.35
            else:
                return None  # Hard requirement

            # 2. Core condition: Price above SMA21 (canonical)
            if current_price > sma_21:
                conditions_met.append("Price above SMA21")
                strength += 0.25
            else:
                return None  # Hard requirement

            # 3. Moving average alignment (highly preferred)
            if ma_aligned:
                conditions_met.append("Moving averages aligned")
                strength += 0.20

            # 4. Position in 20-day range (above 50%)
            if price_position_20d > self.min_price_position:
                conditions_met.append(
                    f"Strong 20D position ({price_position_20d:.0f}%)"
                )
                strength += 0.10

            # 5. ATR volatility sufficient
            if atr_result.atr_percentage >= self.min_atr_percent:
                conditions_met.append(
                    f"Good volatility ({atr_result.atr_percentage:.1f}%)"
                )
                strength += 0.10

            # Must meet minimum strength threshold
            if strength < 0.60:  # Require strong signals only
                return None

            # Calculate targets and stop loss
            stop_loss = current_price - (
                self.stop_loss_multiplier * atr_result.atr_value
            )
            target_1 = sma_50 + (7 * atr_result.atr_value)  # 7 ATR target
            target_2 = sma_50 + (10 * atr_result.atr_value)  # 10 ATR target
            target_3 = sma_50 + (12 * atr_result.atr_value)  # 12 ATR target

            # Risk/reward ratio
            risk = current_price - stop_loss
            reward = target_1 - current_price
            rr_ratio = reward / risk if risk > 0 else 0

            if rr_ratio < self.min_risk_reward:
                return None  # Insufficient risk/reward

            # Calculate time horizon based on ATR distance
            if atr_distance <= 2:
                time_horizon = "2-3 weeks"
                time_horizon_days = 18
            elif atr_distance <= 3:
                time_horizon = "1-2 weeks"
                time_horizon_days = 10
            else:
                time_horizon = "1-3 days"
                time_horizon_days = 2

            # Get instrument ID
            instrument = (
                db.query(Instrument).filter(Instrument.symbol == symbol).first()
            )
            if not instrument:
                logger.warning(f"Instrument {symbol} not found")
                return None

            # Create entry signal
            signal = Signal(
                user_id=user_id,
                instrument_id=instrument.id,
                symbol=symbol,
                signal_type=SignalType.ENTRY,
                status=SignalStatus.ACTIVE,
                signal_strength=round(strength, 3),
                confidence_score=round(atr_result.confidence, 3),
                entry_price=round(current_price, 2),
                current_price=round(current_price, 2),
                stop_loss=round(stop_loss, 2),
                take_profit=round(target_1, 2),
                targets=[round(target_1, 2), round(target_2, 2), round(target_3, 2)],
                atr_distance=round(atr_distance, 2),
                risk_reward_ratio=round(rr_ratio, 2),
                time_horizon=time_horizon,
                time_horizon_days=time_horizon_days,
                company_name=market_data.get("company_name", ""),
                sector=market_data.get("sector", ""),
                market_cap_category=self._classify_market_cap(
                    market_data.get("market_cap", 0)
                ),
                signal_metadata={
                    "atr_value": atr_result.atr_value,
                    "atr_percentage": atr_result.atr_percentage,
                    "volatility_level": atr_result.volatility_level,
                    "ma_aligned": ma_aligned,
                    "price_position_20d": price_position_20d,
                    "conditions_met": conditions_met,
                    "entry_reason": "; ".join(conditions_met),
                },
                expires_at=datetime.now()
                + timedelta(days=1),  # Signal expires in 1 day
            )

            return signal

        except Exception as e:
            logger.error(f"Error checking entry signal for {symbol}: {e}")
            return None

    async def _check_scale_out_signals(
        self,
        db: Session,
        user_id: int,
        symbol: str,
        atr_result: ATRResult,
        matrix_data: ATRMatrixData,
        market_data: Dict,
    ) -> List[Signal]:
        """Check for SCALE_OUT signal conditions."""
        signals = []

        try:
            current_price = market_data.get("close", 0)
            sma_50 = market_data.get("sma_50", 0)
            atr_distance = market_data.get("atr_distance", 0)

            if not all([current_price, sma_50, atr_distance]):
                return signals

            # Check each scale-out level
            for level in self.scale_out_levels:
                if atr_distance >= level:
                    # Calculate target price for this level
                    target_price = sma_50 + (level * atr_result.atr_value)

                    # Calculate signal strength (higher for bigger overshoots)
                    overshoot = atr_distance - level
                    strength = 0.70 + min(overshoot * 0.05, 0.25)

                    # Get instrument
                    instrument = (
                        db.query(Instrument).filter(Instrument.symbol == symbol).first()
                    )
                    if not instrument:
                        continue

                    signal = Signal(
                        user_id=user_id,
                        instrument_id=instrument.id,
                        symbol=symbol,
                        signal_type=SignalType.SCALE_OUT,
                        status=SignalStatus.ACTIVE,
                        signal_strength=round(strength, 3),
                        confidence_score=round(atr_result.confidence, 3),
                        entry_price=round(current_price, 2),
                        current_price=round(current_price, 2),
                        take_profit=round(target_price, 2),
                        atr_distance=round(atr_distance, 2),
                        time_horizon="Immediate",
                        time_horizon_days=1,
                        signal_metadata={
                            "scale_level": level,
                            "target_price": target_price,
                            "overshoot": overshoot,
                            "reason": f"ATR distance {atr_distance:.1f}x reached {level}x scale-out level",
                        },
                        expires_at=datetime.now() + timedelta(hours=6),
                    )

                    signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"Error checking scale-out signals for {symbol}: {e}")
            return []

    async def _check_exit_signals(
        self,
        db: Session,
        user_id: int,
        symbol: str,
        atr_result: ATRResult,
        matrix_data: ATRMatrixData,
        market_data: Dict,
    ) -> Optional[Signal]:
        """Check for EXIT/RISK signal conditions."""
        try:
            current_price = market_data.get("close", 0)
            sma_50 = market_data.get("sma_50", 0)
            atr_distance = market_data.get("atr_distance", 0)

            if not all([current_price, sma_50]):
                return None

            # Critical: Price below SMA50
            if current_price < sma_50:
                instrument = (
                    db.query(Instrument).filter(Instrument.symbol == symbol).first()
                )
                if not instrument:
                    return None

                return Signal(
                    user_id=user_id,
                    instrument_id=instrument.id,
                    symbol=symbol,
                    signal_type=SignalType.RISK_WARNING,
                    status=SignalStatus.ACTIVE,
                    signal_strength=0.90,
                    confidence_score=round(atr_result.confidence, 3),
                    entry_price=round(current_price, 2),
                    current_price=round(current_price, 2),
                    atr_distance=round(atr_distance, 2) if atr_distance else None,
                    time_horizon="Immediate",
                    time_horizon_days=1,
                    signal_metadata={
                        "risk_reason": "Price below SMA50 - Major support break",
                        "urgency": "HIGH",
                        "recommended_action": "Consider position reduction or exit",
                    },
                    expires_at=datetime.now() + timedelta(hours=12),
                )

            # Overextended: Very high ATR distance
            if atr_distance and atr_distance > 12:
                instrument = (
                    db.query(Instrument).filter(Instrument.symbol == symbol).first()
                )
                if not instrument:
                    return None

                return Signal(
                    user_id=user_id,
                    instrument_id=instrument.id,
                    symbol=symbol,
                    signal_type=SignalType.RISK_WARNING,
                    status=SignalStatus.ACTIVE,
                    signal_strength=0.75,
                    confidence_score=round(atr_result.confidence, 3),
                    entry_price=round(current_price, 2),
                    current_price=round(current_price, 2),
                    atr_distance=round(atr_distance, 2),
                    time_horizon="1-2 days",
                    time_horizon_days=2,
                    signal_metadata={
                        "risk_reason": f"Extremely overextended at {atr_distance:.1f}x ATR distance",
                        "urgency": "MEDIUM",
                        "recommended_action": "High probability of pullback",
                    },
                    expires_at=datetime.now() + timedelta(hours=24),
                )

            return None

        except Exception as e:
            logger.error(f"Error checking exit signals for {symbol}: {e}")
            return None

    async def _send_signal_notification(self, signal: Signal) -> bool:
        """Send Discord notification for generated signal."""
        try:
            # Determine Discord channel
            channel = self.signal_channels.get(
                signal.signal_type, DiscordChannel.SIGNALS
            )

            # Format message based on signal type
            if signal.signal_type == SignalType.ENTRY:
                message = self._format_entry_message(signal)
            elif signal.signal_type == SignalType.SCALE_OUT:
                message = self._format_scale_out_message(signal)
            elif signal.signal_type == SignalType.RISK_WARNING:
                message = self._format_risk_message(signal)
            else:
                message = self._format_generic_message(signal)

            # Send Discord notification
            success = await discord_notifier.send_signal_alert(
                message=message,
                channel=channel,
                signal_data={
                    "symbol": signal.symbol,
                    "signal_type": signal.signal_type.value,
                    "strength": signal.signal_strength,
                    "price": signal.current_price,
                    "time_horizon": signal.time_horizon,
                },
            )

            if success:
                signal.discord_sent = True
                signal.discord_channel = channel
                logger.info(
                    f"📢 Sent {signal.signal_type.value} notification for {signal.symbol}"
                )

            return success

        except Exception as e:
            logger.error(f"Error sending signal notification: {e}")
            return False

    def _format_entry_message(self, signal: Signal) -> str:
        """Format Discord message for ENTRY signals."""
        upside_pct = (
            (signal.take_profit - signal.current_price) / signal.current_price
        ) * 100

        return f"""🚀 **ENTRY Signal: {signal.symbol}** 
        
💰 **Price**: ${signal.current_price:.2f}
🎯 **Target**: ${signal.take_profit:.2f} ({upside_pct:+.1f}%)
🛑 **Stop Loss**: ${signal.stop_loss:.2f}
📊 **Risk/Reward**: {signal.risk_reward_ratio:.1f}:1
⏱️ **Time Horizon**: {signal.time_horizon}
💪 **Strength**: {signal.signal_strength*100:.0f}%
📈 **ATR Distance**: {signal.atr_distance:.1f}x

📝 **Reason**: {signal.signal_metadata.get('entry_reason', 'ATR Matrix entry conditions met')}"""

    def _format_scale_out_message(self, signal: Signal) -> str:
        """Format Discord message for SCALE_OUT signals."""
        level = signal.signal_metadata.get("scale_level", 0)

        return f"""📈 **SCALE-OUT Alert: {signal.symbol}**
        
🎯 **Current**: ${signal.current_price:.2f}
📏 **ATR Distance**: {signal.atr_distance:.1f}x (reached {level:.0f}x level)
💪 **Strength**: {signal.signal_strength*100:.0f}%

⚡ **Action**: Consider taking partial profits"""

    def _format_risk_message(self, signal: Signal) -> str:
        """Format Discord message for RISK_WARNING signals."""
        risk_reason = signal.signal_metadata.get(
            "risk_reason", "Risk condition detected"
        )
        urgency = signal.signal_metadata.get("urgency", "MEDIUM")

        urgency_emoji = "🚨" if urgency == "HIGH" else "⚠️"

        return f"""{urgency_emoji} **RISK Alert: {signal.symbol}**
        
💰 **Price**: ${signal.current_price:.2f}
📈 **ATR Distance**: {signal.atr_distance:.1f}x
🚨 **Risk**: {risk_reason}
⚡ **Action**: {signal.signal_metadata.get('recommended_action', 'Review position')}"""

    def _format_generic_message(self, signal: Signal) -> str:
        """Format generic Discord message."""
        return f"""📊 **{signal.signal_type.value.upper()} Signal: {signal.symbol}**
        
💰 **Price**: ${signal.current_price:.2f}
💪 **Strength**: {signal.signal_strength*100:.0f}%
⏱️ **Time Horizon**: {signal.time_horizon}"""

    # Helper Methods
    async def _get_user_portfolio_symbols(self, db: Session, user_id: int) -> List[str]:
        """Get symbols from user's portfolio for analysis."""
        # TODO: Implement based on user's actual holdings
        # For now, return major tech stocks
        return ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA", "AMZN", "META", "NFLX"]

    async def _get_enhanced_market_data(self, symbol: str) -> Dict:
        """Get enhanced market data including moving averages and technical indicators."""
        # TODO: Implement with actual market data service
        # For now, return mock data structure
        return {
            "close": 180.0,
            "sma_20": 175.0,
            "sma_50": 170.0,
            "atr_distance": 2.5,
            "ma_aligned": True,
            "price_position_20d": 75.0,
            "company_name": f"{symbol} Inc",
            "sector": "Technology",
            "market_cap": 1000000000,
        }

    def _classify_market_cap(self, market_cap: float) -> str:
        """Classify market cap category."""
        if market_cap > 200_000_000_000:  # $200B+
            return "mega"
        elif market_cap > 10_000_000_000:  # $10B+
            return "large"
        elif market_cap > 2_000_000_000:  # $2B+
            return "mid"
        elif market_cap > 300_000_000:  # $300M+
            return "small"
        else:
            return "micro"

    def _validate_signal_quality(self, signal: Signal, atr_result: ATRResult) -> bool:
        """Validate signal meets quality thresholds."""
        if signal.signal_strength < 0.60:
            return False
        if signal.confidence_score < 0.65:
            return False
        if (
            signal.signal_type == SignalType.ENTRY
            and signal.risk_reward_ratio < self.min_risk_reward
        ):
            return False
        return True


# =============================================================================
# GLOBAL INSTANCE & SCHEDULED EXECUTION
# =============================================================================

# Global signal generator instance
atr_signal_generator = ATRSignalGenerator()


# Convenience function for scheduled execution
async def run_daily_atr_signals(user_id: int = 1) -> Dict:
    """
    Run daily ATR signal generation for a user.
    Called by cron scheduler.
    """
    logger.info(f"🚀 Starting daily ATR signal generation for user {user_id}")

    result = await atr_signal_generator.generate_portfolio_signals(user_id)

    logger.info(f"✅ Daily ATR signals complete: {result}")
    return result
