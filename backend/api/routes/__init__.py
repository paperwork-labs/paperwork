"""
AxiomFolio V1 API Routes Package
================================

Domain-driven route organization:
- portfolio/  : Holdings, orders, options, dividends, etc.
- market/     : Market data, snapshots, regime, intelligence
- admin/      : System administration
- settings/   : User preferences, notifications

Root-level routes are re-exported for backwards compatibility.
"""

# Re-export portfolio routes for backwards compatibility
from .portfolio.core import router as portfolio
from .portfolio.live import router as portfolio_live
from .portfolio.dashboard import router as portfolio_dashboard
from .portfolio.stocks import router as portfolio_stocks
from .portfolio.statements import router as portfolio_statements
from .portfolio.options import router as portfolio_options
from .portfolio.categories import router as portfolio_categories
from .portfolio.dividends import router as portfolio_dividends
from .portfolio.orders import router as portfolio_orders

# Re-export admin routes
from .admin.management import router as admin
from .admin.scheduler import router as admin_scheduler
from .admin.agent import router as admin_agent

# Re-export settings routes
from .settings.app import router as app_settings
from .settings.account import router as account_management
from .settings.notifications import router as notifications

# Root-level routes (not yet organized)
from .auth import router as auth
from .strategies import router as strategies
from .activity import router as activity
from .aggregator import router as aggregator
from .watchlist import router as watchlist

__all__ = [
    # Portfolio
    "portfolio",
    "portfolio_live",
    "portfolio_dashboard",
    "portfolio_stocks",
    "portfolio_statements",
    "portfolio_options",
    "portfolio_categories",
    "portfolio_dividends",
    "portfolio_orders",
    # Admin
    "admin",
    "admin_scheduler",
    "admin_agent",
    # Settings
    "app_settings",
    "account_management",
    "notifications",
    # Root-level
    "auth",
    "strategies",
    "activity",
    "aggregator",
    "watchlist",
]
