from __future__ import annotations

from typing import Any, Dict


class MarketSnapshotService:
    """Snapshot computation/persistence facade for MarketDataService."""

    def __init__(self, service) -> None:
        self._service = service

    def compute_snapshot_from_db(
        self,
        db,
        symbol: str,
        *,
        limit_bars: int = 300,
        as_of_dt=None,
    ) -> Dict[str, Any]:
        return self._service.compute_snapshot_from_db(
            db, symbol, limit_bars=limit_bars, as_of_dt=as_of_dt
        )

    async def compute_snapshot_from_providers(self, symbol: str) -> Dict[str, Any]:
        return await self._service.compute_snapshot_from_providers(symbol)

    def persist_snapshot(
        self,
        db,
        symbol: str,
        snapshot: Dict[str, Any],
        *,
        analysis_type: str = "technical_snapshot",
        ttl_hours: int = 24,
    ):
        return self._service.persist_snapshot(
            db,
            symbol,
            snapshot,
            analysis_type=analysis_type,
            ttl_hours=ttl_hours,
        )

    async def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        return await self._service.get_snapshot(symbol)
