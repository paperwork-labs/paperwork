"""Poll Render deploy status every 5 minutes and persist events.

G28 deploy-health guardrail (D120). Reads
:data:`backend.config.settings.DEPLOY_HEALTH_SERVICE_IDS` for the list of
Render service ids to monitor (comma-separated env var), looks up slug +
type via ``RenderDeployClient.get_service`` the first time we observe
each service, then calls :func:`poll_and_record`.

Why a fixed 5-min cadence (rather than polling only after push events):

1. Render does not notify us on build failure; the Render webhook would
   require a public endpoint and HMAC verification work we haven't done
   yet — polling is simpler and the query cost is trivial (<= 4 API calls
   per 5 min, well under the 300 req/min limit).
2. The 2026-04-20 midnight-merge-storm showed 7 failures clustered
   across ~80 minutes. A 5-minute cadence catches every transition
   without building an ingest pipeline.

Failure modes are surfaced — never silenced (``no-silent-fallback.mdc``):

* RENDER_API_KEY unset -> poll_error rows so the admin dim can say
  "deploy telemetry disabled".
* Render API error -> poll_error rows per failing service.
* DB write failure -> exception bubbles; Celery retries.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from app.database import SessionLocal
from app.services.deploys import poll_and_record
from app.services.deploys.service_resolver import resolve_services
from app.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.deploys.poll_deploy_health.poll_deploy_health",
    soft_time_limit=60,
    time_limit=90,
)
@task_run("deploy_health_poll")
def poll_deploy_health() -> dict[str, Any]:
    """Beat-driven task: poll Render deploy state and upsert events.

    Returns the counter dict from :func:`poll_and_record` so JobRun
    rows show ``inserted`` / ``skipped`` / ``poll_errors`` and
    ``services_polled`` at a glance.
    """
    services = resolve_services()
    if not services:
        logger.info("poll_deploy_health: no services configured — skipping")
        return {
            "services_polled": 0,
            "events_inserted": 0,
            "events_skipped": 0,
            "poll_errors": 0,
            "details": [],
        }

    session = SessionLocal()
    try:
        result = poll_and_record(session, services)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
