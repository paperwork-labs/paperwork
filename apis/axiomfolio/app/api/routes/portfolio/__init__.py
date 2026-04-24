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

from .categories import router as categories_router
from .core import router as core_router
from .dashboard import router as dashboard_router
from .dividends import router as dividends_router
from .income import router as income_router
from .live import router as live_router
from .options import router as options_router
from .options_tax import router as options_tax_router
from .orders import router as orders_router
from .statements import router as statements_router
from .stocks import router as stocks_router
from .tax_export import router as tax_export_router

__all__ = [
    "categories_router",
    "core_router",
    "dashboard_router",
    "dividends_router",
    "income_router",
    "live_router",
    "options_router",
    "options_tax_router",
    "orders_router",
    "statements_router",
    "stocks_router",
    "tax_export_router",
]
