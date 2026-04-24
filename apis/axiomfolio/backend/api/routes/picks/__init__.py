"""Subscriber-facing picks routes."""

from fastapi import APIRouter

from . import candidates_today, conviction, published

router = APIRouter()
router.include_router(published.router)
router.include_router(candidates_today.router)
router.include_router(conviction.router)
