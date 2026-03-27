"""
Real-time signal engine using Redis Streams.

Consumes bar data, evaluates strategies, and publishes signals.
Uses async Redis to avoid blocking the event loop.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.models.strategy import Strategy, StrategyStatus
from backend.models.signals import Signal, SignalType, SignalStatus
from backend.models.market_data import MarketSnapshot
from backend.services.risk.circuit_breaker import circuit_breaker
from backend.services.strategy.rule_evaluator import RuleEvaluator, ConditionGroup

logger = logging.getLogger(__name__)


@dataclass
class BarEvent:
    """Parsed bar event from Redis Stream."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None

    @classmethod
    def from_stream_data(cls, data: Dict[bytes, bytes]) -> "BarEvent":
        """Parse from Redis Stream message."""
        return cls(
            symbol=data.get(b"symbol", b"").decode(),
            timestamp=datetime.fromisoformat(
                data.get(b"timestamp", b"").decode()
            ),
            open=float(data.get(b"open", 0)),
            high=float(data.get(b"high", 0)),
            low=float(data.get(b"low", 0)),
            close=float(data.get(b"close", 0)),
            volume=int(data.get(b"volume", 0)),
            vwap=float(data.get(b"vwap", 0)) if data.get(b"vwap") else None,
        )


@dataclass
class SignalEvent:
    """Signal event to publish."""

    strategy_id: int
    symbol: str
    signal_type: str  # "entry_long", "entry_short", "exit"
    price: float
    timestamp: datetime
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "strategy_id": str(self.strategy_id),
            "symbol": self.symbol,
            "signal_type": self.signal_type,
            "price": str(self.price),
            "timestamp": self.timestamp.isoformat(),
            "confidence": str(self.confidence),
            "metadata": json.dumps(self.metadata),
        }


class SignalEngine:
    """
    Real-time signal engine using Redis Streams.

    Flow:
        stream:bar_close → evaluate strategies → stream:signal

    Features:
    - Consumer group for distributed processing
    - Strategy evaluation per bar
    - Signal deduplication
    - Circuit breaker integration
    """

    BAR_STREAM = "stream:bar_close"
    SIGNAL_STREAM = "stream:signal"
    CONSUMER_GROUP = "signal_engine"
    CONSUMER_NAME = "engine_1"

    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self._redis = redis_client
        self._running = False
        self._processed_count = 0
        self._signal_count = 0

    async def _get_redis(self) -> aioredis.Redis:
        """Get async Redis connection (lazy initialization)."""
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL)
        return self._redis

    async def start(self) -> None:
        """Start the signal engine."""
        if self._running:
            logger.warning("SignalEngine already running")
            return

        self._running = True

        # Create consumer group if not exists
        try:
            redis = await self._get_redis()
            await redis.xgroup_create(
                self.BAR_STREAM,
                self.CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
            logger.info("Created consumer group: %s", self.CONSUMER_GROUP)
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.error("Failed to create consumer group: %s", e)

        # Start processing loop
        asyncio.create_task(self._processing_loop())
        logger.info("SignalEngine started")

    async def stop(self) -> None:
        """Stop the signal engine."""
        self._running = False
        logger.info("SignalEngine stopped")

    async def _processing_loop(self) -> None:
        """Main processing loop - consume bars and evaluate strategies."""
        redis = await self._get_redis()
        while self._running:
            try:
                # Read from stream with consumer group (async)
                messages = await redis.xreadgroup(
                    self.CONSUMER_GROUP,
                    self.CONSUMER_NAME,
                    {self.BAR_STREAM: ">"},
                    count=100,
                    block=1000,  # 1 second timeout
                )

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for message_id, data in stream_messages:
                        try:
                            bar = BarEvent.from_stream_data(data)
                            await self._process_bar(bar)
                            self._processed_count += 1

                            # Acknowledge message (async)
                            await redis.xack(
                                self.BAR_STREAM,
                                self.CONSUMER_GROUP,
                                message_id,
                            )
                        except Exception as e:
                            logger.error(
                                "Error processing bar %s: %s",
                                message_id,
                                e,
                            )

            except Exception as e:
                logger.error("Processing loop error: %s", e)
                await asyncio.sleep(1)

    async def _process_bar(self, bar: BarEvent) -> None:
        """Process a single bar event."""
        # Check circuit breaker before processing
        allowed, reason, tier = circuit_breaker.can_trade(is_exit=False)
        if tier >= 3:
            logger.debug("Circuit breaker at tier 3, skipping signal evaluation")
            return

        db = SessionLocal()
        try:
            # Get active strategies that track this symbol
            strategies = self._get_active_strategies(db, bar.symbol)

            for strategy in strategies:
                try:
                    signals = await self._evaluate_strategy(db, strategy, bar)
                    for signal in signals:
                        await self._publish_signal(signal)
                        self._signal_count += 1
                except Exception as e:
                    logger.error(
                        "Error evaluating strategy %s: %s",
                        strategy.id,
                        e,
                    )
        finally:
            db.close()

    def _get_active_strategies(
        self, db: Session, symbol: str
    ) -> List[Strategy]:
        """Get active strategies that should evaluate this symbol."""
        strategies = (
            db.query(Strategy)
            .filter(
                Strategy.status == StrategyStatus.ACTIVE,
            )
            .all()
        )

        # Filter to strategies that include this symbol in their universe
        matching = []
        for strategy in strategies:
            universe = strategy.universe_filter or {}
            symbols = universe.get("symbols", [])
            sectors = universe.get("sectors", [])

            # If no filter, include all
            if not symbols and not sectors:
                matching.append(strategy)
            elif symbol in symbols:
                matching.append(strategy)
            # Could add sector matching here

        return matching

    async def _evaluate_strategy(
        self,
        db: Session,
        strategy: Strategy,
        bar: BarEvent,
    ) -> List[SignalEvent]:
        """
        Evaluate a strategy against a bar event.

        This is a simplified evaluation - real implementation would
        use the full indicator engine and strategy rules.
        """
        signals = []

        # Get strategy parameters
        params = strategy.parameters or {}
        entry_rules = params.get("entry_rules", {})
        exit_rules = params.get("exit_rules", {})

        # Check for existing position
        from backend.models.position import Position, PositionStatus

        position = (
            db.query(Position)
            .filter(
                Position.symbol == bar.symbol,
                Position.user_id == strategy.user_id,
                Position.status == PositionStatus.OPEN,
                Position.strategy_id == strategy.id,
            )
            .first()
        )

        # Evaluate exit rules if we have a position
        if position:
            exit_signal = self._evaluate_exit_rules(
                bar, position, exit_rules
            )
            if exit_signal:
                signals.append(
                    SignalEvent(
                        strategy_id=strategy.id,
                        symbol=bar.symbol,
                        signal_type="exit",
                        price=bar.close,
                        timestamp=bar.timestamp,
                        confidence=exit_signal.get("confidence", 1.0),
                        metadata={
                            "exit_tier": exit_signal.get("tier"),
                            "reason": exit_signal.get("reason"),
                        },
                    )
                )

        # Evaluate entry rules if no position
        else:
            entry_signal = self._evaluate_entry_rules(bar, entry_rules, db=db)
            if entry_signal:
                signals.append(
                    SignalEvent(
                        strategy_id=strategy.id,
                        symbol=bar.symbol,
                        signal_type="entry_long",
                        price=bar.close,
                        timestamp=bar.timestamp,
                        confidence=entry_signal.get("confidence", 1.0),
                        metadata={
                            "reason": entry_signal.get("reason"),
                        },
                    )
                )

        return signals

    def _evaluate_entry_rules(
        self,
        bar: BarEvent,
        rules: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate entry rules against current market conditions.

        Fetches MarketSnapshot for the symbol to get indicator values,
        builds context dict, and evaluates using RuleEvaluator.

        Args:
            bar: Current bar event with OHLCV data
            rules: Entry rules (ConditionGroup or dict/list for parsing)
            db: Database session (uses SessionLocal if not provided)

        Returns:
            Dict with entry signal details if conditions match, None otherwise
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            # Get latest MarketSnapshot for indicator context
            snapshot = (
                db.query(MarketSnapshot)
                .filter(
                    MarketSnapshot.symbol == bar.symbol,
                    MarketSnapshot.analysis_type == "stock",
                )
                .order_by(MarketSnapshot.as_of_timestamp.desc())
                .first()
            )

            if not snapshot:
                logger.debug("No MarketSnapshot for %s, skipping entry eval", bar.symbol)
                return None

            # Build evaluation context from snapshot + bar data
            context: Dict[str, Any] = {
                # Current bar
                "current_price": bar.close,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                # Stage Analysis
                "stage": snapshot.stage,
                "sub_stage": snapshot.sub_stage,
                # Moving averages
                "sma_5": snapshot.sma_5,
                "sma_10": snapshot.sma_10,
                "sma_21": snapshot.sma_21,
                "sma_50": snapshot.sma_50,
                "sma_100": snapshot.sma_100,
                "sma_150": snapshot.sma_150,
                "sma_200": snapshot.sma_200,
                "ema_8": snapshot.ema_8,
                "ema_21": snapshot.ema_21,
                # Relative strength
                "rs_rank": snapshot.rs_rank,
                "rs_rating": snapshot.rs_rating,
                # Momentum
                "rsi": snapshot.rsi,
                "rsi_14": snapshot.rsi,
                "adx": snapshot.adx,
                "macd": snapshot.macd,
                "macd_signal": snapshot.macd_signal,
                # Volatility
                "atr": snapshot.atr,
                "atr_14": snapshot.atr,
                "atr_pct": snapshot.atr_pct,
                # Volume analysis
                "volume_sma_20": snapshot.volume_sma_20,
                "volume_ratio": snapshot.volume / snapshot.volume_sma_20 if snapshot.volume_sma_20 else None,
                # TD Sequential
                "td_buy_setup": snapshot.td_buy_setup,
                "td_sell_setup": snapshot.td_sell_setup,
                # Price levels
                "week_52_high": snapshot.week_52_high,
                "week_52_low": snapshot.week_52_low,
                # Distance calculations
                "pct_from_sma_50": (bar.close / snapshot.sma_50 - 1) * 100 if snapshot.sma_50 else None,
                "pct_from_sma_200": (bar.close / snapshot.sma_200 - 1) * 100 if snapshot.sma_200 else None,
            }

            # Parse rules to ConditionGroup if needed
            if isinstance(rules, ConditionGroup):
                condition_group = rules
            else:
                try:
                    condition_group = ConditionGroup.from_json(rules)
                except ValueError as e:
                    logger.warning("Invalid entry rules for %s: %s", bar.symbol, e)
                    return None

            # Check for empty rules (no conditions = no signal)
            if not condition_group.conditions and not condition_group.groups:
                return None

            # Evaluate rules
            evaluator = RuleEvaluator()
            result = evaluator.evaluate(condition_group, context)

            if result.matched:
                # Calculate confidence from rule match quality
                matched_count = len(result.details.get("matched_conditions", []))
                total_count = len(condition_group.conditions) + len(condition_group.groups)
                confidence = matched_count / max(total_count, 1)

                return {
                    "confidence": min(1.0, confidence + 0.3),  # Boost for full match
                    "reason": f"Entry rules matched: {result.details}",
                    "stage": context.get("stage"),
                    "rs_rank": context.get("rs_rank"),
                }

            return None

        except Exception as e:
            logger.warning("Entry rules evaluation failed for %s: %s", bar.symbol, e)
            return None
        finally:
            if close_db:
                db.close()

    def _evaluate_exit_rules(
        self,
        bar: BarEvent,
        position: Any,
        rules: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate exit rules.

        Checks:
        - Stop loss (ATR-based or fixed)
        - Take profit targets
        - Trailing stop
        - Time-based exit
        """
        if not position or not position.average_cost:
            return None

        entry_price = float(position.average_cost)
        current_price = bar.close
        pnl_pct = (current_price - entry_price) / entry_price * 100

        # Check stop loss
        stop_loss_pct = rules.get("stop_loss_pct", -7.0)
        if pnl_pct <= stop_loss_pct:
            return {
                "tier": 1,
                "reason": f"Stop loss triggered at {pnl_pct:.1f}%",
                "confidence": 1.0,
            }

        # Check take profit
        take_profit_pct = rules.get("take_profit_pct", 20.0)
        if pnl_pct >= take_profit_pct:
            return {
                "tier": 3,
                "reason": f"Take profit triggered at {pnl_pct:.1f}%",
                "confidence": 1.0,
            }

        return None

    async def _publish_signal(self, signal: SignalEvent) -> None:
        """Publish signal to Redis Stream (async)."""
        try:
            redis = await self._get_redis()
            await redis.xadd(
                self.SIGNAL_STREAM,
                signal.to_dict(),
                maxlen=10000,
                approximate=True,
            )
            logger.info(
                "Published signal: %s %s @ %.2f",
                signal.signal_type,
                signal.symbol,
                signal.price,
            )
        except Exception as e:
            logger.error("Failed to publish signal: %s", e)

    async def get_status(self) -> dict:
        """Get engine status (async)."""
        redis = await self._get_redis()
        return {
            "running": self._running,
            "processed_bars": self._processed_count,
            "signals_generated": self._signal_count,
            "bar_stream_length": await redis.xlen(self.BAR_STREAM),
            "signal_stream_length": await redis.xlen(self.SIGNAL_STREAM),
        }


# Module-level singleton
signal_engine = SignalEngine()
