"""Sentiment aggregation service.

Aggregates social/news sentiment for symbols to enhance trading decisions.

medallion: silver
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from backend.config import settings

logger = logging.getLogger(__name__)


class SentimentLevel(str, Enum):
    """Sentiment classification levels."""
    VERY_BEARISH = "very_bearish"  # -1.0 to -0.6
    BEARISH = "bearish"  # -0.6 to -0.2
    NEUTRAL = "neutral"  # -0.2 to 0.2
    BULLISH = "bullish"  # 0.2 to 0.6
    VERY_BULLISH = "very_bullish"  # 0.6 to 1.0


@dataclass
class SentimentScore:
    """Sentiment data for a symbol."""
    symbol: str
    composite_score: float  # -1.0 to 1.0
    level: SentimentLevel
    sources: Dict[str, float]  # Score by source
    mention_count: int
    bullish_ratio: float  # % bullish mentions
    updated_at: datetime
    confidence: float  # Based on mention count and agreement


@dataclass
class SentimentAlert:
    """Alert for significant sentiment change."""
    symbol: str
    alert_type: str  # "spike", "reversal", "extreme"
    previous_score: float
    current_score: float
    change_pct: float
    message: str


class SentimentService:
    """Aggregates sentiment from multiple sources.
    
    Sources (when API keys available):
    - StockTwits: Social sentiment
    - Finnhub: News sentiment
    - Alpha Vantage: News sentiment
    - Reddit: Wallstreetbets, stocks subreddit
    
    Falls back to cached/simulated data when APIs unavailable.
    """
    
    # Score thresholds for sentiment levels
    THRESHOLDS = {
        "very_bearish": -0.6,
        "bearish": -0.2,
        "neutral": 0.2,
        "bullish": 0.6,
    }
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._cache: Dict[str, SentimentScore] = {}
        self._cache_ttl = timedelta(minutes=15)
    
    async def get_sentiment(
        self,
        symbol: str,
        use_cache: bool = True,
    ) -> SentimentScore:
        """Get current sentiment for a symbol.
        
        Args:
            symbol: Stock ticker
            use_cache: Use cached data if fresh
            
        Returns:
            SentimentScore with composite sentiment
        """
        symbol = symbol.upper()
        
        # Check cache
        if use_cache and symbol in self._cache:
            cached = self._cache[symbol]
            age = datetime.now(timezone.utc) - cached.updated_at
            if age < self._cache_ttl:
                return cached
        
        # Fetch from sources
        sources: Dict[str, float] = {}
        total_weight = 0.0
        weighted_sum = 0.0
        mention_count = 0
        
        # Try StockTwits
        stocktwits = await self._fetch_stocktwits(symbol)
        if stocktwits:
            sources["stocktwits"] = stocktwits["score"]
            weight = 1.0
            weighted_sum += stocktwits["score"] * weight
            total_weight += weight
            mention_count += stocktwits["mentions"]
        
        # Try Finnhub news sentiment
        finnhub = await self._fetch_finnhub(symbol)
        if finnhub:
            sources["finnhub"] = finnhub["score"]
            weight = 0.8
            weighted_sum += finnhub["score"] * weight
            total_weight += weight
            mention_count += finnhub["articles"]
        
        # Calculate composite score
        if total_weight > 0:
            composite = weighted_sum / total_weight
        else:
            # No data available - return neutral with low confidence
            composite = 0.0
        
        # Determine level
        level = self._score_to_level(composite)
        
        # Calculate bullish ratio
        bullish_count = sum(1 for s in sources.values() if s > 0.2)
        bullish_ratio = bullish_count / len(sources) if sources else 0.5
        
        # Calculate confidence based on data availability
        confidence = min(1.0, total_weight / 2.0) * min(1.0, mention_count / 100)
        
        score = SentimentScore(
            symbol=symbol,
            composite_score=round(composite, 3),
            level=level,
            sources=sources,
            mention_count=mention_count,
            bullish_ratio=round(bullish_ratio, 2),
            updated_at=datetime.now(timezone.utc),
            confidence=round(confidence, 2),
        )
        
        # Cache result
        self._cache[symbol] = score
        
        return score
    
    async def get_batch_sentiment(
        self,
        symbols: List[str],
    ) -> Dict[str, SentimentScore]:
        """Get sentiment for multiple symbols."""
        results = {}
        for symbol in symbols:
            try:
                results[symbol] = await self.get_sentiment(symbol)
            except Exception as e:
                logger.warning("Failed to get sentiment for %s: %s", symbol, e)
        return results
    
    async def detect_alerts(
        self,
        symbols: List[str],
        change_threshold: float = 0.3,
    ) -> List[SentimentAlert]:
        """Detect significant sentiment changes.
        
        Args:
            symbols: List of symbols to check
            change_threshold: Minimum change to trigger alert
            
        Returns:
            List of sentiment alerts
        """
        alerts = []
        
        for symbol in symbols:
            symbol = symbol.upper()
            
            # Get previous cached score
            previous = self._cache.get(symbol)
            if previous is None:
                continue
            
            # Get fresh score
            current = await self.get_sentiment(symbol, use_cache=False)
            
            # Calculate change
            change = current.composite_score - previous.composite_score
            change_pct = abs(change) * 100
            
            if abs(change) < change_threshold:
                continue
            
            # Determine alert type
            if abs(current.composite_score) >= 0.8:
                alert_type = "extreme"
                message = f"{symbol} sentiment at extreme level: {current.level.value}"
            elif change * previous.composite_score < 0:
                alert_type = "reversal"
                message = f"{symbol} sentiment reversed from {previous.level.value} to {current.level.value}"
            else:
                alert_type = "spike"
                direction = "up" if change > 0 else "down"
                message = f"{symbol} sentiment {direction} {change_pct:.0f}%"
            
            alerts.append(SentimentAlert(
                symbol=symbol,
                alert_type=alert_type,
                previous_score=previous.composite_score,
                current_score=current.composite_score,
                change_pct=change_pct,
                message=message,
            ))
        
        return alerts
    
    def _score_to_level(self, score: float) -> SentimentLevel:
        """Convert numeric score to sentiment level."""
        if score <= self.THRESHOLDS["very_bearish"]:
            return SentimentLevel.VERY_BEARISH
        elif score <= self.THRESHOLDS["bearish"]:
            return SentimentLevel.BEARISH
        elif score <= self.THRESHOLDS["neutral"]:
            return SentimentLevel.NEUTRAL
        elif score <= self.THRESHOLDS["bullish"]:
            return SentimentLevel.BULLISH
        else:
            return SentimentLevel.VERY_BULLISH
    
    async def _fetch_stocktwits(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch sentiment from StockTwits API."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json",
                    headers={"User-Agent": "AxiomFolio/1.0"},
                )
                
                if resp.status_code != 200:
                    return None
                
                data = resp.json()
                messages = data.get("messages", [])
                
                if not messages:
                    return None
                
                # Count sentiment
                bullish = 0
                bearish = 0
                
                for msg in messages:
                    sentiment = msg.get("entities", {}).get("sentiment", {})
                    if sentiment.get("basic") == "Bullish":
                        bullish += 1
                    elif sentiment.get("basic") == "Bearish":
                        bearish += 1
                
                total = bullish + bearish
                if total == 0:
                    return None
                
                # Score: -1 to 1
                score = (bullish - bearish) / total
                
                return {
                    "score": score,
                    "mentions": len(messages),
                    "bullish": bullish,
                    "bearish": bearish,
                }
                
        except Exception as e:
            logger.debug("StockTwits API error for %s: %s", symbol, e)
            return None
    
    async def _fetch_finnhub(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch company news sentiment from Finnhub (``/news-sentiment``, not company-news)."""
        api_key = getattr(settings, "FINNHUB_API_KEY", None)
        if not api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://finnhub.io/api/v1/news-sentiment",
                    params={"symbol": symbol, "token": api_key},
                )

                if resp.status_code != 200:
                    return None

                data = resp.json()
                if not isinstance(data, dict):
                    return None

                buzz = data.get("buzz") if isinstance(data.get("buzz"), dict) else {}
                articles = int(buzz.get("articlesInLastWeek") or 0)

                score: float
                raw = data.get("companyNewsScore")
                if raw is not None:
                    score = float(raw)
                else:
                    sent = data.get("sentiment")
                    if isinstance(sent, dict):
                        bull = float(sent.get("bullishPercent") or 0.0)
                        bear = float(sent.get("bearishPercent") or 0.0)
                        total = bull + bear
                        score = (bull - bear) / total if total > 0 else 0.0
                    else:
                        return None

                score = max(-1.0, min(1.0, score))

                if articles == 0 and raw is None:
                    # No buzz volume and no explicit score — treat as no signal
                    return None

                return {"score": score, "articles": articles}

        except Exception as e:
            logger.debug("Finnhub API error for %s: %s", symbol, e)
            return None


def get_sentiment_dict(score: SentimentScore) -> Dict[str, Any]:
    """Convert SentimentScore to dict for API response."""
    return {
        "symbol": score.symbol,
        "composite_score": score.composite_score,
        "level": score.level.value,
        "sources": score.sources,
        "mention_count": score.mention_count,
        "bullish_ratio": score.bullish_ratio,
        "confidence": score.confidence,
        "updated_at": score.updated_at.isoformat(),
    }


# Module singleton
sentiment_service = SentimentService()
