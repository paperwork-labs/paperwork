"""Position-management routes (sleeve tagging).

Separate from ``routes/portfolio/`` because these endpoints are
position-centric (operate on a single ``Position.id``) rather than
portfolio-level aggregations. Keeping them in their own router keeps
the portfolio package focused on read/aggregate flows.
"""

from fastapi import APIRouter

from . import sleeve

router = APIRouter()
router.include_router(sleeve.router)
