"""Celery task: generate trade candidates from latest market snapshots.

Runs after the nightly market data pipeline so generators read the
freshest indicator state. Persists ``Candidate`` rows for the validator
queue and returns a structured report consumed by the dashboard.

Per ``engineering.mdc``:

* Time limits matched to the entry in ``backend/tasks/job_catalog.py``.
* Caller controls the session boundary; this task owns its own
  ``SessionLocal`` since it is a top-level Celery entry point, but it
  passes the same session into the generator framework and commits
  exactly once on success.
* No silent ``except``: failures surface in the report and via logging.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from backend.database import SessionLocal
from backend.tasks.celery_app import celery_app
from backend.tasks.utils.task_utils import task_run

# Importing the generators package registers concrete generators with
# the registry via ``__init_subclass__``. Keep this import even if it
# looks unused.
from backend.services.picks import generators  # noqa: F401
from backend.services.picks.candidate_generator import (
    GeneratorRunReport,
    registered_generators,
    run_all_generators,
)


logger = logging.getLogger(__name__)


@celery_app.task(
    name="backend.tasks.picks.generate_candidates",
    soft_time_limit=540,
    time_limit=600,
    queue="celery",
)
@task_run("generate_candidates")
def generate_candidates_task(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Run all (or named) candidate generators and persist their output.

    Returns a JSON-serializable summary suitable for ``JobRun.result``.
    """
    db = SessionLocal()
    try:
        registered = [c.name for c in registered_generators()]
        if not registered:
            logger.warning("no candidate generators registered; nothing to run")
            return {
                "status": "ok",
                "registered": [],
                "reports": [],
                "summary": {"created": 0, "skipped_duplicate": 0, "invalid": 0, "errors": 0},
            }

        reports: List[GeneratorRunReport] = run_all_generators(db, only=only)
        summary = _summarise(reports)

        # One commit at the end keeps the run atomic for any single
        # generator: persist_candidates flushes per generator, and we
        # commit once. If commit fails we roll back everything (the
        # validator queue is far better off seeing nothing than a
        # partial set).
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("commit failed; rolling back all generator output")
            raise

        logger.info(
            "candidate generation complete: %s",
            {k: v for k, v in summary.items()},
        )
        return {
            "status": "ok",
            "registered": registered,
            "reports": [r.to_dict() for r in reports],
            "summary": summary,
        }
    finally:
        db.close()


def _summarise(reports: Sequence[GeneratorRunReport]) -> Dict[str, int]:
    out = {"created": 0, "skipped_duplicate": 0, "invalid": 0, "errors": 0}
    for r in reports:
        out["created"] += r.created
        out["skipped_duplicate"] += r.skipped_duplicate
        out["invalid"] += r.invalid
        if r.error:
            out["errors"] += 1
    return out
