"""Subscriber-facing picks routes."""

from fastapi import APIRouter

from . import published

router = APIRouter()
router.include_router(published.router)
