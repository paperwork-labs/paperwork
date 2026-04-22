"""User-scoped connection aggregation helpers (broker accounts + OAuth)."""

from backend.services.connections.health_aggregate import build_connections_health

__all__ = ["build_connections_health"]
