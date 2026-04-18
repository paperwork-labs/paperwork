"""
Typed schemas for AnomalyExplainer inputs and outputs.

Why frozen dataclasses instead of Pydantic here?

* This sub-system runs inside Celery tasks and admin routes; we want the
  smallest possible runtime footprint and zero JSON-schema generation
  cost on every call.
* The wire format from the LLM is parsed into ``dict`` and validated
  manually in :mod:`explainer`; once it lands in our types, it's pure
  Python and never round-tripped over a wire.
* When/if we expose ``Explanation`` over HTTP we can wrap it in a
  Pydantic model on the route side without changing this layer.

Conventions:

* Enums are lower-case snake_case strings so logs and API payloads stay
  greppable.
* ``Decimal`` for confidence (no IEEE-754 surprises in audit logs).
* ``datetime`` values are timezone-aware UTC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0.0"


class AnomalySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AnomalyCategory(str, Enum):
    """Coarse buckets used to retrieve the right runbook section.

    Keep these aligned with the H2 headers in ``docs/MARKET_DATA_RUNBOOK.md``
    and the dimensions returned by ``AdminHealthService.get_composite_health``
    so keyword retrieval can find a relevant chunk every time.
    """

    PIPELINE_FAILURE = "pipeline_failure"
    STALE_SNAPSHOT = "stale_snapshot"
    MONOTONICITY = "monotonicity"
    INDICATOR_OUTLIER = "indicator_outlier"
    BROKER_SYNC = "broker_sync"
    REGIME_MISALIGNMENT = "regime_misalignment"
    COVERAGE_GAP = "coverage_gap"
    OTHER = "other"


@dataclass(frozen=True)
class Anomaly:
    """Operator-side description of a single ops issue.

    Producers (auto_ops, admin_health, alerts) build one of these and pass
    it to :class:`AnomalyExplainer`. Keep ``facts`` flat and JSON-serializable
    so it survives a Redis hop or a Brain webhook payload unchanged.
    """

    id: str
    category: AnomalyCategory
    severity: AnomalySeverity
    title: str
    facts: Dict[str, Any] = field(default_factory=dict)
    raw_evidence: str = ""
    detected_at: Optional[datetime] = None

    def normalized(self) -> "Anomaly":
        """Return a copy with ``detected_at`` filled in and forced to UTC.

        * Missing -> ``datetime.now(timezone.utc)``.
        * Naive   -> assume UTC and attach ``timezone.utc``.
        * Aware non-UTC -> convert to UTC via ``astimezone`` so audit logs
          are comparable across producers (Celery on UTC, dev laptops on
          local tz, Brain webhook payloads, etc.).
        """
        if self.detected_at is None:
            ts = datetime.now(timezone.utc)
        elif self.detected_at.tzinfo is None:
            ts = self.detected_at.replace(tzinfo=timezone.utc)
        elif self.detected_at.tzinfo is timezone.utc:
            return self
        else:
            ts = self.detected_at.astimezone(timezone.utc)
        return Anomaly(
            id=self.id,
            category=self.category,
            severity=self.severity,
            title=self.title,
            facts=dict(self.facts),
            raw_evidence=self.raw_evidence,
            detected_at=ts,
        )


@dataclass(frozen=True)
class RemediationStep:
    """One numbered step in a runbook recommendation."""

    order: int
    description: str
    runbook_section: Optional[str] = None  # e.g. "MARKET_DATA_RUNBOOK.md#stale-snapshots"
    proposed_task: Optional[str] = None  # job_catalog task id, e.g. "tasks.market.refresh_snapshots"
    requires_approval: bool = True
    rationale: Optional[str] = None


@dataclass(frozen=True)
class Explanation:
    """Output of :class:`AnomalyExplainer.explain`.

    ``model`` records which provider produced the narrative so we can
    triage hallucinations later.

    ``confidence`` is the LLM's own self-reported confidence clamped to
    ``[0.0, 1.0]``. For the deterministic fallback path it is set to
    ``Decimal("0.3")`` so dashboards visually distinguish degraded output.
    """

    schema_version: str
    anomaly_id: str
    title: str
    summary: str
    root_cause_hypothesis: str
    narrative: str
    steps: List[RemediationStep]
    confidence: Decimal
    runbook_excerpts: List[str]
    generated_at: datetime
    model: str
    is_fallback: bool = False
