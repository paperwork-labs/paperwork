"""Sync cron_schedule DB rows to Render cron-job services.

Reads all CronSchedule rows from PostgreSQL and reconciles them with
the Render API: creates missing crons, updates changed ones, deletes
orphans, and suspends/resumes based on the ``enabled`` flag.

No-op when ``RENDER_API_KEY`` is not configured (local dev / CI).

Usage:
    python -m backend.scripts.sync_render_crons
"""

from __future__ import annotations

import json
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.database import SessionLocal
from backend.services.render_sync_service import render_sync_service

logger = logging.getLogger("sync_render_crons")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    db = SessionLocal()
    try:
        result = render_sync_service.sync_all(db)
        print(json.dumps(result, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
