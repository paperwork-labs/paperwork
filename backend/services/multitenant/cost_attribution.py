"""Per-tenant cost attribution rollup.

Aggregates per-user spend per UTC day across:

* LLM calls — sourced from ``PortfolioNarrative.cost_usd`` today.
* Provider call cost — currently a row-count proxy. Real cost requires
  an upstream "provider invocation log" we haven't built yet; the
  proxy gives finance a stable number to look at and keeps the
  rollup table populated. When the real source lands, swap the
  ``_provider_call_cost`` impl.
* Storage — proxy: row counts × small constant per row, summed across
  user-scoped tables. Same trade-off as above.

All money math uses :class:`Decimal`. Storage rollup writes integer MB.
The job uses an UPSERT so reruns for the same (user, day) overwrite
rather than duplicate.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.models import Base
from backend.models.multitenant import TenantCostRollup
from backend.models.narrative import PortfolioNarrative
from backend.models.user import User

logger = logging.getLogger(__name__)


# Row-count storage proxy: assume an average user-scoped row weighs
# ~1 KB on disk + indexes. 1 MB ~= 1000 rows. This is intentionally
# conservative; real per-tenant disk attribution needs PG stats.
_BYTES_PER_ROW = 1024


def _user_scoped_tables() -> Iterable:
    for table in Base.metadata.sorted_tables:
        if "user_id" in table.c and table.name != "users":
            yield table


class CostAttributionService:
    """Compute and persist daily ``TenantCostRollup`` rows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- public API -----------------------------------------------------

    def rollup_day(self, day: date) -> int:
        """Compute and upsert rollup rows for ``day``. Returns row count."""
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)

        rows_written = 0
        rows_failed = 0
        rows_total = 0

        # Iterate every active user. We deliberately skip soft-deleted
        # users (``is_active = False``) — their cost has stopped accruing.
        user_ids = [
            uid
            for (uid,) in self.db.execute(
                select(User.id).where(User.is_active.is_(True))
            ).all()
        ]
        rows_total = len(user_ids)

        for uid in user_ids:
            try:
                llm = self._llm_cost(uid, start, end)
                provider = self._provider_call_cost(uid, start, end)
                storage_mb = self._storage_mb(uid)
                total = llm + provider

                stmt = pg_insert(TenantCostRollup).values(
                    user_id=uid,
                    day=day,
                    llm_cost_usd=llm,
                    provider_call_cost_usd=provider,
                    storage_mb=storage_mb,
                    total_cost_usd=total,
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_tenant_cost_rollups_user_day",
                    set_={
                        "llm_cost_usd": llm,
                        "provider_call_cost_usd": provider,
                        "storage_mb": storage_mb,
                        "total_cost_usd": total,
                    },
                )
                self.db.execute(stmt)
                rows_written += 1
            except Exception as exc:
                rows_failed += 1
                logger.warning(
                    "cost_rollup: user_id=%s day=%s failed: %s", uid, day, exc
                )

        self.db.commit()

        # Counter-drift assertion (per the no-silent-fallback iron law).
        assert rows_written + rows_failed == rows_total, (
            f"cost_rollup counter drift: written={rows_written} "
            f"failed={rows_failed} total={rows_total}"
        )
        logger.info(
            "cost_rollup: day=%s written=%d failed=%d total=%d",
            day,
            rows_written,
            rows_failed,
            rows_total,
        )
        return rows_written

    def top_n_by_cost(self, day: date, limit: int = 25) -> list[dict]:
        """Return top ``limit`` users by ``total_cost_usd`` for ``day``."""
        rows = self.db.execute(
            select(
                TenantCostRollup.user_id,
                TenantCostRollup.llm_cost_usd,
                TenantCostRollup.provider_call_cost_usd,
                TenantCostRollup.storage_mb,
                TenantCostRollup.total_cost_usd,
            )
            .where(TenantCostRollup.day == day)
            .order_by(TenantCostRollup.total_cost_usd.desc())
            .limit(limit)
        ).all()
        return [
            {
                "user_id": int(r.user_id),
                "llm_cost_usd": str(r.llm_cost_usd),
                "provider_call_cost_usd": str(r.provider_call_cost_usd),
                "storage_mb": int(r.storage_mb),
                "total_cost_usd": str(r.total_cost_usd),
            }
            for r in rows
        ]

    # -- per-tenant cost calculators -----------------------------------

    def _llm_cost(self, user_id: int, start, end) -> Decimal:
        total = self.db.execute(
            select(func.coalesce(func.sum(PortfolioNarrative.cost_usd), 0)).where(
                PortfolioNarrative.user_id == user_id,
                PortfolioNarrative.created_at >= start,
                PortfolioNarrative.created_at < end,
            )
        ).scalar()
        return Decimal(str(total or 0))

    def _provider_call_cost(self, user_id: int, start, end) -> Decimal:
        # PROXY: there is no per-user provider-invocation log today.
        # Returning Decimal('0') is honest; we will replace this with a
        # real query against a future ``ProviderCall`` table. This keeps
        # the column populated and the schema stable so downstream
        # reports don't have to migrate.
        return Decimal("0")

    def _storage_mb(self, user_id: int) -> int:
        # PROXY: row-count × bytes-per-row, summed across user-scoped
        # tables. Stable, cheap, and good enough for the "who's
        # consuming the most" admin view.
        total_rows = 0
        for table in _user_scoped_tables():
            try:
                cnt = self.db.execute(
                    select(func.count())
                    .select_from(table)
                    .where(table.c.user_id == user_id)
                ).scalar() or 0
            except Exception as exc:
                logger.warning(
                    "cost_rollup: row-count failed for table=%s user=%s: %s",
                    table.name,
                    user_id,
                    exc,
                )
                continue
            total_rows += int(cnt)
        return max(0, (total_rows * _BYTES_PER_ROW) // (1024 * 1024))
