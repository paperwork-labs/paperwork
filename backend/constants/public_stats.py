"""Public transparency counters — derived from the real broker catalog.

The public ``/api/v1/public/stats`` endpoint and marketing pages
(``WhyFree``, ``Pricing``, ``PublicStatsStrip``) read from these
constants so they stay in sync with the code reality.

Single source of truth for broker counts:
    * ``DIRECT_OAUTH_BROKERS_LIVE``: brokers we can connect via OAuth today
      (i.e. ``BrokerType`` members backed by a concrete sync service).
    * ``DIRECT_OAUTH_BROKERS_PLANNED``: Phase 1 additions from the
      broker-parity plan (E*TRADE / Tradier / Coinbase) — listed here
      so the marketing claim "expanding OAuth" is code-grounded and
      shrinks to zero when each PR ships.
    * ``IMPORT_CATALOG_BROKERS_COUNT``: count of brokers available via
      CSV / email-statement import (from ``broker_catalog.py``). The
      catalog itself remains the authority for names and metadata; we
      only expose the count here to avoid a heavy cross-module import.
    * ``BROKERS_SUPPORTED``: the single integer rendered in the public
      stats strip. It is intentionally the sum of LIVE direct OAuth +
      the import-catalog, so a user reading the marketing page can
      connect (or at least land data from) that many brokers today.

See docs/KNOWLEDGE.md D129 for the direct-OAuth-only expansion policy
(no Plaid in v1).
"""

from __future__ import annotations

from typing import Tuple


DIRECT_OAUTH_BROKERS_LIVE: Tuple[str, ...] = (
    "schwab",
    "ibkr",
    "tastytrade",
    "etrade",
)

DIRECT_OAUTH_BROKERS_PLANNED: Tuple[str, ...] = (
    "tradier",
    "coinbase",
)

IMPORT_CATALOG_BROKERS_COUNT: int = 14

BROKERS_SUPPORTED: int = len(DIRECT_OAUTH_BROKERS_LIVE) + IMPORT_CATALOG_BROKERS_COUNT
