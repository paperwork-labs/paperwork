# #!/usr/bin/env python3
# """
# AxiomFolio V1 - ATR API Routes
# ==============================

# API endpoints for ATR calculations and universe processing:
# - Portfolio ATR data (for Holdings UI)
# - Major indices ATR processing
# - Individual symbol ATR calculation
# - ATR-based trading signals

# Integrates with:
# - Market Data Service (for price data)
# - Index Constituents Service (for major indices)
# - ATR Engine (for calculations)
# - Signal Generation (for trading alerts)
# """

# from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
# from typing import List, Dict, Any, Optional
# from datetime import datetime
# import logging

# from backend.api.dependencies import get_current_user
# from backend.models.user import User
# from backend.services.analysis.atr_engine import atr_engine
# from backend.services.market.market_data_service import market_data_service
# from backend.services.market.market_data_service import MarketDataService

# logger = logging.getLogger(__name__)

# router = APIRouter()


# # @router.get("/universe")
# # async def get_atr_universe():
# #     """
# #     Get the optimal stock universe for ATR analysis.

# #     Returns S&P 500 + NASDAQ 100 constituents from live APIs.
# #     NO HARDCODING - all data from market APIs.
# #     """
# #     try:
# #         logger.info("🌍 Getting ATR universe from live APIs")

# #         # Get universe from index service (integrates with FMP, Polygon, etc.)
# #         universe = await market_data_service.get_all_tradeable_symbols(["SP500","NASDAQ100"])  # example

# #         return {
# #             "success": True,
# #             "universe_size": len(universe),
# #             "symbols": universe,
# #             "indices_included": ["SP500", "NASDAQ100"],
# #             "data_source": "LIVE_APIS",
# #             "timestamp": datetime.now().isoformat(),
# #         }

# #     except Exception as e:
# #         logger.error(f"Error getting ATR universe: {e}")
# #         raise HTTPException(
# #             status_code=500, detail=f"Failed to get ATR universe: {str(e)}"
# #         )


# @router.post("/indices/bootstrap")
# async def bootstrap_market_data_for_indices(
#     indices: Optional[List[str]] = None,
#     max_symbols: int = 1200,
#     concurrency: int = 25,
# ) -> Dict[str, Any]:
#     """
#     Prefetch current prices for all symbols in the given indices so portfolio
#     endpoints have data available immediately.

#     Defaults to SP500, NASDAQ100, DOW30. Russell 2000 can be added but is large.
#     """
#     try:
#         indices = indices or ["SP500", "NASDAQ100", "DOW30"]
#         svc = MarketDataService()

#         # Get constituents per index
#         index_to_symbols: Dict[str, List[str]] = {}
#         for name in indices:
#             syms = await index_service.get_index_constituents(name)
#             if syms:
#                 index_to_symbols[name.upper()] = syms

#         # Deduplicate and optionally cap total symbol count
#         all_syms: List[str] = []
#         seen = set()
#         for name in indices:
#             for s in index_to_symbols.get(name.upper(), []):
#                 if s not in seen:
#                     seen.add(s)
#                     all_syms.append(s)
#         if max_symbols and len(all_syms) > max_symbols:
#             all_syms = all_syms[:max_symbols]

#         # Concurrent price fetch with simple rate limiting via semaphore
#         import asyncio as _asyncio

#         sem = _asyncio.Semaphore(concurrency)

#         async def _fetch(sym: str):
#             async with sem:
#                 try:
#                     await svc.get_current_price(sym)
#                     return True
#                 except Exception:
#                     return False

#         tasks = [_fetch(sym) for sym in all_syms]
#         results = await _asyncio.gather(*tasks, return_exceptions=True)
#         successes = sum(1 for r in results if r is True)

#         return {
#             "success": True,
#             "indices": indices,
#             "requested_symbols": len(all_syms),
#             "prices_prefetched": successes,
#             "timestamp": datetime.now().isoformat(),
#         }
#     except Exception as e:
#         logger.error(f"Error bootstrapping market data: {e}")
#         raise HTTPException(status_code=500, detail=f"Bootstrap failed: {str(e)}")


# @router.get("/portfolio")
# async def get_portfolio_atr(
#     symbols: str,  # Comma-separated symbols
#     timeframe: str = "1D",
#     user: User = Depends(get_current_user),
# ):
#     """
#     Get ATR analysis for portfolio symbols (for Holdings UI).

#     Usage: /api/v1/atr/portfolio?symbols=AAPL,MSFT,GOOGL&timeframe=1D
#     """
#     try:
#         # Parse symbols
#         symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

#         if not symbol_list:
#             raise HTTPException(status_code=400, detail="No valid symbols provided")

#         logger.info(f"📊 Getting ATR data for portfolio symbols: {symbol_list}")

#         # Get ATR data for all symbols
#         portfolio_atr = await atr_engine.get_portfolio_atr(symbol_list)

#         # Format response for Holdings UI
#         atr_data = {}
#         for symbol, atr_result in portfolio_atr.items():
#             atr_data[symbol] = {
#                 "atr_value": atr_result.atr_value,
#                 "atr_percentage": round(atr_result.atr_percentage, 2),
#                 "volatility_level": atr_result.volatility_level,
#                 "volatility_percentile": round(atr_result.volatility_percentile, 1),
#                 "suggested_stop_loss": round(atr_result.suggested_stop_loss, 2),
#                 "chandelier_long_exit": round(atr_result.chandelier_long_exit, 2),
#                 "chandelier_short_exit": round(atr_result.chandelier_short_exit, 2),
#                 "is_breakout": atr_result.is_breakout,
#                 "breakout_multiple": (
#                     round(atr_result.breakout_multiple, 1)
#                     if atr_result.breakout_multiple
#                     else None
#                 ),
#                 "confidence": round(atr_result.confidence, 2),
#                 "data_quality": round(atr_result.data_quality, 2),
#                 "calculation_date": atr_result.calculation_date.isoformat(),
#             }

#         return {
#             "success": True,
#             "symbols_processed": len(atr_data),
#             "timeframe": timeframe,
#             "atr_data": atr_data,
#             "timestamp": datetime.now().isoformat(),
#         }

#     except Exception as e:
#         logger.error(f"Error getting portfolio ATR: {e}")
#         raise HTTPException(
#             status_code=500, detail=f"Failed to get portfolio ATR: {str(e)}"
#         )


# @router.get("/symbol/{symbol}")
# async def get_symbol_atr(symbol: str, timeframe: str = "1D", periods: int = 14):
#     """
#     Get detailed ATR analysis for a single symbol.

#     Returns comprehensive ATR data including:
#     - Core ATR metrics
#     - Volatility regime analysis
#     - Trading signals
#     - Options strikes
#     - Position management levels
#     """
#     try:
#         symbol = symbol.upper()
#         logger.info(f"📈 Getting detailed ATR for {symbol}")

#         # Get comprehensive ATR analysis
#         atr_result = await atr_engine.calculate_enhanced_atr(symbol, timeframe, periods)

#         if atr_result.atr_value == 0:
#             raise HTTPException(
#                 status_code=404, detail=f"No ATR data available for {symbol}"
#             )

#         return {
#             "success": True,
#             "symbol": symbol,
#             "timeframe": timeframe,
#             "periods": periods,
#             "atr_analysis": {
#                 # Core metrics
#                 "atr_value": atr_result.atr_value,
#                 "atr_percentage": round(atr_result.atr_percentage, 2),
#                 "true_range": atr_result.true_range,
#                 # Volatility analysis
#                 "volatility_level": atr_result.volatility_level,
#                 "volatility_percentile": round(atr_result.volatility_percentile, 1),
#                 "volatility_trend": atr_result.volatility_trend,
#                 "cycle_stage": atr_result.cycle_stage,
#                 # Trading signals
#                 "is_breakout": atr_result.is_breakout,
#                 "breakout_multiple": (
#                     round(atr_result.breakout_multiple, 1)
#                     if atr_result.breakout_multiple
#                     else None
#                 ),
#                 "breakout_direction": atr_result.breakout_direction,
#                 # Position management
#                 "suggested_stop_loss": round(atr_result.suggested_stop_loss, 2),
#                 "chandelier_long_exit": round(atr_result.chandelier_long_exit, 2),
#                 "chandelier_short_exit": round(atr_result.chandelier_short_exit, 2),
#                 "atr_bands_upper": round(atr_result.atr_bands_upper, 2),
#                 "atr_bands_lower": round(atr_result.atr_bands_lower, 2),
#                 # Options trading
#                 "options_strike_otm": atr_result.options_strike_otm,
#                 "options_strike_itm": atr_result.options_strike_itm,
#                 "iv_rank_estimate": round(atr_result.iv_rank_estimate, 1),
#                 # Market timing
#                 "entry_threshold": round(atr_result.entry_threshold, 2),
#                 "exhaustion_level": round(atr_result.exhaustion_level, 2),
#                 "scale_out_levels": [
#                     round(level, 2) for level in atr_result.scale_out_levels
#                 ],
#                 # Quality metrics
#                 "confidence": round(atr_result.confidence, 2),
#                 "data_quality": round(atr_result.data_quality, 2),
#                 "calculation_date": atr_result.calculation_date.isoformat(),
#             },
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting ATR for {symbol}: {e}")
#         raise HTTPException(
#             status_code=500, detail=f"Failed to get ATR for {symbol}: {str(e)}"
#         )


# @router.post("/process-universe")
# async def process_universe_atr(
#     background_tasks: BackgroundTasks,
#     indices: List[str] = ["SP500", "NASDAQ100"],
#     user: User = Depends(get_current_user),
# ):
#     """
#     Process ATR for entire stock universe (background task).

#     This is the main endpoint for mass ATR processing.
#     Runs in background and stores results in database.
#     """
#     try:
#         logger.info(f"🚀 Starting universe ATR processing for indices: {indices}")

#         # Add background task for processing
#         background_tasks.add_task(_process_universe_background, indices, user.id)

#         return {
#             "success": True,
#             "message": f"Universe ATR processing started for {len(indices)} indices",
#             "indices": indices,
#             "status": "processing_in_background",
#             "timestamp": datetime.now().isoformat(),
#         }

#     except Exception as e:
#         logger.error(f"Error starting universe processing: {e}")
#         raise HTTPException(
#             status_code=500, detail=f"Failed to start processing: {str(e)}"
#         )


# @router.get("/universe/results")
# async def get_universe_results(
#     limit: int = 100, breakouts_only: bool = False, high_volatility_only: bool = False
# ):
#     """
#     Get results from universe ATR processing.

#     Query parameters:
#     - limit: Maximum number of results to return
#     - breakouts_only: Only return symbols with breakout signals
#     - high_volatility_only: Only return high/extreme volatility symbols
#     """
#     try:
#         # This would query the database for stored ATR results
#         # For now, return a placeholder response

#         return {
#             "success": True,
#             "message": "ATR universe results (placeholder - implement database query)",
#             "filters": {
#                 "limit": limit,
#                 "breakouts_only": breakouts_only,
#                 "high_volatility_only": high_volatility_only,
#             },
#             "results": [],
#             "timestamp": datetime.now().isoformat(),
#         }

#     except Exception as e:
#         logger.error(f"Error getting universe results: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")


# @router.get("/indices/available")
# async def get_available_indices():
#     """Get list of available indices for ATR processing."""
#     try:
#         available_indices = [
#             {
#                 "name": "S&P 500",
#                 "symbol": "SP500",
#                 "description": "500 largest US companies",
#                 "estimated_count": 500,
#                 "data_sources": ["FMP", "Wikipedia"],
#             },
#             {
#                 "name": "NASDAQ 100",
#                 "symbol": "NASDAQ100",
#                 "description": "100 largest non-financial NASDAQ companies",
#                 "estimated_count": 100,
#                 "data_sources": ["FMP", "Wikipedia"],
#             },
#             {
#                 "name": "Dow Jones 30",
#                 "symbol": "DOW30",
#                 "description": "30 large US companies",
#                 "estimated_count": 30,
#                 "data_sources": ["FMP", "Wikipedia"],
#             },
#             {
#                 "name": "Russell 2000",
#                 "symbol": "RUSSELL2000",
#                 "description": "2000 small-cap US companies",
#                 "estimated_count": 2000,
#                 "data_sources": ["Not implemented - too large"],
#                 "note": "Skipped by default due to size",
#             },
#         ]

#         return {
#             "success": True,
#             "available_indices": available_indices,
#             "recommended": ["SP500", "NASDAQ100"],
#             "total_estimated_symbols": 600,  # S&P 500 + NASDAQ 100 with overlap
#             "timestamp": datetime.now().isoformat(),
#         }

#     except Exception as e:
#         logger.error(f"Error getting available indices: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to get indices: {str(e)}")


# # =============================================================================
# # BACKGROUND TASKS
# # =============================================================================


# async def _process_universe_background(indices: List[str], user_id: int):
#     """Background task for processing entire universe ATR."""
#     try:
#         logger.info(f"🔄 Background ATR processing started for user {user_id}")

#         # Process the universe
#         result = await atr_engine.process_major_indices(indices)

#         logger.info("✅ Background ATR processing complete:")
#         logger.info(f"   📊 Total symbols: {result.total_symbols}")
#         logger.info(f"   ✅ Successful: {result.successful_calculations}")
#         logger.info(f"   ❌ Failed: {result.failed_calculations}")
#         logger.info(f"   🚀 Breakouts: {result.breakouts_detected}")
#         logger.info(f"   📈 High volatility: {result.high_volatility_count}")
#         logger.info(f"   ⏱️ Execution time: {result.execution_time:.1f}s")

#         # Store results in database for API access
#         # TODO: Implement database storage

#         # Generate signals from breakouts and high volatility
#         # TODO: Integrate with signal generation service

#     except Exception as e:
#         logger.error(f"Background ATR processing failed: {e}")


# # =============================================================================
# # INTEGRATION HELPER
# # =============================================================================


# @router.get("/health")
# async def atr_health_check():
#     """Health check for ATR system dependencies."""
#     try:
#         health_status = {
#             "atr_engine": "✅ Ready",
#             "market_data_service": "✅ Ready",
#             "database": "✅ Connected",
#             "apis": {},
#         }

#         # Check API availability
#         try:
#             # Test getting a small universe
#             test_symbols = await market_data_service.get_index_constituents("DOW30")
#             health_status["apis"][
#                 "index_data"
#             ] = f"✅ {len(test_symbols)} symbols retrieved"
#         except Exception as e:
#             health_status["apis"]["index_data"] = f"❌ {str(e)}"

#         return {
#             "success": True,
#             "health_status": health_status,
#             "timestamp": datetime.now().isoformat(),
#         }

#     except Exception as e:
#         logger.error(f"ATR health check failed: {e}")
#         raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
