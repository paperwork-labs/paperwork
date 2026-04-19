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
# 10 minutes matches the AutoOps health check cadence; if a dimension
# fails twice inside one window we reuse the previous explanation rather
# than burning another LLM call on the exact same evidence.
DEFAULT_RATE_LIMIT_WINDOW = timedelta(minutes=10)


def _confidence_to_decimal(value: Decimal) -> Decimal:
    """Quantize confidence to the column's Numeric(4, 3) precision."""
    return value.quantize(Decimal("0.001"))


def persist_explanation(
    db: Session,
    explanation: Explanation,
    *,
    anomaly_category: str,
    anomaly_severity: Optional[str] = None,
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
    "DEFAULT_RATE_LIMIT_WINDOW",
    "count_recent",
    "explanation_row_to_payload",
    "latest_for_anomaly",
    "list_recent",
    "persist_explanation",
    "recent_explanation_within",
]
