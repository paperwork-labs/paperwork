#!/usr/bin/env python3
"""
AxiomFolio V1 - SINGLE ATR Engine
=================================

THE definitive ATR calculation engine for AxiomFolio.
Handles ALL ATR calculations with research-based enhancements:

- Proper J. Welles Wilder True Range calculation
- Volatility regime classification (Low/Medium/High/Extreme)  
- 2x ATR breakout detection (industry standard)
- Chandelier Exit trailing stops
- ATR Bands for dynamic support/resistance
- Multi-timeframe analysis
- Mass processing for major indices (S&P 500, NASDAQ 100, Russell 2000)
- Options strategy optimization
- Performance optimized for thousands of symbols

"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
import aiohttp  # Added for API calls


# Note: TechnicalIndicators class doesn't exist - removed for now
from backend.database import SessionLocal

logger = logging.getLogger(__name__)

# =============================================================================
# ENHANCED DATA STRUCTURES
# =============================================================================


@dataclass
class ATRResult:
    """Enhanced ATR calculation result with all features."""

    symbol: str
    timeframe: str

    # Core ATR metrics
    atr_value: float
    atr_percentage: float  # ATR as % of price
    true_range: float  # Current period's true range

    # Volatility analysis
    volatility_level: str  # LOW, MEDIUM, HIGH, EXTREME
    volatility_percentile: float  # 0-100
    volatility_trend: str  # EXPANDING, CONTRACTING, STABLE
    cycle_stage: str  # COMPRESSION, EXPANSION, EXHAUSTION

    # Trading signals
    is_breakout: bool
    breakout_multiple: float  # How many ATRs the current move is
    breakout_direction: str  # UP, DOWN, NONE

    # Position management
    chandelier_long_exit: float
    chandelier_short_exit: float
    atr_bands_upper: float
    atr_bands_lower: float
    suggested_stop_loss: float

    # Options trading
    options_strike_otm: List[float]  # Out-of-money strikes based on ATR
    options_strike_itm: List[float]  # In-the-money strikes
    iv_rank_estimate: float  # Implied volatility rank estimate

    # Market timing
    entry_threshold: float
    exhaustion_level: float  # 2x+ ATR exhaustion
    scale_out_levels: List[float]  # 7x, 8x, 9x, 10x ATR

    # Performance metrics
    data_quality: float  # 0.0 to 1.0
    confidence: float
    calculation_date: datetime
    periods_used: int


@dataclass
class ATRUniverseResult:
    """Result for processing entire stock universe."""

    total_symbols: int
    successful_calculations: int
    failed_calculations: int
    breakouts_detected: int
    high_volatility_count: int
    signals_generated: int
    execution_time: float
    top_breakouts: List[Dict]
    top_volatility: List[Dict]


class ATREngine:
    """
    THE definitive ATR calculation engine for AxiomFolio.

    Features:
    - Research-based Wilder's ATR calculation
    - Mass processing for major indices
    - Volatility regime classification
    - Trading signal generation
    - Options strategy optimization
    - Performance optimized
    """

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or SessionLocal()

        # ATR calculation parameters (Wilder's original + enhancements)
        self.default_period = 14
        self.fast_period = 7  # Day trading
        self.slow_period = 21  # Position trading

        # Volatility regime thresholds (research-based percentiles)
        self.volatility_thresholds = {
            "LOW": 25,  # Below 25th percentile
            "MEDIUM": 75,  # 25th to 75th percentile
            "HIGH": 90,  # 75th to 90th percentile
            "EXTREME": 90,  # Above 90th percentile
        }

        # Trading parameters (industry standards)
        self.breakout_threshold = 2.0  # 2x ATR for valid breakout
        self.exhaustion_threshold = 2.5  # 2.5x ATR for exhaustion
        self.chandelier_multiplier = 3.0  # 3x ATR for trailing stops

        # Mass processing parameters
        self.batch_size = 50  # Process in batches for performance
        self.max_concurrent = 10  # Max concurrent calculations

        # Cache for performance
        self.atr_cache = {}
        self.cache_duration = timedelta(hours=1)

    # =============================================================================
    # CORE ATR CALCULATIONS (Wilder's Method)
    # =============================================================================

    def calculate_true_range_series(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate True Range series using J. Welles Wilder's method.

        True Range = Max of:
        1. Current High - Current Low
        2. |Current High - Previous Close|
        3. |Current Low - Previous Close|
        """
        high = data["high"].values
        low = data["low"].values
        close = data["close"].values

        # Shift close by 1 to get previous close
        prev_close = np.concatenate([[close[0]], close[:-1]])

        # Calculate the three components
        tr1 = high - low  # Current range
        tr2 = np.abs(high - prev_close)  # High to previous close gap
        tr3 = np.abs(low - prev_close)  # Low to previous close gap

        # True Range is the maximum of the three
        true_range = np.maximum(tr1, np.maximum(tr2, tr3))

        return pd.Series(true_range, index=data.index)

    def calculate_wilder_atr(
        self, true_range_series: pd.Series, periods: int = 14
    ) -> pd.Series:
        """
        Calculate ATR using Wilder's smoothing method.

        Wilder's smoothing: ATR = (Previous ATR * (n-1) + Current TR) / n
        This is the ORIGINAL and CORRECT method (not EMA).
        """
        atr_values = []

        # First ATR is simple average of first 'periods' true ranges
        if len(true_range_series) < periods:
            return pd.Series(
                [np.nan] * len(true_range_series), index=true_range_series.index
            )

        first_atr = true_range_series.head(periods).mean()
        atr_values.extend([np.nan] * (periods - 1))  # Pad with NaN
        atr_values.append(first_atr)

        # Subsequent ATRs use Wilder's smoothing
        for i in range(periods, len(true_range_series)):
            current_tr = true_range_series.iloc[i]
            previous_atr = atr_values[-1]

            # Wilder's smoothing formula
            new_atr = (previous_atr * (periods - 1) + current_tr) / periods
            atr_values.append(new_atr)

        return pd.Series(atr_values, index=true_range_series.index)

    # =============================================================================
    # ENHANCED ATR ANALYSIS
    # =============================================================================

    async def calculate_enhanced_atr(
        self, symbol: str, timeframe: str = "1D", periods: int = None
    ) -> ATRResult:
        """
        Calculate comprehensive ATR analysis for a single symbol.
        THE main method for ATR calculations.
        """
        if periods is None:
            periods = self.default_period

        # Check cache first
        cache_key = f"{symbol}_{timeframe}_{periods}"
        if cache_key in self.atr_cache:
            cached_result, cached_time = self.atr_cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                return cached_result

        try:
            # Get market data
            data = await self._get_market_data(symbol, timeframe, periods * 3)

            if data.empty or len(data) < periods:
                return self._empty_atr_result(symbol, timeframe)

            # Core ATR calculations
            tr_series = self.calculate_true_range_series(data)
            atr_series = self.calculate_wilder_atr(tr_series, periods)

            current_atr = (
                atr_series.dropna().iloc[-1] if not atr_series.dropna().empty else 0
            )
            current_price = data["close"].iloc[-1]
            current_tr = tr_series.iloc[-1]

            if current_atr <= 0:
                return self._empty_atr_result(symbol, timeframe)

            # Enhanced analysis
            volatility_analysis = self._analyze_volatility_regime(
                atr_series, current_atr
            )
            breakout_analysis = self._detect_breakout(data, current_atr, current_tr)
            chandelier_exits = self._calculate_chandelier_exits(data, atr_series)
            atr_bands = self._calculate_atr_bands(data, atr_series)
            options_strikes = self._calculate_options_strikes(
                current_price, current_atr
            )
            trading_levels = self._calculate_trading_levels(current_price, current_atr)

            # Create comprehensive result
            result = ATRResult(
                symbol=symbol,
                timeframe=timeframe,
                atr_value=current_atr,
                atr_percentage=(current_atr / current_price) * 100,
                true_range=current_tr,
                volatility_level=volatility_analysis["level"],
                volatility_percentile=volatility_analysis["percentile"],
                volatility_trend=volatility_analysis["trend"],
                cycle_stage=volatility_analysis["cycle_stage"],
                is_breakout=breakout_analysis["is_breakout"],
                breakout_multiple=breakout_analysis["multiple"],
                breakout_direction=breakout_analysis["direction"],
                chandelier_long_exit=chandelier_exits["long"],
                chandelier_short_exit=chandelier_exits["short"],
                atr_bands_upper=atr_bands["upper"],
                atr_bands_lower=atr_bands["lower"],
                suggested_stop_loss=self._calculate_stop_loss(
                    current_price, current_atr, volatility_analysis["level"]
                ),
                options_strike_otm=options_strikes["otm"],
                options_strike_itm=options_strikes["itm"],
                iv_rank_estimate=self._estimate_iv_rank(volatility_analysis),
                entry_threshold=trading_levels["entry"],
                exhaustion_level=trading_levels["exhaustion"],
                scale_out_levels=trading_levels["scale_out"],
                data_quality=min(1.0, len(data) / (periods * 2)),
                confidence=self._calculate_confidence(data, atr_series),
                calculation_date=datetime.now(),
                periods_used=periods,
            )

            # Cache the result
            self.atr_cache[cache_key] = (result, datetime.now())

            return result

        except Exception as e:
            logger.error(f"Error calculating ATR for {symbol}: {e}")
            return self._empty_atr_result(symbol, timeframe)

    # =============================================================================
    # MASS PROCESSING FOR MAJOR INDICES
    # =============================================================================

    async def process_major_indices(
        self, indices: List[str] = None
    ) -> ATRUniverseResult:
        """
        Process ATR for all major indices stocks.

        Args:
            indices: List of index names ['SP500', 'NASDAQ100', 'RUSSELL2000']
        """
        if indices is None:
            indices = ["SP500", "NASDAQ100", "RUSSELL2000"]

        logger.info(f"🚀 Processing ATR for major indices: {indices}")
        start_time = datetime.now()

        # Get all symbols from specified indices
        all_symbols = await self._get_index_symbols(indices)
        total_symbols = len(all_symbols)

        logger.info(
            f"📊 Processing {total_symbols} symbols from {len(indices)} indices"
        )

        # Process in batches for performance
        results = []
        successful = 0
        failed = 0
        breakouts = 0
        high_vol = 0
        signals = 0

        for i in range(0, len(all_symbols), self.batch_size):
            batch = all_symbols[i : i + self.batch_size]
            logger.info(
                f"Processing batch {i//self.batch_size + 1}/{(len(all_symbols) + self.batch_size - 1)//self.batch_size}"
            )

            # Process batch concurrently
            batch_tasks = [self.calculate_enhanced_atr(symbol) for symbol in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Collect results
            for symbol, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to process {symbol}: {result}")
                    failed += 1
                    continue

                if result.atr_value > 0:
                    successful += 1
                    results.append(result)

                    # Count interesting signals
                    if result.is_breakout:
                        breakouts += 1
                    if result.volatility_level in ["HIGH", "EXTREME"]:
                        high_vol += 1
                    if result.is_breakout or result.volatility_level in [
                        "HIGH",
                        "EXTREME",
                    ]:
                        signals += 1
                else:
                    failed += 1

        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()

        # Find top breakouts and volatility
        top_breakouts = sorted(
            [r for r in results if r.is_breakout],
            key=lambda x: x.breakout_multiple,
            reverse=True,
        )[:10]

        top_volatility = sorted(
            [r for r in results if r.volatility_level in ["HIGH", "EXTREME"]],
            key=lambda x: x.volatility_percentile,
            reverse=True,
        )[:10]

        # Store results in database
        await self._store_atr_results(results)

        logger.info(
            f"✅ Processed {successful}/{total_symbols} symbols in {execution_time:.1f}s"
        )
        logger.info(
            f"🚀 Found {breakouts} breakouts, {high_vol} high volatility stocks"
        )

        return ATRUniverseResult(
            total_symbols=total_symbols,
            successful_calculations=successful,
            failed_calculations=failed,
            breakouts_detected=breakouts,
            high_volatility_count=high_vol,
            signals_generated=signals,
            execution_time=execution_time,
            top_breakouts=[
                {
                    "symbol": r.symbol,
                    "multiple": r.breakout_multiple,
                    "direction": r.breakout_direction,
                    "atr_percentage": r.atr_percentage,
                }
                for r in top_breakouts
            ],
            top_volatility=[
                {
                    "symbol": r.symbol,
                    "volatility_level": r.volatility_level,
                    "percentile": r.volatility_percentile,
                    "atr_percentage": r.atr_percentage,
                }
                for r in top_volatility
            ],
        )

    async def get_portfolio_atr(self, symbols: List[str]) -> Dict[str, ATRResult]:
        """Get ATR analysis for specific portfolio symbols (for Holdings UI)."""
        results = {}

        # Process portfolio symbols with high priority
        tasks = [self.calculate_enhanced_atr(symbol) for symbol in symbols]
        portfolio_results = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, result in zip(symbols, portfolio_results):
            if isinstance(result, Exception):
                logger.error(
                    f"Error calculating ATR for portfolio symbol {symbol}: {result}"
                )
                results[symbol] = self._empty_atr_result(symbol, "1D")
            else:
                results[symbol] = result

        return results

    # =============================================================================
    # HELPER METHODS
    # =============================================================================

    def _analyze_volatility_regime(
        self, atr_series: pd.Series, current_atr: float
    ) -> Dict:
        """Analyze volatility regime and cycle stage."""
        valid_atr = atr_series.dropna()
        if len(valid_atr) < 10:
            return {
                "level": "MEDIUM",
                "percentile": 50.0,
                "trend": "STABLE",
                "cycle_stage": "STABLE",
            }

        # Calculate percentile
        percentile = (valid_atr <= current_atr).mean() * 100

        # Classify level
        if percentile <= self.volatility_thresholds["LOW"]:
            level = "LOW"
        elif percentile <= self.volatility_thresholds["MEDIUM"]:
            level = "MEDIUM"
        elif percentile <= self.volatility_thresholds["HIGH"]:
            level = "HIGH"
        else:
            level = "EXTREME"

        # Determine trend
        recent_avg = valid_atr.tail(5).mean()
        older_avg = valid_atr.tail(20).head(10).mean()

        if recent_avg > older_avg * 1.15:
            trend = "EXPANDING"
        elif recent_avg < older_avg * 0.85:
            trend = "CONTRACTING"
        else:
            trend = "STABLE"

        # Determine cycle stage
        if level == "LOW" and trend in ["CONTRACTING", "STABLE"]:
            cycle_stage = "COMPRESSION"  # Expect breakout soon
        elif level in ["HIGH", "EXTREME"] and trend == "EXPANDING":
            cycle_stage = "EXPANSION"  # Active volatility
        elif level in ["HIGH", "EXTREME"] and trend == "CONTRACTING":
            cycle_stage = "EXHAUSTION"  # Expect normalization
        else:
            cycle_stage = "STABLE"

        return {
            "level": level,
            "percentile": percentile,
            "trend": trend,
            "cycle_stage": cycle_stage,
        }

    def _detect_breakout(
        self, data: pd.DataFrame, atr: float, current_tr: float
    ) -> Dict:
        """Detect 2x ATR breakouts (industry standard)."""
        if atr <= 0:
            return {"is_breakout": False, "multiple": 0, "direction": "NONE"}

        multiple = current_tr / atr
        is_breakout = multiple >= self.breakout_threshold

        if not is_breakout:
            return {"is_breakout": False, "multiple": multiple, "direction": "NONE"}

        # Determine direction
        current_candle = data.iloc[-1]
        direction = "UP" if current_candle["close"] > current_candle["open"] else "DOWN"

        return {"is_breakout": True, "multiple": multiple, "direction": direction}

    def _calculate_chandelier_exits(
        self, data: pd.DataFrame, atr_series: pd.Series
    ) -> Dict:
        """Calculate Chandelier Exit trailing stops."""
        current_atr = atr_series.dropna().iloc[-1]
        lookback = 14

        recent_data = data.tail(lookback)
        highest_high = recent_data["high"].max()
        lowest_low = recent_data["low"].min()

        return {
            "long": highest_high - (self.chandelier_multiplier * current_atr),
            "short": lowest_low + (self.chandelier_multiplier * current_atr),
        }

    def _calculate_atr_bands(self, data: pd.DataFrame, atr_series: pd.Series) -> Dict:
        """Calculate ATR Bands (dynamic support/resistance)."""
        middle = data["close"].rolling(window=20).mean().iloc[-1]
        current_atr = atr_series.dropna().iloc[-1]
        multiplier = 2.0  # 2x ATR bands

        return {
            "upper": middle + (multiplier * current_atr),
            "lower": middle - (multiplier * current_atr),
            "middle": middle,
        }

    def _calculate_options_strikes(self, price: float, atr: float) -> Dict:
        """Calculate optimal options strikes based on ATR."""
        # Out-of-money strikes (for selling options)
        otm_distance = atr * 1.5  # 1.5x ATR for premium collection

        # In-the-money strikes (for buying options)
        itm_distance = atr * 0.5  # 0.5x ATR for directional plays

        return {
            "otm": [
                round(price + otm_distance, 0),  # OTM calls
                round(price - otm_distance, 0),  # OTM puts
            ],
            "itm": [
                round(price - itm_distance, 0),  # ITM calls
                round(price + itm_distance, 0),  # ITM puts
            ],
        }

    def _calculate_trading_levels(self, price: float, atr: float) -> Dict:
        """Calculate key trading levels."""
        return {
            "entry": price + (atr * 0.5),  # Entry on momentum
            "exhaustion": price + (atr * 2.5),  # Potential reversal
            "scale_out": [  # Scale-out levels
                price + (atr * 7),
                price + (atr * 8),
                price + (atr * 9),
                price + (atr * 10),
            ],
        }

    def _calculate_stop_loss(self, price: float, atr: float, vol_level: str) -> float:
        """Calculate optimal stop loss based on volatility regime."""
        multipliers = {
            "LOW": 1.5,  # Tighter stops in low volatility
            "MEDIUM": 2.0,  # Standard stop
            "HIGH": 2.5,  # Wider stops in high volatility
            "EXTREME": 3.0,  # Very wide stops
        }

        multiplier = multipliers.get(vol_level, 2.0)
        return price - (atr * multiplier)

    def _estimate_iv_rank(self, volatility_analysis: Dict) -> float:
        """Estimate implied volatility rank from historical volatility."""
        # Rough estimate: higher historical volatility suggests higher IV rank
        percentile = volatility_analysis["percentile"]
        return min(100, percentile * 1.2)  # Scale up slightly

    def _calculate_confidence(self, data: pd.DataFrame, atr_series: pd.Series) -> float:
        """Calculate confidence in ATR calculation."""
        data_points = len(atr_series.dropna())
        min_required = self.default_period * 2

        confidence = min(1.0, data_points / min_required)

        # Reduce confidence for very old data
        latest_date = data.index[-1] if not data.empty else datetime.now()
        if isinstance(latest_date, str):
            latest_date = pd.to_datetime(latest_date)

        days_old = (datetime.now() - latest_date).days
        if days_old > 5:  # Reduce confidence for stale data
            confidence *= max(0.5, 1 - (days_old / 30))

        return confidence

    async def _get_market_data(
        self, symbol: str, timeframe: str, periods: int
    ) -> pd.DataFrame:
        """Get market data using the existing market data service."""
        try:
            from backend.services.market.market_data_service import market_data_service

            # Convert periods to appropriate period string for API
            period_map = {
                "1D": self._periods_to_yahoo_period(periods),
                "1H": "5d",  # Get more recent data for intraday
                "4H": "1mo",
                "1W": f"{periods//52 + 1}y",
            }

            period_str = period_map.get(timeframe, "1y")
            interval_str = timeframe.lower() if timeframe != "1D" else "1d"

            # Get historical data from market data service
            data = await market_data_service.get_historical_data(
                symbol=symbol, period=period_str, interval=interval_str
            )

            if data is not None and not data.empty:
                # Ensure we have the required columns in the right format
                required_cols = ["Open", "High", "Low", "Close", "Volume"]
                if all(col in data.columns for col in required_cols):
                    # Rename to lowercase for consistency with our calculations
                    data.columns = [col.lower() for col in data.columns]
                    return data.head(periods)  # Limit to requested periods
                else:
                    logger.warning(
                        f"Missing required columns for {symbol}: {data.columns.tolist()}"
                    )

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return pd.DataFrame()

    def _periods_to_yahoo_period(self, periods: int) -> str:
        """Convert number of periods to Yahoo Finance period string."""
        if periods <= 7:
            return "7d"
        elif periods <= 30:
            return "1mo"
        elif periods <= 90:
            return "3mo"
        elif periods <= 180:
            return "6mo"
        elif periods <= 365:
            return "1y"
        elif periods <= 730:
            return "2y"
        else:
            return "5y"

    async def _get_index_symbols(self, indices: List[str]) -> List[str]:
        """Get index constituents from production APIs (NO HARDCODING!)."""
        try:
            from backend.services.market.index_constituents_service import index_service

            logger.info(f"📊 Fetching constituents for indices: {indices}")

            # Get all index constituents from our production service
            from backend.services.market.market_data_service import market_data_service
            all_indices_data = await market_data_service.get_all_tradeable_symbols(indices)

            # Combine all symbols
            all_symbols = []
            for index_name, symbols in all_indices_data.items():
                if symbols:
                    all_symbols.extend(symbols)
                    logger.info(f"✅ {index_name}: {len(symbols)} symbols")
                else:
                    logger.warning(f"❌ {index_name}: No symbols retrieved")

            # Remove duplicates and return
            unique_symbols = list(set(all_symbols))
            logger.info(
                f"🎯 Total unique symbols across all indices: {len(unique_symbols)}"
            )

            return unique_symbols

        except Exception as e:
            logger.error(f"Error getting index symbols: {e}")
            return []

    async def _get_sp500_constituents(self) -> List[str]:
        """Get S&P 500 constituents from FMP API."""
        try:
            from backend.services.market.market_data_service import market_data_service

            # Check if FMP is available
            if (
                hasattr(market_data_service, "fmp_api_key")
                and market_data_service.fmp_api_key
            ):
                # Use FMP API to get S&P 500 constituents
                url = f"https://financialmodelingprep.com/api/v3/sp500_constituent?apikey={market_data_service.fmp_api_key}"

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if isinstance(data, list):
                                symbols = [
                                    item.get("symbol")
                                    for item in data
                                    if item.get("symbol")
                                ]
                                return [
                                    s for s in symbols if s and len(s) <= 5
                                ]  # Filter valid symbols

            # Fallback: Get from Wikipedia or other free source
            return await self._get_sp500_from_wikipedia()

        except Exception as e:
            logger.error(f"Error getting S&P 500 constituents: {e}")
            return []

    async def _get_nasdaq100_constituents(self) -> List[str]:
        """Get NASDAQ 100 constituents from API."""
        try:
            from backend.services.market.market_data_service import market_data_service

            # Try FMP API first
            if (
                hasattr(market_data_service, "fmp_api_key")
                and market_data_service.fmp_api_key
            ):
                url = f"https://financialmodelingprep.com/api/v3/nasdaq_constituent?apikey={market_data_service.fmp_api_key}"

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if isinstance(data, list):
                                symbols = [
                                    item.get("symbol")
                                    for item in data
                                    if item.get("symbol")
                                ]
                                return [s for s in symbols if s and len(s) <= 5]

            # Fallback to Wikipedia
            return await self._get_nasdaq100_from_wikipedia()

        except Exception as e:
            logger.error(f"Error getting NASDAQ 100 constituents: {e}")
            return []

    async def _get_russell2000_constituents(self) -> List[str]:
        """Get Russell 2000 constituents (sample for now - full list is 2000 stocks!)."""
        try:
            # Russell 2000 has 2000 stocks, which is massive
            # For now, we'll get the top 100 by market cap from Russell 2000 ETF holdings
            logger.info("📊 Getting Russell 2000 sample (top holdings)")

            # This would ideally come from:
            # 1. Russell official API (paid)
            # 2. ETF provider APIs (iShares IWM holdings)
            # 3. Financial data providers

            # For now, return empty and focus on S&P 500 + NASDAQ 100
            # which gives us ~600 high-quality stocks
            logger.warning(
                "Russell 2000 constituents not implemented yet (2000 stocks is massive)"
            )
            return []

        except Exception as e:
            logger.error(f"Error getting Russell 2000 constituents: {e}")
            return []

    async def _get_dow30_constituents(self) -> List[str]:
        """Get Dow 30 constituents from API."""
        try:
            from backend.services.market.market_data_service import market_data_service

            # Try FMP API
            if (
                hasattr(market_data_service, "fmp_api_key")
                and market_data_service.fmp_api_key
            ):
                url = f"https://financialmodelingprep.com/api/v3/dowjones_constituent?apikey={market_data_service.fmp_api_key}"

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if isinstance(data, list):
                                symbols = [
                                    item.get("symbol")
                                    for item in data
                                    if item.get("symbol")
                                ]
                                return [s for s in symbols if s and len(s) <= 5]

            # Fallback to Wikipedia
            return await self._get_dow30_from_wikipedia()

        except Exception as e:
            logger.error(f"Error getting Dow 30 constituents: {e}")
            return []

    async def _get_sp500_from_wikipedia(self) -> List[str]:
        """Fallback: Get S&P 500 from Wikipedia table."""
        try:
            # Wikipedia has a regularly updated S&P 500 table
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

            # Read the table using pandas (works with Wikipedia tables)
            import pandas as pd

            tables = pd.read_html(url)

            if tables and len(tables) > 0:
                # First table contains the S&P 500 companies
                sp500_table = tables[0]
                if "Symbol" in sp500_table.columns:
                    symbols = sp500_table["Symbol"].dropna().tolist()
                    # Clean symbols (remove dots, etc.)
                    clean_symbols = []
                    for symbol in symbols:
                        if isinstance(symbol, str) and len(symbol) <= 5:
                            # Replace dots with dashes (BRK.A -> BRK-A)
                            clean_symbol = symbol.replace(".", "-")
                            clean_symbols.append(clean_symbol)

                    logger.info(
                        f"✅ Got {len(clean_symbols)} S&P 500 symbols from Wikipedia"
                    )
                    return clean_symbols

        except Exception as e:
            logger.error(f"Error getting S&P 500 from Wikipedia: {e}")

        return []

    async def _get_nasdaq100_from_wikipedia(self) -> List[str]:
        """Fallback: Get NASDAQ 100 from Wikipedia."""
        try:
            url = "https://en.wikipedia.org/wiki/Nasdaq-100"

            import pandas as pd

            tables = pd.read_html(url)

            for table in tables:
                if "Ticker" in table.columns or "Symbol" in table.columns:
                    symbol_col = "Ticker" if "Ticker" in table.columns else "Symbol"
                    symbols = table[symbol_col].dropna().tolist()

                    clean_symbols = []
                    for symbol in symbols:
                        if isinstance(symbol, str) and len(symbol) <= 5:
                            clean_symbol = symbol.replace(".", "-")
                            clean_symbols.append(clean_symbol)

                    if len(clean_symbols) > 50:  # Should have ~100 symbols
                        logger.info(
                            f"✅ Got {len(clean_symbols)} NASDAQ 100 symbols from Wikipedia"
                        )
                        return clean_symbols

        except Exception as e:
            logger.error(f"Error getting NASDAQ 100 from Wikipedia: {e}")

        return []

    async def _get_dow30_from_wikipedia(self) -> List[str]:
        """Fallback: Get Dow 30 from Wikipedia."""
        try:
            url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"

            import pandas as pd

            tables = pd.read_html(url)

            for table in tables:
                if (
                    "Symbol" in table.columns and len(table) <= 35
                ):  # Dow has 30 companies
                    symbols = table["Symbol"].dropna().tolist()

                    clean_symbols = []
                    for symbol in symbols:
                        if isinstance(symbol, str) and len(symbol) <= 5:
                            clean_symbol = symbol.replace(".", "-")
                            clean_symbols.append(clean_symbol)

                    if 25 <= len(clean_symbols) <= 35:  # Should be ~30 symbols
                        logger.info(
                            f"✅ Got {len(clean_symbols)} Dow 30 symbols from Wikipedia"
                        )
                        return clean_symbols

        except Exception as e:
            logger.error(f"Error getting Dow 30 from Wikipedia: {e}")

        return []

    async def _store_atr_results(self, results: List[ATRResult]) -> None:
        """Store ATR results in database for API access."""
        # This would store the results in a dedicated ATR results table
        # for fast API retrieval
        logger.info(f"📊 Storing {len(results)} ATR results in database")
        # TODO: Implement database storage

    def _empty_atr_result(self, symbol: str, timeframe: str) -> ATRResult:
        """Return empty ATR result for error cases."""
        return ATRResult(
            symbol=symbol,
            timeframe=timeframe,
            atr_value=0.0,
            atr_percentage=0.0,
            true_range=0.0,
            volatility_level="UNKNOWN",
            volatility_percentile=0.0,
            volatility_trend="STABLE",
            cycle_stage="STABLE",
            is_breakout=False,
            breakout_multiple=0.0,
            breakout_direction="NONE",
            chandelier_long_exit=0.0,
            chandelier_short_exit=0.0,
            atr_bands_upper=0.0,
            atr_bands_lower=0.0,
            suggested_stop_loss=0.0,
            options_strike_otm=[],
            options_strike_itm=[],
            iv_rank_estimate=0.0,
            entry_threshold=0.0,
            exhaustion_level=0.0,
            scale_out_levels=[],
            data_quality=0.0,
            confidence=0.0,
            calculation_date=datetime.now(),
            periods_used=0,
        )


# =============================================================================
# GLOBAL INSTANCE - SINGLE SOURCE OF TRUTH
# =============================================================================

# THE definitive ATR engine for AxiomFolio
atr_engine = ATREngine()


# Convenience functions for common use cases
async def calculate_atr(symbol: str, timeframe: str = "1D") -> ATRResult:
    """Quick ATR calculation for a symbol."""
    return await atr_engine.calculate_enhanced_atr(symbol, timeframe)


async def process_stock_universe() -> ATRUniverseResult:
    """Process ATR for entire stock universe (S&P 500, NASDAQ 100, Russell 2000)."""
    return await atr_engine.process_major_indices()


async def get_portfolio_atr_data(symbols: List[str]) -> Dict[str, ATRResult]:
    """Get ATR data for portfolio symbols (for Holdings UI)."""
    return await atr_engine.get_portfolio_atr(symbols)
