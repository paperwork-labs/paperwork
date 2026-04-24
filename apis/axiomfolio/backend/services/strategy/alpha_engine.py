"""Alpha factor engine for multi-factor signal generation.

Defines and combines alpha factors for quantitative stock selection.

medallion: gold
"""
from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from bisect import bisect_left
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models.market_data import MarketSnapshot

logger = logging.getLogger(__name__)


class FactorCategory(str, Enum):
    """Categories of alpha factors."""
    MOMENTUM = "momentum"
    VALUE = "value"
    QUALITY = "quality"
    VOLATILITY = "volatility"
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"


@dataclass
class AlphaFactor:
    """Definition of an alpha factor."""
    name: str
    category: FactorCategory
    description: str
    compute: Callable[[MarketSnapshot], Optional[float]]
    weight: float = 1.0
    higher_is_better: bool = True


@dataclass
class FactorScore:
    """Score for a single factor on a symbol."""
    factor_name: str
    raw_value: Optional[float]
    z_score: float  # Normalized across universe
    percentile: float  # 0-100


@dataclass
class CompositeScore:
    """Combined alpha score for a symbol."""
    symbol: str
    composite_score: float  # -1 to 1
    factor_scores: Dict[str, FactorScore]
    category_scores: Dict[str, float]
    rank: int
    signal: str  # "strong_buy", "buy", "hold", "sell", "strong_sell"
    computed_at: datetime


class AlphaEngine:
    """Multi-factor alpha engine for stock selection.
    
    Combines multiple alpha factors into a composite score.
    Supports regime-weighted factor selection.
    """
    
    # Signal thresholds
    SIGNAL_THRESHOLDS = {
        "strong_buy": 0.6,
        "buy": 0.2,
        "hold": -0.2,
        "sell": -0.6,
    }
    
    def __init__(self, db: Session):
        self.db = db
        self.factors = self._define_factors()
        self._regime_weights: Dict[str, Dict[str, float]] = {
            "R1": {"momentum": 1.5, "quality": 0.8},  # Risk-on: favor momentum
            "R2": {"momentum": 1.2, "quality": 1.0},
            "R3": {"momentum": 1.0, "quality": 1.0},  # Neutral
            "R4": {"momentum": 0.7, "quality": 1.3},  # Risk-off: favor quality
            "R5": {"momentum": 0.5, "quality": 1.5},  # High risk: favor quality
        }
    
    def _define_factors(self) -> List[AlphaFactor]:
        """Define all alpha factors."""
        return [
            # Momentum factors
            AlphaFactor(
                name="rs_mansfield",
                category=FactorCategory.MOMENTUM,
                description="Relative Strength vs SPY",
                compute=lambda s: float(s.rs_mansfield_pct) if s.rs_mansfield_pct else None,
                weight=1.2,
                higher_is_better=True,
            ),
            AlphaFactor(
                name="price_vs_sma150",
                category=FactorCategory.MOMENTUM,
                description="Price distance from SMA150",
                compute=self._compute_price_vs_sma150,
                weight=1.0,
                higher_is_better=True,
            ),
            AlphaFactor(
                name="rsi_momentum",
                category=FactorCategory.MOMENTUM,
                description="RSI momentum score (50-70 optimal)",
                compute=self._compute_rsi_score,
                weight=0.8,
                higher_is_better=True,
            ),
            
            # Quality factors
            AlphaFactor(
                name="stage_quality",
                category=FactorCategory.QUALITY,
                description="Stage Analysis quality (2A = high)",
                compute=self._compute_stage_quality,
                weight=1.5,
                higher_is_better=True,
            ),
            AlphaFactor(
                name="sma_alignment",
                category=FactorCategory.QUALITY,
                description="SMA stack alignment (10>21>50>150)",
                compute=self._compute_sma_alignment,
                weight=1.0,
                higher_is_better=True,
            ),
            
            # Volatility factors
            AlphaFactor(
                name="atr_normalized",
                category=FactorCategory.VOLATILITY,
                description="ATR as % of price (lower = calmer)",
                compute=lambda s: float(s.atr_percent) if s.atr_percent else None,
                weight=0.5,
                higher_is_better=False,  # Prefer lower volatility
            ),
            
            # Technical factors
            AlphaFactor(
                name="td_sequential",
                category=FactorCategory.TECHNICAL,
                description="TD Sequential setup/countdown",
                compute=self._compute_td_score,
                weight=0.6,
                higher_is_better=True,
            ),
            AlphaFactor(
                name="volume_trend",
                category=FactorCategory.TECHNICAL,
                description="Volume vs average",
                compute=self._compute_volume_trend,
                weight=0.4,
                higher_is_better=True,
            ),
        ]
    
    def compute_scores(
        self,
        symbols: Optional[List[str]] = None,
        regime: str = "R3",
    ) -> List[CompositeScore]:
        """Compute alpha scores for symbols.
        
        Args:
            symbols: List of symbols (None = all tracked)
            regime: Current market regime for weighting
            
        Returns:
            List of CompositeScore sorted by rank
        """
        # Get snapshots
        query = self.db.query(MarketSnapshot).filter(
            MarketSnapshot.analysis_type == "technical_snapshot"
        )
        
        if symbols:
            query = query.filter(MarketSnapshot.symbol.in_([s.upper() for s in symbols]))
        
        # Get latest snapshot per symbol
        snapshots = query.all()
        
        if not snapshots:
            return []
        
        # Deduplicate to latest per symbol
        by_symbol: Dict[str, MarketSnapshot] = {}
        for snap in snapshots:
            existing = by_symbol.get(snap.symbol)
            if not existing or (
                snap.analysis_timestamp and existing.analysis_timestamp and
                snap.analysis_timestamp > existing.analysis_timestamp
            ):
                by_symbol[snap.symbol] = snap
        
        snapshots = list(by_symbol.values())
        
        # Compute raw factor values
        raw_values: Dict[str, Dict[str, Optional[float]]] = {}
        
        for snap in snapshots:
            raw_values[snap.symbol] = {}
            for factor in self.factors:
                try:
                    value = factor.compute(snap)
                    raw_values[snap.symbol][factor.name] = value
                except Exception as e:
                    logger.debug("Factor %s failed for %s: %s", factor.name, snap.symbol, e)
                    raw_values[snap.symbol][factor.name] = None
        
        # Compute z-scores and percentiles
        factor_stats = self._compute_factor_stats(raw_values)
        
        # Get regime weights
        regime_weights = self._regime_weights.get(regime, {})
        
        # Compute composite scores
        scores = []
        for snap in snapshots:
            factor_scores = {}
            category_totals: Dict[str, List[float]] = {}
            weighted_sum = 0.0
            total_weight = 0.0
            
            for factor in self.factors:
                raw = raw_values[snap.symbol].get(factor.name)
                
                if raw is None:
                    continue
                
                stats = factor_stats.get(factor.name, {})
                z_score = self._compute_z_score(raw, stats)
                percentile = self._compute_percentile(raw, stats)
                
                # Flip for factors where lower is better
                if not factor.higher_is_better:
                    z_score = -z_score
                    percentile = 100 - percentile
                
                factor_scores[factor.name] = FactorScore(
                    factor_name=factor.name,
                    raw_value=raw,
                    z_score=z_score,
                    percentile=percentile,
                )
                
                # Apply weight with regime adjustment
                category_mult = regime_weights.get(factor.category.value, 1.0)
                adjusted_weight = factor.weight * category_mult
                
                weighted_sum += z_score * adjusted_weight
                total_weight += adjusted_weight
                
                # Track category scores
                cat = factor.category.value
                if cat not in category_totals:
                    category_totals[cat] = []
                category_totals[cat].append(z_score)
            
            # Compute composite score (-1 to 1 range via tanh)
            if total_weight > 0:
                raw_composite = weighted_sum / total_weight
                import math
                composite = math.tanh(raw_composite / 2)  # Compress to -1,1
            else:
                composite = 0.0
            
            # Category averages
            category_scores = {
                cat: sum(vals) / len(vals) if vals else 0.0
                for cat, vals in category_totals.items()
            }
            
            # Determine signal
            signal = self._score_to_signal(composite)
            
            scores.append(CompositeScore(
                symbol=snap.symbol,
                composite_score=round(composite, 4),
                factor_scores=factor_scores,
                category_scores={k: round(v, 4) for k, v in category_scores.items()},
                rank=0,  # Set after sorting
                signal=signal,
                computed_at=datetime.now(timezone.utc),
            ))
        
        # Sort and rank
        scores.sort(key=lambda s: s.composite_score, reverse=True)
        for i, score in enumerate(scores):
            score.rank = i + 1
        
        return scores
    
    def get_top_picks(
        self,
        n: int = 10,
        regime: str = "R3",
        min_score: float = 0.2,
    ) -> List[CompositeScore]:
        """Get top N stocks by alpha score."""
        all_scores = self.compute_scores(regime=regime)
        
        # Filter by minimum score
        filtered = [s for s in all_scores if s.composite_score >= min_score]
        
        return filtered[:n]
    
    def get_factor_exposure(
        self,
        symbols: List[str],
    ) -> Dict[str, Dict[str, float]]:
        """Get factor exposure breakdown for symbols."""
        scores = self.compute_scores(symbols=symbols)
        
        exposures = {}
        for score in scores:
            exposures[score.symbol] = {
                name: fs.z_score
                for name, fs in score.factor_scores.items()
            }
        
        return exposures
    
    def _compute_factor_stats(
        self,
        raw_values: Dict[str, Dict[str, Optional[float]]],
    ) -> Dict[str, Dict[str, float]]:
        """Compute mean and std for each factor across universe."""
        stats = {}
        
        for factor in self.factors:
            values = [
                raw_values[sym].get(factor.name)
                for sym in raw_values
                if raw_values[sym].get(factor.name) is not None
            ]
            
            if not values:
                continue

            if factor.name == "stage_quality":
                sorted_v = sorted(values, reverse=True)
                k = max(1, math.ceil(0.30 * len(sorted_v)))
                ref_values = sorted_v[:k]
            else:
                ref_values = values

            mean = statistics.mean(ref_values)
            std = statistics.stdev(ref_values) if len(ref_values) > 1 else 1.0

            stats[factor.name] = {
                "mean": mean,
                "std": max(std, 0.001),  # Avoid division by zero
                "min": min(values),
                "max": max(values),
                "values": sorted(values),
            }

        return stats
    
    def _compute_z_score(
        self,
        value: float,
        stats: Dict[str, Any],
    ) -> float:
        """Compute z-score for a value."""
        if not stats:
            return 0.0
        
        mean = stats.get("mean", 0)
        std = stats.get("std", 1)
        
        return (value - mean) / std
    
    def _compute_percentile(
        self,
        value: float,
        stats: Dict[str, Any],
    ) -> float:
        """Compute percentile rank for a value using binary search (O(log n))."""
        values = stats.get("values", [])
        if not values:
            return 50.0
        
        # values is already sorted in _compute_factor_stats
        count_below = bisect_left(values, value)
        return (count_below / len(values)) * 100
    
    def _score_to_signal(self, score: float) -> str:
        """Convert composite score to signal."""
        if score >= self.SIGNAL_THRESHOLDS["strong_buy"]:
            return "strong_buy"
        elif score >= self.SIGNAL_THRESHOLDS["buy"]:
            return "buy"
        elif score >= self.SIGNAL_THRESHOLDS["hold"]:
            return "hold"
        elif score >= self.SIGNAL_THRESHOLDS["sell"]:
            return "sell"
        else:
            return "strong_sell"
    
    # Factor computation methods
    
    def _compute_price_vs_sma150(self, snap: MarketSnapshot) -> Optional[float]:
        """Compute price distance from SMA150."""
        if not snap.current_price or not snap.sma_150:
            return None
        return ((float(snap.current_price) - float(snap.sma_150)) / float(snap.sma_150)) * 100
    
    def _compute_rsi_score(self, snap: MarketSnapshot) -> Optional[float]:
        """Convert RSI to a momentum score.
        
        Optimal RSI for momentum is 50-70.
        Score peaks at 60 and falls off at extremes.
        """
        if snap.rsi is None:
            return None
        
        rsi = float(snap.rsi)
        
        # Score peaks at 60
        if rsi <= 30:
            return -1.0  # Oversold
        elif rsi <= 50:
            return (rsi - 30) / 20 - 1  # -1 to 0
        elif rsi <= 70:
            return 1 - abs(rsi - 60) / 10  # Peak at 60
        else:
            return -0.5 - (rsi - 70) / 60  # Overbought
    
    def _compute_stage_quality(self, snap: MarketSnapshot) -> Optional[float]:
        """Convert stage to quality score."""
        stage = snap.stage_label
        if not stage:
            return None
        
        # Stage quality mapping
        scores = {
            "2A": 1.0,
            "2B": 0.7,
            "2C": 0.4,
            "1B": 0.5,  # Bottoming
            "3A": 0.0,  # Topping
            "3B": -0.3,
            "4A": -0.6,
            "4B": -0.8,
            "4C": -1.0,
            "1A": 0.2,
        }
        
        return scores.get(stage, 0.0)
    
    def _compute_sma_alignment(self, snap: MarketSnapshot) -> Optional[float]:
        """Check SMA stack alignment."""
        smas = []
        
        for attr in ["ema_10", "sma_21", "sma_50", "sma_150"]:
            val = getattr(snap, attr, None)
            if val is not None:
                smas.append(float(val))
        
        if len(smas) < 4:
            return None
        
        # Check if in order (bullish alignment)
        in_order = all(smas[i] >= smas[i + 1] for i in range(len(smas) - 1))
        
        if in_order:
            return 1.0
        
        # Check how many pairs are in order
        ordered_pairs = sum(1 for i in range(len(smas) - 1) if smas[i] >= smas[i + 1])
        return ordered_pairs / (len(smas) - 1) * 2 - 1  # -1 to 1
    
    def _compute_td_score(self, snap: MarketSnapshot) -> Optional[float]:
        """Convert TD Sequential to actionable score."""
        td_setup = snap.td_buy_setup or 0
        td_countdown = snap.td_buy_countdown or 0
        
        # Buy setup 9 or countdown 13 = bullish
        if td_setup >= 9:
            return 0.8
        elif td_countdown >= 13:
            return 1.0
        elif td_setup >= 7:
            return 0.4
        
        return 0.0
    
    def _compute_volume_trend(self, snap: MarketSnapshot) -> Optional[float]:
        """Compute volume trend score."""
        vol_ratio = snap.vol_ratio
        if vol_ratio is None:
            return None
        
        ratio = float(vol_ratio)
        
        # Above average volume with price up = bullish
        if ratio > 1.5:
            return 0.8
        elif ratio > 1.2:
            return 0.4
        elif ratio > 0.8:
            return 0.0
        else:
            return -0.3  # Low volume


def get_composite_score_dict(score: CompositeScore) -> Dict[str, Any]:
    """Convert CompositeScore to dict for API response."""
    return {
        "symbol": score.symbol,
        "composite_score": score.composite_score,
        "rank": score.rank,
        "signal": score.signal,
        "category_scores": score.category_scores,
        "factor_scores": {
            name: {
                "raw_value": fs.raw_value,
                "z_score": round(fs.z_score, 3),
                "percentile": round(fs.percentile, 1),
            }
            for name, fs in score.factor_scores.items()
        },
        "computed_at": score.computed_at.isoformat(),
    }
