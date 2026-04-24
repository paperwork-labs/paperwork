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
from .activity import router as activity
from .admin.agent import router as admin_agent
from .admin.autoops import router as admin_autoops
from .admin.corporate_actions import router as admin_corporate_actions
from .admin.data_quality import router as admin_data_quality
from .admin.deploy_health import router as admin_deploy_health
from .admin.jobs import router as admin_jobs

# Re-export admin routes
from .admin.management import router as admin
from .admin.scheduler import router as admin_scheduler
from .aggregator import router as aggregator

# Root-level routes (not yet organized)
from .auth import router as auth
from .oauth import router as oauth
from .portfolio.allocation import router as portfolio_allocation
from .portfolio.categories import router as portfolio_categories
from .portfolio.core import router as portfolio
from .portfolio.dashboard import router as portfolio_dashboard
from .portfolio.discipline_trajectory import router as portfolio_discipline_trajectory
from .portfolio.dividends import router as portfolio_dividends
from .portfolio.income import router as portfolio_income
from .portfolio.live import router as portfolio_live
from .portfolio.options import router as portfolio_options
from .portfolio.options_tax import router as portfolio_options_tax
from .portfolio.orders import router as portfolio_orders
from .portfolio.statements import router as portfolio_statements
from .portfolio.stocks import router as portfolio_stocks
from .portfolio.tax_export import router as portfolio_tax_export
from .settings.account import router as account_management

# Re-export settings routes
from .settings.app import router as app_settings
from .settings.historical_import import router as historical_import
from .settings.notifications import router as notifications
from .strategies import router as strategies
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
    "portfolio_income",
    "portfolio_orders",
    "portfolio_tax_export",
    "portfolio_options_tax",
    "portfolio_allocation",
    "portfolio_discipline_trajectory",
    # Admin
    "admin",
    "admin_scheduler",
    "admin_agent",
    "admin_autoops",
    "admin_corporate_actions",
    "admin_data_quality",
    "admin_deploy_health",
    "admin_jobs",
    # Settings
    "app_settings",
    "account_management",
    "historical_import",
    "notifications",
    # Root-level
    "auth",
    "strategies",
    "activity",
    "aggregator",
    "watchlist",
    "oauth",
]
