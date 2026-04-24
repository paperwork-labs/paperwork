"""Signals API (auxiliary external context, not primary strategy signals)."""

from fastapi import APIRouter

from . import external

router = APIRouter(prefix="/signals", tags=["Signals"])
router.include_router(external.router)
