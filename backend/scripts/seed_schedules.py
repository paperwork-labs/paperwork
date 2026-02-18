"""Seed cron_schedule table from the job catalog.

Idempotent — inserts missing entries and updates catalog-managed fields
(display_name, description, group, task) only for rows with created_by
== 'catalog_seed'. Admin-created or admin-customized rows are skipped.
Runtime fields (cron, enabled, timezone) are never overwritten.
Safe to call on every deploy.

Usage:
    python -m backend.scripts.seed_schedules
"""

from __future__ import annotations

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.database import SessionLocal
from backend.models.market_data import CronSchedule
from backend.tasks.job_catalog import CATALOG

logger = logging.getLogger("seed_schedules")

_CATALOG_MANAGED_FIELDS = ("display_name", "description", "group", "task")


def seed(db_session=None) -> dict[str, int]:
    own_session = db_session is None
    db = db_session or SessionLocal()
    try:
        existing: dict[str, CronSchedule] = {
            row.id: row for row in db.query(CronSchedule).all()
        }
        seeded = 0
        updated = 0
        skipped_customized = 0
        for tmpl in CATALOG:
            if tmpl.id not in existing:
                row = CronSchedule(
                    id=tmpl.id,
                    display_name=tmpl.display_name,
                    group=tmpl.group,
                    task=tmpl.task,
                    description=tmpl.description,
                    cron=tmpl.default_cron,
                    timezone=tmpl.default_tz,
                    args_json=tmpl.args or [],
                    kwargs_json=tmpl.kwargs or {},
                    enabled=True,
                    timeout_s=tmpl.timeout_s,
                    singleflight=tmpl.singleflight,
                    created_by="catalog_seed",
                )
                db.add(row)
                seeded += 1
            else:
                row = existing[tmpl.id]
                # Avoid clobbering admin-customized labels/metadata.
                if row.created_by and row.created_by != "catalog_seed":
                    skipped_customized += 1
                    continue
                changed = False
                for field in _CATALOG_MANAGED_FIELDS:
                    catalog_val = getattr(tmpl, field)
                    if getattr(row, field) != catalog_val:
                        setattr(row, field, catalog_val)
                        changed = True
                if changed:
                    updated += 1
        db.commit()
        result = {
            "seeded": seeded,
            "updated": updated,
            "unchanged": len(existing) - updated - skipped_customized,
            "skipped_customized": skipped_customized,
        }
        logger.info("Schedule seed complete: %s", result)
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = seed()
    print(
        f"Seed: {result['seeded']} new, {result['updated']} updated, "
        f"{result['unchanged']} unchanged, {result['skipped_customized']} customized skipped"
    )
