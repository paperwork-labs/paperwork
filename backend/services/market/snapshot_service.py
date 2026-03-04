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
        skip_fundamentals: bool = False,
        benchmark_df=None,
    ) -> Dict[str, Any]:
        _ = limit_bars
        return self._service.compute_snapshot_from_db(
            db, symbol, as_of_dt=as_of_dt, skip_fundamentals=skip_fundamentals,
            benchmark_df=benchmark_df,
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
        auto_commit: bool = True,
    ):
        return self._service.persist_snapshot(
            db,
            symbol,
            snapshot,
            analysis_type=analysis_type,
            ttl_hours=ttl_hours,
            auto_commit=auto_commit,
        )

    async def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        return await self._service.get_snapshot(symbol)
