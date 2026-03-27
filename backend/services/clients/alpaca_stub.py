"""Alpaca broker adapter re-export.

The implementation lives in :mod:`backend.services.portfolio.adapters.alpaca_adapter`.
This module remains for imports of ``AlpacaAdapter`` from ``clients``.
"""

from __future__ import annotations

from backend.services.portfolio.adapters.alpaca_adapter import AlpacaAdapter

__all__ = ["AlpacaAdapter"]
