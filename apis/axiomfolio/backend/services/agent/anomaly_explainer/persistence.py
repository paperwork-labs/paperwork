"""
Persistence helpers for AnomalyExplainer outputs.

Wraps :class:`backend.models.auto_ops_explanation.AutoOpsExplanation` so
the Celery task and admin route share the same write path (rate
limiting, denormalized columns, audit-friendly logging) and never
duplicate the Decimal/JSON conversion logic.

Why a service module instead of putting this on the model:

* The model is a thin SQLAlchemy class -- keeping it free of business
  logic (rate-limit windows, dict shape conventions) makes it easy to
  read in code review.
* Routes and Celery tasks pass already-built :class:`Explanation`
  objects; the conversion to columns happens in exactly one place.

medallion: ops
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.models.auto_ops_explanation import AutoOpsExplanation

from .explainer import explanation_to_dict
from .schemas import Explanation

logger = logging.getLogger(__name__)

# Default rate-limit window for ``recent_explanation_within`` lookups.
# One hour: aligns with a longer de-dupe window so repeated AutoOps
# health checks in the same hour reuse one explanation and reduce spend.
DEFAULT_RATE_LIMIT_WINDOW = timedelta(hours=1)

# Max AutoOps LLM rows per health dimension (anomaly_id prefix) per UTC day
# after the rate-window short-circuit. Prevents a flapping runbook from
# burning 3+ fresh rows for the same dimension in 24h.
DAILY_EXPLANATION_CAP_PER_KEY = 3

# Guardrails for ``recent_explanation_within(..., window=...)`` overrides.
MIN_RATE_LIMIT_WINDOW = timedelta(minutes=1)
MAX_RATE_LIMIT_WINDOW = timedelta(hours=24)


def clamp_rate_limit_window(window: timedelta) -> timedelta:
    """Keep ad-hoc rate-limit windows within a safe, finite range."""
    if window < MIN_RATE_LIMIT_WINDOW:
        return MIN_RATE_LIMIT_WINDOW
    if window > MAX_RATE_LIMIT_WINDOW:
        return MAX_RATE_LIMIT_WINDOW
    return window


def _confidence_to_decimal(value: Decimal) -> Decimal:
    """Quantize confidence to the column's Numeric(4, 3) precision."""
    return value.quantize(Decimal("0.001"))


def persist_explanation(
    db: Session,
    explanation: Explanation,
    *,
    anomaly_category: str,
    anomaly_severity: Optional[str] = None,
    user_id: Optional[int] = None,
) -> AutoOpsExplanation:
    """Insert one :class:`Explanation` and return the stored row.

    The caller controls commit scope -- we ``flush`` so the row gets an
    id but never commit on the caller's behalf (engineering.mdc DB
    sessions convention).

    ``anomaly_severity`` is an optional override used by the Celery task
    when it doesn't have the original :class:`Anomaly` object handy
    (e.g. when re-persisting a payload received from another producer).
    The :class:`Explanation` itself doesn't carry severity, so this
    parameter keeps the denormalized column accurate.
    """
    payload = explanation_to_dict(explanation)
    severity = (
        anomaly_severity
        or payload.get("severity")
        or "warning"
    )
    severity = str(severity).strip().lower() or "warning"

    row = AutoOpsExplanation(
        schema_version=explanation.schema_version,
        anomaly_id=explanation.anomaly_id,
        category=anomaly_category,
        severity=severity,
        title=explanation.title[:255],
        summary=explanation.summary,
        confidence=_confidence_to_decimal(explanation.confidence),
        is_fallback=explanation.is_fallback,
        model=explanation.model[:64],
        payload_json=payload,
        generated_at=explanation.generated_at,
        user_id=user_id,
    )
    db.add(row)
    db.flush()
    logger.info(
        "auto_ops_explanation persisted id=%s anomaly_id=%s "
        "category=%s severity=%s confidence=%s fallback=%s model=%s",
        row.id,
        row.anomaly_id,
        row.category,
        row.severity,
        row.confidence,
        row.is_fallback,
        row.model,
    )
    return row

def latest_for_anomaly(
    db: Session, anomaly_id: str
) -> Optional[AutoOpsExplanation]:
    """Most recent explanation for one anomaly id, or ``None``."""
    return (
        db.query(AutoOpsExplanation)
        .filter(AutoOpsExplanation.anomaly_id == anomaly_id)
        .order_by(desc(AutoOpsExplanation.generated_at))
        .limit(1)
        .first()
    )


def latest_for_dimension_key(
    db: Session,
    anomaly_id: str,
) -> Optional[AutoOpsExplanation]:
    """Most recent row for any anomaly id sharing this dimension key prefix.

    Uses the same ``prefix:%`` grouping as :func:`explanation_count_today_for_key`
    so daily-cap / 429 skip paths can reuse a sibling explanation when the
    current id has no row yet.
    """
    prefix, _, rest = anomaly_id.partition(":")
    if not rest:
        return None
    pattern = f"{prefix}:%"
    return (
        db.query(AutoOpsExplanation)
        .filter(AutoOpsExplanation.anomaly_id.like(pattern))
        .order_by(desc(AutoOpsExplanation.generated_at))
        .limit(1)
        .first()
    )


def explanation_count_today_for_key(
    db: Session,
    anomaly_id: str,
    *,
    now: Optional[datetime] = None,
) -> int:
    """Count persisted explanations in the current UTC day for this key.

    The key is the ``dimension`` segment of
    ``{dimension}:{status}:{day}:{hash}`` ids from
    :func:`anomaly_builder.deterministic_id`, i.e. the prefix before the
    first ``:``. Caps apply per dimension+day, not per full anomaly_id.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    prefix, _, rest = anomaly_id.partition(":")
    if not rest:
        return 0
    pattern = f"{prefix}:%"
    n = int(
        db.query(func.count(AutoOpsExplanation.id))
        .filter(
            AutoOpsExplanation.anomaly_id.like(pattern),
            AutoOpsExplanation.generated_at >= start,
        )
        .scalar()
        or 0
    )
    return n


def recent_explanation_within(
    db: Session,
    anomaly_id: str,
    *,
    window: timedelta = DEFAULT_RATE_LIMIT_WINDOW,
    now: Optional[datetime] = None,
) -> Optional[AutoOpsExplanation]:
    """Return the most recent explanation if it's inside ``window``.

    Used by the Celery task to short-circuit a redundant LLM call when a
    flapping dimension fires multiple anomalies in a short window.
    """
    now = now or datetime.now(timezone.utc)
    window = clamp_rate_limit_window(window)
    cutoff = now - window
    return (
        db.query(AutoOpsExplanation)
        .filter(
            AutoOpsExplanation.anomaly_id == anomaly_id,
            AutoOpsExplanation.generated_at >= cutoff,
        )
        .order_by(desc(AutoOpsExplanation.generated_at))
        .limit(1)
        .first()
    )


def list_recent(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    fallback_only: Optional[bool] = None,
) -> List[AutoOpsExplanation]:
    """Paginated list for the admin UI.

    Filters are optional; ``fallback_only`` lets the UI surface degraded
    explanations (LLM down, fallback steps used) for triage.
    """
    q = db.query(AutoOpsExplanation).order_by(desc(AutoOpsExplanation.generated_at))
    if category:
        q = q.filter(AutoOpsExplanation.category == category)
    if severity:
        q = q.filter(AutoOpsExplanation.severity == severity.strip().lower())
    if fallback_only is True:
        q = q.filter(AutoOpsExplanation.is_fallback.is_(True))
    elif fallback_only is False:
        q = q.filter(AutoOpsExplanation.is_fallback.is_(False))
    return q.offset(max(0, offset)).limit(max(1, min(limit, 200))).all()


def count_recent(
    db: Session,
    *,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    fallback_only: Optional[bool] = None,
) -> int:
    """Total count for the admin UI's pagination footer."""
    q = db.query(func.count(AutoOpsExplanation.id))
    if category:
        q = q.filter(AutoOpsExplanation.category == category)
    if severity:
        q = q.filter(AutoOpsExplanation.severity == severity.strip().lower())
    if fallback_only is True:
        q = q.filter(AutoOpsExplanation.is_fallback.is_(True))
    elif fallback_only is False:
        q = q.filter(AutoOpsExplanation.is_fallback.is_(False))
    return int(q.scalar() or 0)


def explanation_row_to_payload(row: AutoOpsExplanation) -> dict:
    """API-friendly dict for an :class:`AutoOpsExplanation` row.

    Centralized so the route handler and the Celery wiring stay in sync.
    """
    return {
        "id": row.id,
        "schema_version": row.schema_version,
        "anomaly_id": row.anomaly_id,
        "category": row.category,
        "severity": row.severity,
        "title": row.title,
        "summary": row.summary,
        "confidence": str(row.confidence),
        "is_fallback": bool(row.is_fallback),
        "model": row.model,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "payload": row.payload_json,
    }


__all__ = [
    "DAILY_EXPLANATION_CAP_PER_KEY",
    "DEFAULT_RATE_LIMIT_WINDOW",
    "MAX_RATE_LIMIT_WINDOW",
    "MIN_RATE_LIMIT_WINDOW",
    "clamp_rate_limit_window",
    "explanation_count_today_for_key",
    "count_recent",
    "explanation_row_to_payload",
    "latest_for_anomaly",
    "latest_for_dimension_key",
    "list_recent",
    "persist_explanation",
    "recent_explanation_within",
]
