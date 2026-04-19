"""
Celery task that runs :class:`AnomalyExplainer` and persists the output.

Wired by :mod:`backend.tasks.ops.auto_ops` after the composite-health
check: every non-green dimension is converted into an :class:`Anomaly`
and dispatched here as a fire-and-forget side effect of remediation.
The explanation is *not* on the critical path -- if the LLM is down or
the task crashes, remediation still proceeds.

Why a separate task instead of an inline call:

* LLM latency (200ms -- 5s typical) would inflate the
  ``auto_remediate_health`` task's runtime and crowd the Beat schedule.
* Each anomaly explanation runs independently, so dispatching them as
  separate tasks lets the worker pool fan out across them.
* A bad LLM payload should never block the remediator's success
  metrics; isolating the work isolates the failure modes too.

Idempotency:

* :func:`recent_explanation_within` short-circuits the LLM call when an
  explanation for the same anomaly id already exists inside the rate
  limit window. The window matches the AutoOps cadence so a flapping
  dimension only burns one LLM call per visit.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

from celery import shared_task

from backend.database import SessionLocal
from backend.services.agent.anomaly_explainer import (
    AnomalyExplainer,
    anomaly_from_dict,
    build_default_explainer,
    explanation_row_to_payload,
    explanation_to_dict,
    persist_explanation,
    recent_explanation_within,
)
from backend.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


def _run_explainer(
    payload: Mapping[str, Any], *, explainer: AnomalyExplainer | None = None
) -> Dict[str, Any]:
    """Pure function so we can drive it from sync routes too.

    Returns the persisted-row payload (matches what the API endpoint
    returns) or, when the rate-limit short-circuit fires, the existing
    row's payload with ``"reused": True`` set so the caller can tell the
    explanation is not freshly generated.
    """
    anomaly = anomaly_from_dict(payload).normalized()
    explainer = explainer or build_default_explainer()

    db = SessionLocal()
    try:
        existing = recent_explanation_within(db, anomaly.id)
        if existing is not None:
            out = explanation_row_to_payload(existing)
            out["reused"] = True
            return out

        explanation = explainer.explain(anomaly)
        row = persist_explanation(
            db,
            explanation,
            anomaly_category=anomaly.category.value,
            anomaly_severity=anomaly.severity.value,
        )
        db.commit()
        out = explanation_row_to_payload(row)
        out["reused"] = False
        return out
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@shared_task(
    name="backend.tasks.ops.explain_anomaly.explain_anomaly",
    soft_time_limit=30,
    time_limit=60,
    autoretry_for=(),  # never retry: a degraded LLM should hit the fallback path inside .explain()
)
@task_run("auto_ops_explain_anomaly")
def explain_anomaly(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build, persist, and return one AnomalyExplanation.

    Accepts the dict produced by
    :func:`backend.services.agent.anomaly_explainer.anomaly_to_dict`.
    Always returns a JSON-serializable dict so downstream consumers
    (callers triggering it via ``.delay().get()`` in tests, future Brain
    webhook fanout, ...) can rely on the same shape as the REST route.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("explain_anomaly requires a dict payload")
    try:
        return _run_explainer(payload)
    except Exception as exc:  # noqa: BLE001 - log + bubble so Celery records the failure
        logger.exception(
            "explain_anomaly failed for anomaly=%s: %s",
            payload.get("id"),
            exc,
        )
        raise


def explain_anomaly_sync(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Synchronous variant for FastAPI routes that want an inline result.

    Mirrors :func:`explain_anomaly` but skips the Celery wrapping so
    routes can return a typed JSON response without an extra hop.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("explain_anomaly_sync requires a dict payload")
    return _run_explainer(payload)


__all__ = [
    "explain_anomaly",
    "explain_anomaly_sync",
]


# Re-export ``explanation_to_dict`` so callers that import the task
# module also get the canonical serializer in one place.
explanation_to_dict = explanation_to_dict  # noqa: F401 - intentional re-export
