"""
Connection-options endpoint for the Connect hub UI.

Exposes ``GET /api/v1/portfolio/connection-options`` — a single payload that
carries (a) the static broker catalog and (b) the per-user connected state
for each broker. The UI uses this to render every broker card with the
correct CTA without making N follow-up requests.

Per D100/D101b: this route is the data contract behind the unified
``/connect`` page. It does NOT initiate any OAuth or sync flows — those
live in the existing aggregator routes (``/api/v1/aggregator/*``) and
account routes (``/api/v1/accounts/*``). Keep it that way: this route is a
read-only catalog/state read.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import DefaultDict, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.broker_account import (
    AccountStatus,
    BrokerAccount,
    BrokerType,
)
from app.models.user import User
from app.services.silver.portfolio.broker_catalog import (
    SLUG_TO_BROKER_TYPE,
    BrokerCatalogEntry,
    get_catalog,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# -----------------------------------------------------------------------------
# Response schemas
# -----------------------------------------------------------------------------


class BrokerUserState(BaseModel):
    """Per-user state for a single broker.

    ``connected`` is True iff the user has at least one active
    ``BrokerAccount`` row for the broker. ``account_count`` and
    ``last_synced_at`` are populated only when ``connected`` is True; the
    frontend uses them to render the "Last synced N min ago" microcopy.
    """

    connected: bool
    account_count: int = 0
    last_synced_at: Optional[datetime] = None


class BrokerOption(BaseModel):
    slug: str
    name: str
    description: str
    logo_url: str
    category: str
    method: str
    status: str
    user_state: BrokerUserState


class ConnectionOptionsResponse(BaseModel):
    brokers: List[BrokerOption]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _broker_type_for_slug(slug: str) -> Optional[BrokerType]:
    """Resolve a catalog slug to its ``BrokerType`` enum, if any.

    Returns None for catalog slugs we do not (yet) persist to
    ``broker_accounts`` — for those, ``user_state.connected`` is always
    False because there's no row to read.
    """

    raw = SLUG_TO_BROKER_TYPE.get(slug)
    if not raw:
        return None
    try:
        return BrokerType(raw)
    except ValueError:
        # Catalog references a broker we don't yet model in the enum —
        # surface as "not connected" rather than 500. Worth logging once.
        logger.warning("broker_catalog slug '%s' has no BrokerType enum member", slug)
        return None


def _active_accounts_by_broker(
    db: Session, user_id: int
) -> Dict[BrokerType, List[BrokerAccount]]:
    """Load all active ``BrokerAccount`` rows for ``user_id`` once.

    Used by ``list_connection_options`` to avoid an N+1 query per catalog entry.
    """

    rows = (
        db.query(BrokerAccount)
        .filter(
            BrokerAccount.user_id == user_id,
            BrokerAccount.status == AccountStatus.ACTIVE,
        )
        .all()
    )
    grouped: DefaultDict[BrokerType, List[BrokerAccount]] = defaultdict(list)
    for row in rows:
        grouped[row.broker].append(row)
    return dict(grouped)


def _build_user_state(
    entry: BrokerCatalogEntry,
    accounts_by_broker: Dict[BrokerType, List[BrokerAccount]],
) -> BrokerUserState:
    """Build the per-user state for one broker from a pre-grouped account map.

    Inactive/closed accounts (``AccountStatus`` != ACTIVE) are excluded at
    query time so a user who once connected and later disconnected does not
    show as "connected" forever.
    """

    bt = _broker_type_for_slug(entry.slug)
    if bt is None:
        return BrokerUserState(connected=False)

    accounts = accounts_by_broker.get(bt) or []
    if not accounts:
        return BrokerUserState(connected=False)

    last_sync_values = [a.last_successful_sync for a in accounts if a.last_successful_sync]
    last_sync = max(last_sync_values) if last_sync_values else None
    return BrokerUserState(
        connected=True,
        account_count=len(accounts),
        last_synced_at=last_sync,
    )


# -----------------------------------------------------------------------------
# Route
# -----------------------------------------------------------------------------


@router.get(
    "/connection-options",
    response_model=ConnectionOptionsResponse,
    summary="List all brokers + per-user connected state for the Connect hub",
)
async def list_connection_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectionOptionsResponse:
    """Return the broker catalog enriched with the caller's connected state.

    Authentication is required: ``user_state`` is derived from the caller's
    ``BrokerAccount`` rows, so an unauthenticated response would be either
    misleading or trivially leaky. We do NOT swallow per-broker errors —
    the catalog is in-process data and the only DB failure mode would be
    a wholesale outage that the global handler should surface.
    """

    catalog = get_catalog()
    accounts_by_broker = _active_accounts_by_broker(db, current_user.id)
    options: List[BrokerOption] = []
    for entry in catalog:
        user_state = _build_user_state(entry, accounts_by_broker)
        options.append(
            BrokerOption(
                slug=entry.slug,
                name=entry.name,
                description=entry.description,
                logo_url=entry.logo_url,
                category=entry.category,
                method=entry.method,
                status=entry.status,
                user_state=user_state,
            )
        )

    return ConnectionOptionsResponse(brokers=options)
