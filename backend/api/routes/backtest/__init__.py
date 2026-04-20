"""Backtest analysis HTTP routes (Monte Carlo, walk-forward, etc).

Each sub-module exposes its own ``router``; this package stitches them
together so the URL surface remains stable while internal layout can
evolve. See ``backend/api/main.py`` for the include_router site.
"""

from fastapi import APIRouter

from backend.api.routes.backtest.monte_carlo import router as monte_carlo_router

router = APIRouter()
router.include_router(monte_carlo_router)

__all__ = ["router"]
