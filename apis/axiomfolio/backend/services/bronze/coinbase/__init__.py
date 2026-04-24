"""Coinbase bronze ingestion (OAuth 2.0 v2 wallet API).

medallion: bronze
"""

from __future__ import annotations

from backend.services.bronze.coinbase.client import (
    CoinbaseAPIError,
    CoinbaseBronzeClient,
)
from backend.services.bronze.coinbase.sync_service import CoinbaseSyncService

__all__ = [
    "CoinbaseAPIError",
    "CoinbaseBronzeClient",
    "CoinbaseSyncService",
]
