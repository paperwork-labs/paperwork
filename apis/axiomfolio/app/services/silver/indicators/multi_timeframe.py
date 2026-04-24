"""
Multi-Timeframe Stage Analysis Engine.

Computes stage classification on multiple timeframes (1H, 4H, 1D, 1W)
and calculates alignment scores for confluence-based trading.

medallion: silver
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.market_data import MarketSnapshot

logger = logging.getLogger(__name__)


@dataclass
class TimeframeStage:
    """Stage analysis result for a single timeframe."""

    timeframe: str  # "1H", "4H", "1D", "1W"
    stage: str  # "1", "2A", "2B", "3", "4A", "4B"
    trend: str  # "bullish", "bearish", "neutral"
    sma_slope: float  # Slope of primary SMA
    price_vs_sma: float  # Price distance from SMA as %
    confidence: float  # 0-1 confidence in classification


@dataclass
class MultiTimeframeResult:
    """Aggregate multi-timeframe analysis result."""

    symbol: str
    timestamp: datetime
    stages: Dict[str, TimeframeStage]  # Keyed by timeframe
    alignment_score: int  # 0-100
    primary_trend: str  # "bullish", "bearish", "mixed"
    recommendation: str  # "strong_buy", "buy", "hold", "sell", "strong_sell"

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "stages": {k: self._stage_to_dict(v) for k, v in self.stages.items()},
            "alignment_score": self.alignment_score,
            "primary_trend": self.primary_trend,
            "recommendation": self.recommendation,
        }

    def _stage_to_dict(self, s: TimeframeStage) -> dict:
        return {
            "timeframe": s.timeframe,
            "stage": s.stage,
            "trend": s.trend,
            "sma_slope": s.sma_slope,
            "price_vs_sma": s.price_vs_sma,
            "confidence": s.confidence,
        }


class MultiTimeframeEngine:
    """
    Computes stage analysis across multiple timeframes.

    Stage Analysis Primer (per Oliver Kell / Weinstein):
    - Stage 1: Base building (consolidation after downtrend)
    - Stage 2A: Early uptrend (breakout from base)
    - Stage 2B: Healthy uptrend (strong momentum)
    - Stage 3: Top building (consolidation at highs)
    - Stage 4A: Early downtrend (breakdown)
    - Stage 4B: Declining (strong downward momentum)

    Alignment scoring:
    - All timeframes bullish (2A/2B): 100
    - Most timeframes aligned: 60-90
    - Mixed signals: 30-60
    - Bearish alignment: 0-30
    """

    TIMEFRAMES = ["1H", "4H", "1D", "1W"]
    BULLISH_STAGES = {"2A", "2B"}
    BEARISH_STAGES = {"4A", "4B"}
    NEUTRAL_STAGES = {"1", "3"}

    def __init__(self, db: Session):
        self.db = db

    def analyze(self, symbol: str) -> Optional[MultiTimeframeResult]:
        """
        Run multi-timeframe analysis on a symbol.

        Returns None if insufficient data.
        """
        stages: Dict[str, TimeframeStage] = {}

        for tf in self.TIMEFRAMES:
            stage = self._analyze_timeframe(symbol, tf)
            if stage:
                stages[tf] = stage

        if not stages:
            logger.warning("No timeframe data for %s", symbol)
            return None

        # Calculate alignment score
        alignment = self._calculate_alignment(stages)

        # Determine primary trend
        trend = self._determine_trend(stages)

        # Generate recommendation
        rec = self._generate_recommendation(alignment, trend, stages)

        return MultiTimeframeResult(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            stages=stages,
            alignment_score=alignment,
            primary_trend=trend,
            recommendation=rec,
        )

    def analyze_batch(self, symbols: List[str]) -> Dict[str, MultiTimeframeResult]:
        """Analyze multiple symbols."""
        results = {}
        for symbol in symbols:
            result = self.analyze(symbol)
            if result:
                results[symbol] = result
        return results

    def update_snapshot(self, symbol: str) -> bool:
        """
        Run MTF analysis and update MarketSnapshot with results.

        Updates fields: stage_1h, stage_4h, stage_1w, mtf_alignment
        """
        result = self.analyze(symbol)
        if not result:
            return False

        # Find the snapshot to update
        snapshot = (
            self.db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == symbol,
                MarketSnapshot.analysis_type == "technical_snapshot",
            )
            .order_by(MarketSnapshot.analysis_timestamp.desc())
            .first()
        )

        if not snapshot:
            logger.warning("No snapshot found for %s", symbol)
            return False

        # Update MTF fields
        if "1H" in result.stages:
            snapshot.stage_1h = result.stages["1H"].stage
        if "4H" in result.stages:
            snapshot.stage_4h = result.stages["4H"].stage
        if "1W" in result.stages:
            snapshot.stage_1w = result.stages["1W"].stage
        snapshot.mtf_alignment = result.alignment_score

        # Caller controls commit scope
        logger.info(
            "Updated MTF for %s: alignment=%d, trend=%s",
            symbol,
            result.alignment_score,
            result.primary_trend,
        )
        return True

    def _analyze_timeframe(
        self, symbol: str, timeframe: str
    ) -> Optional[TimeframeStage]:
        """
        Analyze a single timeframe.

        For now, uses daily snapshot data and infers higher timeframes.
        Full implementation would use actual OHLCV bars per timeframe.
        """
        # Get the latest snapshot for the symbol
        snapshot = (
            self.db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == symbol,
                MarketSnapshot.analysis_type == "technical_snapshot",
            )
            .order_by(MarketSnapshot.analysis_timestamp.desc())
            .first()
        )

        if not snapshot:
            return None

        # Use daily stage as base, adjust for timeframe
        # In production, would compute from actual timeframe bars
        base_stage = snapshot.stage_label or "2B"
        sma_slope = float(snapshot.sma150_slope or 0)
        current_price = float(snapshot.current_price or 0)
        sma150 = float(snapshot.sma_150 or current_price)

        # Calculate price distance from SMA
        price_vs_sma = 0.0
        if sma150 > 0:
            price_vs_sma = ((current_price - sma150) / sma150) * 100

        # Determine trend from stage
        if base_stage in self.BULLISH_STAGES:
            trend = "bullish"
        elif base_stage in self.BEARISH_STAGES:
            trend = "bearish"
        else:
            trend = "neutral"

        # Confidence based on timeframe (longer = more reliable)
        confidence_map = {"1H": 0.6, "4H": 0.7, "1D": 0.85, "1W": 0.95}
        confidence = confidence_map.get(timeframe, 0.5)

        # Adjust stage based on timeframe characteristics
        # (Simplified - production would use actual timeframe data)
        adjusted_stage = self._adjust_stage_for_timeframe(
            base_stage, timeframe, sma_slope
        )

        return TimeframeStage(
            timeframe=timeframe,
            stage=adjusted_stage,
            trend=trend,
            sma_slope=sma_slope,
            price_vs_sma=price_vs_sma,
            confidence=confidence,
        )

    def _adjust_stage_for_timeframe(
        self, base_stage: str, timeframe: str, sma_slope: float
    ) -> str:
        """
        Adjust stage classification based on timeframe.

        Shorter timeframes are more volatile, longer are smoother.
        """
        # For now, use base stage for all timeframes
        # Full implementation would compute from actual OHLCV data
        return base_stage

    def _calculate_alignment(self, stages: Dict[str, TimeframeStage]) -> int:
        """
        Calculate alignment score (0-100).

        Higher score = more timeframes agree on direction.
        """
        if not stages:
            return 50

        bullish_count = 0
        bearish_count = 0
        total_weight = 0

        # Weight by timeframe importance
        weights = {"1H": 1, "4H": 2, "1D": 3, "1W": 4}

        for tf, stage in stages.items():
            weight = weights.get(tf, 1)
            total_weight += weight

            if stage.stage in self.BULLISH_STAGES:
                bullish_count += weight
            elif stage.stage in self.BEARISH_STAGES:
                bearish_count += weight

        if total_weight == 0:
            return 50

        # Calculate directional alignment
        if bullish_count > bearish_count:
            # Bullish alignment
            alignment = int(50 + (bullish_count / total_weight) * 50)
        elif bearish_count > bullish_count:
            # Bearish alignment (inverse)
            alignment = int(50 - (bearish_count / total_weight) * 50)
        else:
            alignment = 50

        return max(0, min(100, alignment))

    def _determine_trend(self, stages: Dict[str, TimeframeStage]) -> str:
        """Determine primary trend from stage analysis."""
        if not stages:
            return "mixed"

        bullish = sum(1 for s in stages.values() if s.stage in self.BULLISH_STAGES)
        bearish = sum(1 for s in stages.values() if s.stage in self.BEARISH_STAGES)

        if bullish > bearish and bullish >= len(stages) // 2:
            return "bullish"
        elif bearish > bullish and bearish >= len(stages) // 2:
            return "bearish"
        return "mixed"

    def _generate_recommendation(
        self,
        alignment: int,
        trend: str,
        stages: Dict[str, TimeframeStage],
    ) -> str:
        """Generate trading recommendation based on analysis."""
        # Priority: Daily stage + alignment
        daily_stage = stages.get("1D")

        if alignment >= 80 and trend == "bullish":
            return "strong_buy"
        elif alignment >= 60 and trend == "bullish":
            return "buy"
        elif alignment <= 20 and trend == "bearish":
            return "strong_sell"
        elif alignment <= 40 and trend == "bearish":
            return "sell"
        else:
            return "hold"
