"""Webhook endpoints for external integrations."""
from fastapi import APIRouter

from .picks import router as picks_webhook_router
from .stripe import router as stripe_router
from .tradingview import router as tradingview_router

router = APIRouter()
router.include_router(tradingview_router, prefix="/tradingview", tags=["tradingview"])
router.include_router(stripe_router, tags=["stripe"])
router.include_router(picks_webhook_router, prefix="/picks", tags=["picks-webhooks"])
