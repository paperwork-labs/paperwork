"""
FileFree.ai tax-export orchestrator.

This is the thin DB-aware layer. It fetches the rows that the mapper needs
and delegates the actual transform. Callers should use this class -- not the
mapper directly -- because it handles:

* Resolving which broker accounts belong to which user.
* Filtering closed-lot trades to the requested tax year and accounts.
* Optional account-id filtering for users with many accounts who only want
  one broker exported.
* Returning a single :class:`FileFreePackage` ready to JSON-encode.

Sessions are passed in by the caller (FastAPI dependency, Celery task, CLI),
never opened here -- consistent with the rest of the backend services.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Sequence

from sqlalchemy import extract
from sqlalchemy.orm import Session

from backend.models import BrokerAccount
from backend.models.trade import Trade

from .mapper import build_package
from .schemas import FileFreePackage

logger = logging.getLogger(__name__)

# Trade.status values that represent realized lots usable for tax filing.
_REALIZED_STATUSES = ("CLOSED_LOT", "WASH_SALE")


class FileFreeExporter:
    """Build FileFree.ai-shaped tax packages from the live DB."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def export(
        self,
        *,
        user_id: int,
        tax_year: int,
        account_ids: Optional[Sequence[int]] = None,
        include_tax_advantaged: bool = False,
        generated_at: Optional[datetime] = None,
    ) -> FileFreePackage:
        """Produce a :class:`FileFreePackage` for one user and one tax year.

        Args:
            user_id: Internal AxiomFolio user id whose accounts to export.
            tax_year: Calendar year (e.g. ``2024``) of the closing trade date.
            account_ids: Optional whitelist of broker account ids. ``None``
                means "all of this user's accounts".
            include_tax_advantaged: If ``False`` (default) IRA / Roth / HSA
                accounts are excluded from the export -- they don't generate
                taxable events anyway and including them only confuses the
                downstream UI. Set to ``True`` only for full audit dumps.
            generated_at: Override the timestamp written to the package; if
                omitted, ``now(UTC)`` is used. Tests should pin this for
                deterministic output.

        Returns:
            A populated, validated :class:`FileFreePackage` instance.
        """
        accounts = self._load_accounts(
            user_id=user_id,
            account_ids=account_ids,
            include_tax_advantaged=include_tax_advantaged,
        )
        if not accounts:
            logger.info(
                "filefree_export: user_id=%s tax_year=%s -> 0 in-scope accounts",
                user_id,
                tax_year,
            )
            return build_package(
                user_id=user_id,
                tax_year=tax_year,
                accounts=[],
                trades=[],
                generated_at=generated_at or datetime.now(timezone.utc),
            )

        scoped_account_ids = [acct.id for acct in accounts]
        trades = self._load_trades(account_ids=scoped_account_ids, tax_year=tax_year)

        logger.info(
            "filefree_export: user_id=%s tax_year=%s accounts=%d trades=%d",
            user_id,
            tax_year,
            len(accounts),
            len(trades),
        )

        return build_package(
            user_id=user_id,
            tax_year=tax_year,
            accounts=accounts,
            trades=trades,
            generated_at=generated_at or datetime.now(timezone.utc),
        )

    def _load_accounts(
        self,
        *,
        user_id: int,
        account_ids: Optional[Sequence[int]],
        include_tax_advantaged: bool,
    ) -> List[BrokerAccount]:
        q = self.db.query(BrokerAccount).filter(BrokerAccount.user_id == user_id)
        if account_ids:
            q = q.filter(BrokerAccount.id.in_(list(account_ids)))
        accounts = q.all()
        if include_tax_advantaged:
            return accounts
        return [a for a in accounts if not a.is_tax_advantaged]

    def _load_trades(
        self,
        *,
        account_ids: Sequence[int],
        tax_year: int,
    ) -> List[Trade]:
        if not account_ids:
            return []
        return (
            self.db.query(Trade)
            .filter(
                Trade.account_id.in_(list(account_ids)),
                Trade.status.in_(_REALIZED_STATUSES),
                extract("year", Trade.execution_time) == tax_year,
            )
            .order_by(Trade.account_id, Trade.execution_time, Trade.id)
            .all()
        )
