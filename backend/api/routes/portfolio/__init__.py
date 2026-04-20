"""
Portfolio Routes Package
========================

Handles all portfolio-related endpoints:
- Core portfolio operations
- Stocks/holdings
- Categories
- Options
- Orders
- Dividends
- Statements
- Live data
"""

from .core import router as core_router
from .stocks import router as stocks_router
from .categories import router as categories_router
from .options import router as options_router
from .orders import router as orders_router
from .dividends import router as dividends_router
from .income import router as income_router
from .statements import router as statements_router
from .live import router as live_router
from .dashboard import router as dashboard_router
from .tax_export import router as tax_export_router

__all__ = [
    "core_router",
    "stocks_router",
    "categories_router",
    "options_router",
    "orders_router",
    "dividends_router",
    "income_router",
    "statements_router",
    "live_router",
    "dashboard_router",
    "tax_export_router",
]
