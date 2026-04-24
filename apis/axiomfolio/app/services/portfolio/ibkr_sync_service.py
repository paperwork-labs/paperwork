"""Backward-compat shim — all logic moved to app.services.portfolio.ibkr/.

medallion: silver
"""

from app.services.portfolio.ibkr.pipeline import (  # noqa: F401
    IBKRSyncService,
    ibkr_sync_service,
    portfolio_sync_service,
)
from app.services.portfolio.ibkr.helpers import serialize_for_json  # noqa: F401
