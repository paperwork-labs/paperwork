"""Subscriber-facing picks routes."""

from fastapi import APIRouter

from . import candidates_today, published

router = APIRouter()
router.include_router(published.router)
router.include_router(candidates_today.router)
