"""
Fundamentals enrichment tasks (index constituents + MarketSnapshot fields).
"""

import logging
from datetime import UTC, datetime, timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import or_

from app.database import SessionLocal
from app.models import IndexConstituent
from app.services.market.constants import FUNDAMENTAL_FIELDS
from app.services.market.market_data_service import quote, snapshot_builder
from app.tasks.utils.task_utils import (
    _set_task_status,
    setup_event_loop,
    task_run,
)

logger = logging.getLogger(__name__)

_DEFAULT_SOFT = 3500
_DEFAULT_HARD = 3600


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run("market_indices_fundamentals_enrich")
def enrich_index(indices: list[str] | None = None, limit_per_run: int = 500) -> dict:
    """Fill sector/industry/market_cap on IndexConstituent using DB-first snapshots."""
    _set_task_status("market_indices_fundamentals_enrich", "running")
    session = SessionLocal()
    try:
        q = session.query(IndexConstituent)
        if indices:
            q = q.filter(IndexConstituent.index_name.in_([i.upper() for i in indices]))
        rows = (
            q.filter(
                (IndexConstituent.sector.is_(None))
                | (IndexConstituent.industry.is_(None))
                | (IndexConstituent.market_cap.is_(None))
            )
            .order_by(IndexConstituent.symbol.asc())
            .limit(limit_per_run)
            .all()
        )
        updated = 0
        for r in rows:
            sym = (r.symbol or "").upper()
            if not sym:
                continue
            snap = snapshot_builder.get_snapshot_from_store(session, sym)
            if not snap:
                snap = snapshot_builder.compute_snapshot_from_db(session, sym)
            if not snap or (
                snap.get("sector") is None
                and snap.get("industry") is None
                and snap.get("market_cap") is None
            ):
                try:
                    loop = setup_event_loop()
                    try:
                        prov = loop.run_until_complete(
                            snapshot_builder.compute_snapshot_from_providers(sym)
                        )
                    finally:
                        loop.close()
                    if prov:
                        for k in FUNDAMENTAL_FIELDS[2:5]:
                            if prov.get(k) is not None:
                                snap = snap or {}
                                snap[k] = prov.get(k)
                except SoftTimeLimitExceeded:
                    raise
                except Exception as e:
                    logger.warning("Provider fundamentals fetch failed for %s: %s", sym, e)
            if not snap:
                continue
            changed = False
            if r.sector is None and snap.get("sector") is not None:
                r.sector = snap.get("sector")
                changed = True
            if r.industry is None and snap.get("industry") is not None:
                r.industry = snap.get("industry")
                changed = True
            if r.market_cap is None and snap.get("market_cap") is not None:
                try:
                    r.market_cap = int(snap.get("market_cap"))
                except (TypeError, ValueError) as e:
                    logger.warning("market_cap conversion failed for %s: %s", sym, e)
                else:
                    changed = True
            if changed:
                updated += 1
        if updated:
            session.commit()
        res = {"status": "ok", "inspected": len(rows), "updated": updated}
        _set_task_status("market_indices_fundamentals_enrich", "ok", res)
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run(
    "market_snapshots_fundamentals_fill",
    lock_key=lambda **_: "fundamentals_fill",
    lock_ttl_seconds=_DEFAULT_HARD + 300,
)
def fill_missing(limit_per_run: int = 500) -> dict:
    """Fill missing fundamental/display data on MarketSnapshot rows (tracked table)."""
    _set_task_status("market_snapshots_fundamentals_fill", "running")
    session = SessionLocal()
    try:
        from sqlalchemy import case

        from app.models.market_data import MarketSnapshot as _MS

        missing_conditions = []
        for k in FUNDAMENTAL_FIELDS:
            if hasattr(_MS, k):
                missing_conditions.append(getattr(_MS, k).is_(None))
        if not missing_conditions:
            return {"status": "ok", "inspected": 0, "updated": 0}

        rows = (
            session.query(_MS)
            .filter(
                _MS.analysis_type == "technical_snapshot",
                or_(*missing_conditions),
            )
            .order_by(
                case((_MS.sector.is_(None), 0), else_=1),
                _MS.analysis_timestamp.desc(),
            )
            .limit(limit_per_run)
            .all()
        )
        updated = 0
        for r in rows:
            sym = (r.symbol or "").upper()
            if not sym:
                continue
            snap = snapshot_builder.compute_snapshot_from_db(session, sym)
            needs_funda = not snap or any(snap.get(k) is None for k in FUNDAMENTAL_FIELDS)
            if needs_funda:
                funda = quote.get_fundamentals_info(sym)
                if funda:
                    snap = snap or {}
                    for k in FUNDAMENTAL_FIELDS:
                        if funda.get(k) is not None:
                            snap[k] = funda.get(k)
            if not snap:
                continue
            has_new = any(
                getattr(r, k, None) is None and snap.get(k) is not None
                for k in FUNDAMENTAL_FIELDS
                if hasattr(_MS, k)
            )
            if has_new:
                snapshot_builder.persist_snapshot(session, sym, {**(r.raw_analysis or {}), **snap})
                updated += 1
        res = {"status": "ok", "inspected": len(rows), "updated": updated}
        _set_task_status("market_snapshots_fundamentals_fill", "ok", res)
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run("market_snapshots_fundamentals_refresh")
def refresh_stale(stale_days: int = 7, limit_per_run: int = 500) -> dict:
    """Re-fetch fundamentals for snapshots older than *stale_days*."""
    _set_task_status("market_snapshots_fundamentals_refresh", "running")
    session = SessionLocal()
    try:
        from app.models.market_data import MarketSnapshot as _MS

        cutoff = datetime.now(UTC) - timedelta(days=stale_days)
        rows = (
            session.query(_MS)
            .filter(
                _MS.analysis_type == "technical_snapshot",
                _MS.analysis_timestamp < cutoff,
            )
            .order_by(_MS.analysis_timestamp.asc())
            .limit(limit_per_run)
            .all()
        )
        updated = 0
        for r in rows:
            sym = (r.symbol or "").upper()
            if not sym:
                continue
            try:
                funda = quote.get_fundamentals_info(sym)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                logger.warning("Fundamentals refresh failed for %s: %s", sym, e)
                continue
            if not funda:
                continue
            changed = False
            for k in FUNDAMENTAL_FIELDS:
                new_val = funda.get(k)
                if new_val is not None:
                    if getattr(r, k, None) != new_val and hasattr(r, k):
                        setattr(r, k, new_val)
                        changed = True
            if changed:
                r.analysis_timestamp = datetime.now(UTC)
                updated += 1
        if updated:
            session.commit()
        res = {"status": "ok", "inspected": len(rows), "updated": updated}
        _set_task_status("market_snapshots_fundamentals_refresh", "ok", res)
        return res
    finally:
        session.close()
