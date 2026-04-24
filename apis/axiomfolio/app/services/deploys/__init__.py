"""Deploy-health subsystem.

G28 deploy-health guardrail (see ``docs/plans/GAPS_2026Q2.md`` and D120).

Public surface kept small on purpose: routes, tasks, and the composite
health builder import ``RenderDeployClient`` + ``poll_and_record`` from
here. The Beat-driven poller lives in :mod:`app.tasks.deploys`.

medallion: ops
"""

from __future__ import annotations

from .poll_service import poll_and_record, summarize_service_health
from .render_client import (
    DeployRecord,
    RenderDeployClient,
    RenderDeployClientError,
)

__all__ = [
    "DeployRecord",
    "RenderDeployClient",
    "RenderDeployClientError",
    "poll_and_record",
    "summarize_service_health",
]
