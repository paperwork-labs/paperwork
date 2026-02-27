"""Backward-compat shim — all logic moved to backend.services.portfolio.ibkr/."""

from backend.services.portfolio.ibkr.pipeline import (  # noqa: F401
    IBKRSyncService,
    ibkr_sync_service,
    portfolio_sync_service,
)
from backend.services.portfolio.ibkr.helpers import serialize_for_json  # noqa: F401
