"""Webhook endpoints for external integrations."""
from fastapi import APIRouter

from .tradingview import router as tradingview_router

router = APIRouter()
router.include_router(tradingview_router, prefix="/tradingview", tags=["tradingview"])
