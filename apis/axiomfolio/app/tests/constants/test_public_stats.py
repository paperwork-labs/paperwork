"""Consistency tests for ``backend/constants/public_stats.py``.

These tests enforce that the numbers rendered by the public stats strip
and WhyFree/Pricing marketing pages stay grounded in the actual broker
catalog and enum, rather than drifting silently as new direct-connect
brokers ship or import-catalog entries are added.

See docs/KNOWLEDGE.md D129 (direct-connect-only policy) and D131
(the rename from ``DIRECT_OAUTH_BROKERS_LIVE`` →
``DIRECT_CONNECT_BROKERS_LIVE`` — IBKR is FlexQuery, not OAuth).
"""

from __future__ import annotations

from app.constants import public_stats as pstats
from app.constants.public_stats import (
    BROKERS_SUPPORTED,
    DIRECT_CONNECT_BROKERS_LIVE,
    DIRECT_OAUTH_BROKERS_LIVE,
    DIRECT_OAUTH_BROKERS_PLANNED,
    IMPORT_CATALOG_BROKERS_COUNT,
)
from app.models.broker_account import BrokerType
from app.services.silver.portfolio.broker_catalog import get_catalog


def test_direct_oauth_alias_points_at_direct_connect() -> None:
    """Back-compat alias from D131: the old ``DIRECT_OAUTH_BROKERS_LIVE``
    name is preserved and must resolve to the renamed constant so callers
    pinned to the old import keep working through the transition.
    """
    assert DIRECT_OAUTH_BROKERS_LIVE is DIRECT_CONNECT_BROKERS_LIVE
    assert DIRECT_CONNECT_BROKERS_LIVE is pstats.DIRECT_CONNECT_BROKERS_LIVE


def test_direct_connect_live_matches_brokertype_enum() -> None:
    """Every 'live direct-connect' slug must exist as a BrokerType member.

    If a slug is added to ``DIRECT_CONNECT_BROKERS_LIVE`` before its
    ``BrokerType`` member ships, the marketing copy will claim something
    the code cannot deliver.
    """

    enum_values = {b.value for b in BrokerType}
    missing = [
        slug for slug in DIRECT_CONNECT_BROKERS_LIVE if slug not in enum_values
    ]
    assert not missing, (
        f"Live direct-connect brokers missing from BrokerType enum: {missing}. "
        "Either land the sync service (and add the enum member) first, "
        "or move the slug to DIRECT_OAUTH_BROKERS_PLANNED."
    )


def test_direct_oauth_planned_not_yet_in_brokertype_enum() -> None:
    """Planned OAuth brokers must NOT already be shipping.

    If a planned slug has already landed in ``BrokerType``, it should be
    promoted to ``DIRECT_CONNECT_BROKERS_LIVE`` so marketing reflects
    reality.
    """

    enum_values = {b.value for b in BrokerType}
    already_live = [
        slug for slug in DIRECT_OAUTH_BROKERS_PLANNED if slug in enum_values
    ]
    assert not already_live, (
        f"Planned OAuth brokers have already shipped: {already_live}. "
        "Promote them to DIRECT_CONNECT_BROKERS_LIVE."
    )


def test_import_catalog_count_matches_catalog() -> None:
    """The marketing count of import brokers matches the real catalog."""

    catalog_import_count = sum(1 for entry in get_catalog() if entry.method == "import")
    assert IMPORT_CATALOG_BROKERS_COUNT == catalog_import_count, (
        f"IMPORT_CATALOG_BROKERS_COUNT ({IMPORT_CATALOG_BROKERS_COUNT}) drifted "
        f"from broker_catalog ({catalog_import_count} import entries). "
        "Update the constant when the catalog changes."
    )


def test_brokers_supported_is_live_direct_connect_plus_import() -> None:
    """``BROKERS_SUPPORTED`` = live direct-connect + import-catalog, always."""

    assert (
        BROKERS_SUPPORTED
        == len(DIRECT_CONNECT_BROKERS_LIVE) + IMPORT_CATALOG_BROKERS_COUNT
    )
