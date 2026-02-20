"""
ATR calculator adapter for strategy/options use.
Delegates to atr_engine (single source of truth) and exposes a dict-based API
expected by strategy_manager and strategies routes.
"""

from backend.services.analysis.atr_engine import atr_engine, ATRResult
from typing import Any, Dict

__all__ = ["atr_calculator", "calculate_options_atr", "ATRResult"]


async def calculate_options_atr(symbol: str) -> Dict[str, Any]:
    """
    Return ATR data as a dict for options strategy configuration.
    Uses atr_engine.calculate_enhanced_atr and shapes the result.
    """
    result = await atr_engine.calculate_enhanced_atr(symbol)
    return {
        "symbol": result.symbol,
        "atr_value": result.atr_value,
        "atr_percentage": result.atr_percentage,
        "volatility_level": result.volatility_level,
        "volatility_percentile": result.volatility_percentile,
        "volatility_trend": result.volatility_trend,
        "options_strike_otm": result.options_strike_otm,
        "options_strike_itm": result.options_strike_itm,
        "suggested_stop_loss": result.suggested_stop_loss,
        "position_size_factor": 0.10,
        "suggested_strikes": result.options_strike_otm[:3] if result.options_strike_otm else [],
        "options_multiplier": 1.0,
    }


# Alias for drop-in replacement where code expects atr_calculator module with an object
class ATRCalculatorAdapter:
    """Adapter exposing atr_engine as atr_calculator-compatible interface."""

    calculate_options_atr = staticmethod(calculate_options_atr)


atr_calculator = ATRCalculatorAdapter()
