"""Public transparency counters — derived from the real broker catalog.

The public ``/api/v1/public/stats`` endpoint and marketing pages
(``WhyFree``, ``Pricing``, ``PublicStatsStrip``) read from these
constants so they stay in sync with the code reality.

Single source of truth for broker counts:
    * ``DIRECT_CONNECT_BROKERS_LIVE``: brokers we connect to directly
      today (i.e. ``BrokerType`` members backed by a concrete sync
      service). Note that "direct" here is deliberately broader than
      "OAuth" — IBKR uses FlexQuery + Gateway rather than OAuth, and
      Schwab / TastyTrade use OAuth. The marketing claim we make is
      "direct connection/integration", not "OAuth", because that is
      what the code actually does. See docs/KNOWLEDGE.md D131.
    * ``DIRECT_OAUTH_BROKERS_PLANNED``: OAuth-only brokers not yet in
      ``DIRECT_CONNECT_BROKERS_LIVE``. As each one ships it is promoted into
      ``DIRECT_CONNECT_BROKERS_LIVE`` and removed from this tuple so
      the marketing claim "expanding OAuth" is code-grounded and
      shrinks to zero when the track is done.
    * ``IMPORT_CATALOG_BROKERS_COUNT``: count of brokers available via
      CSV / email-statement import (from ``broker_catalog.py``). The
      catalog itself remains the authority for names and metadata; we
      only expose the count here to avoid a heavy cross-module import.
    * ``BROKERS_SUPPORTED``: the single integer rendered in the public
      stats strip. It is intentionally the sum of LIVE direct connect +
      the import-catalog, so a user reading the marketing page can
      connect (or at least land data from) that many brokers today.

Backwards-compatibility alias ``DIRECT_OAUTH_BROKERS_LIVE`` is kept as a
deprecated name pointing at the same tuple so callers pinned to the old
import don't break mid-flight. Prefer ``DIRECT_CONNECT_BROKERS_LIVE``.

See docs/KNOWLEDGE.md D129 for the direct-connect-only expansion policy
(no Plaid in v1), and D131 for the OAuth→direct-connect rename.
"""

from __future__ import annotations

DIRECT_CONNECT_BROKERS_LIVE: tuple[str, ...] = (
    "schwab",  # OAuth 2.0
    "ibkr",  # FlexQuery + IB Gateway (not OAuth — see D131)
    "tastytrade",  # OAuth 2.0
    "etrade",  # OAuth 1.0a (sandbox in v1)
    "tradier",  # OAuth 2.0 (live + sandbox tokens)
    "coinbase",  # OAuth 2.0 (consumer wallet read-only)
)

# Deprecated alias. Kept so existing imports
# (``from app.constants.public_stats import DIRECT_OAUTH_BROKERS_LIVE``)
# don't break during the rename. Remove once external callers migrate.
DIRECT_OAUTH_BROKERS_LIVE: tuple[str, ...] = DIRECT_CONNECT_BROKERS_LIVE

DIRECT_OAUTH_BROKERS_PLANNED: tuple[str, ...] = ()

IMPORT_CATALOG_BROKERS_COUNT: int = 14

BROKERS_SUPPORTED: int = len(DIRECT_CONNECT_BROKERS_LIVE) + IMPORT_CATALOG_BROKERS_COUNT
