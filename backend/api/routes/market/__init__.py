"""
Market Data Routes Package
==========================

Modular market data routes - complete migration from market_data.py.

Modules:
- admin.py: Health, backfill, jobs, auto-fix, indicators
- prices.py: Current prices, historical data, indicator series
- snapshots.py: Market snapshots CRUD
- coverage.py: Data coverage health
- regime.py: Market regime state
- intelligence.py: AI-generated briefs
- universe.py: Index constituents, tracked symbols
- dashboard.py: Market overview dashboards
"""

from fastapi import APIRouter

from .admin import router as admin_router
from .prices import router as prices_router
from .snapshots import router as snapshots_router
from .coverage import router as coverage_router
from .regime import router as regime_router
from .intelligence import router as intelligence_router
from .universe import router as universe_router
from .dashboard import router as dashboard_router
from .earnings import router as earnings_router

# Combined router for all market endpoints
router = APIRouter()

# Include all sub-routers (order matters for route matching)
router.include_router(admin_router)
router.include_router(dashboard_router)
router.include_router(prices_router)
router.include_router(snapshots_router)
router.include_router(coverage_router)
router.include_router(regime_router)
router.include_router(intelligence_router)
router.include_router(universe_router)
router.include_router(earnings_router)

__all__ = [
    "router",
    "admin_router",
    "prices_router",
    "snapshots_router",
    "coverage_router",
    "regime_router",
    "intelligence_router",
    "universe_router",
    "dashboard_router",
    "earnings_router",
]
