"""Resolve the list of Render services we monitor for G28 deploy-health.

Shared by:
    * ``app.tasks.deploys.poll_deploy_health`` (Beat poller)
    * ``app.api.routes.admin.deploy_health`` (admin API)
    * ``app.services.market.admin_health_service`` (composite health)

Kept in the service layer so the admin-health composite does NOT need to
import a Celery task module (which would drag in ``celery.shared_task`` +
task globals just to parse an env var). See PR #386 review.

Failure modes surfaced (never silenced — ``no-silent-fallback.mdc``):

* ``RENDER_API_KEY`` unset -> :class:`RenderDeployClient.enabled` is
  ``False``; we still return the configured ids with empty slugs so the
  poller can record ``poll_error`` rows, and the admin UI can say
  "deploy telemetry disabled" instead of fake-green.
* Render API error on the metadata lookup -> warning log, empty slug,
  proceed. The row still lands; the slug fills in on the next poll.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import Dict, List

from app.config import settings
from app.services.deploys.render_client import RenderDeployClient

logger = logging.getLogger(__name__)


_SERVICE_META_CACHE: Dict[str, Dict[str, str]] = {}


def _resolve_service_meta(
    client: RenderDeployClient, service_id: str
) -> Dict[str, str]:
    """Return ``{service_id, service_slug, service_type}`` for one service.

    Cached per-process since Render service metadata is effectively static.
    """
    cached = _SERVICE_META_CACHE.get(service_id)
    if cached:
        return cached

    slug = ""
    svc_type = ""
    if client.enabled:
        try:
            payload = client.get_service(service_id)
            slug = str(payload.get("slug") or payload.get("name") or "")
            svc_type = str(payload.get("type") or "")
        except Exception as exc:
            logger.warning(
                "could not resolve metadata for service %s: %s — proceeding with empty slug",
                service_id,
                exc,
            )

    meta = {
        "service_id": service_id,
        "service_slug": slug,
        "service_type": svc_type,
    }
    _SERVICE_META_CACHE[service_id] = meta
    return meta


def configured_service_ids() -> List[str]:
    """Return the raw list of service ids from
    ``DEPLOY_HEALTH_SERVICE_IDS``, stripped and de-blanked."""
    raw = (getattr(settings, "DEPLOY_HEALTH_SERVICE_IDS", "") or "").strip()
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def resolve_services(
    client: RenderDeployClient | None = None,
) -> List[Dict[str, str]]:
    """Read configured service ids and enrich with slug/type.

    ``client`` is injectable so tests can stub out the Render client.
    """
    ids = configured_service_ids()
    if not ids:
        return []

    if client is None:
        client = RenderDeployClient()
    return [_resolve_service_meta(client, sid) for sid in ids]


def reset_cache() -> None:
    """Test helper: clear the per-process metadata cache."""
    _SERVICE_META_CACHE.clear()
