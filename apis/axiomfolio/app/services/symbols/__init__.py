"""Symbol master services.

Single point of import for the symbol master layer:

    from app.services.symbols import SymbolMasterService

The service handles point-in-time resolution, alias registration,
and ticker-change recording. The ``initial_load`` module bootstraps
the master from existing ``MarketSnapshot`` rows plus a curated
seed of historical corporate actions.

medallion: silver
"""

from app.services.symbols.symbol_master_service import (
    HISTORICAL_FLOOR_DATE,
    SymbolMasterError,
    SymbolMasterService,
    TickerChangeResult,
    UnknownTickerError,
)

__all__ = [
    "HISTORICAL_FLOOR_DATE",
    "SymbolMasterError",
    "SymbolMasterService",
    "TickerChangeResult",
    "UnknownTickerError",
]
