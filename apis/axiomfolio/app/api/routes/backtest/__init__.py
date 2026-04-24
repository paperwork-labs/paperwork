"""Backtest analysis HTTP routes (walk-forward, Monte Carlo, etc).

Each sub-module exposes its own ``router``; this package stitches them
together so the URL surface stays stable while internal layout evolves.
See ``app/api/main.py`` for the include_router site.

Walk-forward ships in ``walk_forward``; Monte Carlo in ``monte_carlo``.
Both mount under the same aggregated ``router``.
"""

from fastapi import APIRouter

from app.api.routes.backtest.walk_forward import router as walk_forward_router
from app.api.routes.backtest.monte_carlo import router as monte_carlo_router

router = APIRouter()
router.include_router(walk_forward_router)
router.include_router(monte_carlo_router)

__all__ = ["router", "walk_forward_router", "monte_carlo_router"]
