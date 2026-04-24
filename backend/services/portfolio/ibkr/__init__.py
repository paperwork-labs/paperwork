"""IBKR sync pipeline — split from monolithic ibkr_sync_service.py.

medallion: bronze
"""

from backend.services.portfolio.ibkr.pipeline import IBKRSyncService

__all__ = ["IBKRSyncService"]
