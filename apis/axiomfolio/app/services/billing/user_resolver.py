"""Resolves Stripe events to internal User IDs.

Resolution order (most reliable first):

    1. ``metadata.user_id`` set by the checkout-session creator (this is the
       canonical path; see app/api/routes/billing.py once that PR lands).
    2. ``stripe_customer_id`` lookup against the entitlements table (cached
       there by an earlier event).
    3. ``email`` lookup against the users table.

Returning ``None`` means "we don't know who this is, do not act." The
processor will raise StripeWebhookError so Stripe retries (the answer may
become known after the user signs up).

medallion: ops
"""
from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


class DBUserResolver:
    """Production resolver backed by the SQLAlchemy session.

    Caller owns the Session lifecycle (per engineering.mdc).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve(
        self,
        *,
        stripe_customer_id: Optional[str],
        email: Optional[str],
        metadata: Mapping[str, Any],
    ) -> Optional[int]:
        # 1. Trust explicit metadata first.
        meta_uid = metadata.get("user_id")
        if meta_uid is not None:
            try:
                uid = int(meta_uid)
                if uid > 0:
                    return uid
            except (TypeError, ValueError):
                logger.warning(
                    "stripe webhook: metadata.user_id not int-coercible: %r", meta_uid
                )

        # 2. stripe_customer_id -> entitlements row (only if entitlements table
        # exists; we soft-import to keep this PR independent of PR #326).
        if stripe_customer_id:
            uid = self._lookup_by_stripe_customer(stripe_customer_id)
            if uid is not None:
                return uid

        # 3. Email fallback.
        if email:
            normalized = email.strip().lower()
            if normalized:
                stmt = select(User.id).where(User.email == normalized).limit(1)
                row = self._session.execute(stmt).scalar_one_or_none()
                if row:
                    return int(row)

        return None

    # ------------------------------------------------------------------ #

    def _lookup_by_stripe_customer(self, customer_id: str) -> Optional[int]:
        """Look up user_id from entitlements.stripe_customer_id, if the table exists."""
        try:
            from app.models.entitlement import Entitlement  # type: ignore[import-not-found]
        except ImportError:
            # Entitlements model not yet available in this branch (PR #326
            # not merged); skip silently.
            return None

        stmt = (
            select(Entitlement.user_id)
            .where(Entitlement.stripe_customer_id == customer_id)
            .limit(1)
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return int(row) if row else None
