"""Webhook endpoints for external integrations."""
from fastapi import APIRouter

from .stripe import router as stripe_router
from .tradingview import router as tradingview_router

router = APIRouter()
router.include_router(tradingview_router, prefix="/tradingview", tags=["tradingview"])
router.include_router(stripe_router, tags=["stripe"])
