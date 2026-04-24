"""Corporate-action engine.

Public surface is grown incrementally as submodules land. Importers
should reference the concrete module path (e.g.
``backend.services.corporate_actions.adjusters``) so adding a new
submodule never breaks the package import for anyone.

medallion: silver
"""

from .adjusters import (
    AdjustmentResult,
    adjust_for_cash_dividend,
    adjust_for_merger_cash,
    adjust_for_merger_stock,
    adjust_for_reverse_split,
    adjust_for_split,
    adjust_for_stock_dividend,
    decimal_ratio,
)

__all__ = [
    "AdjustmentResult",
    "adjust_for_cash_dividend",
    "adjust_for_merger_cash",
    "adjust_for_merger_stock",
    "adjust_for_reverse_split",
    "adjust_for_split",
    "adjust_for_stock_dividend",
    "decimal_ratio",
]
