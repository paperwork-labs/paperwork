"""IBKR sync pipeline — split from monolithic ibkr_sync_service.py.

medallion: bronze
"""

from app.services.bronze.ibkr.pipeline import IBKRSyncService

__all__ = ["IBKRSyncService"]
