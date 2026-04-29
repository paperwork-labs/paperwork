"""Pydantic schemas for anomaly_alerts/v1 — WS-50 anomaly detection.

Matches the shape of ``apis/brain/data/anomaly_alerts.json``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

_DESCRIPTION = (
    "Anomalies detected by the anomaly detection service. Z-score-based with rolling 7d baseline."
)


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class Direction(StrEnum):
    above = "above"
    below = "below"


class AnomalyAlert(BaseModel):
    id: str = Field(..., description="Unique alert ID — format alert-<ISO8601>-<metric-slug>")
    metric: str = Field(..., description="Dotted metric key, e.g. dora.deploy_frequency_per_week")
    value: float = Field(..., description="Observed metric value at detection time")
    baseline_mean: float = Field(..., description="Rolling 7d mean used as the baseline")
    baseline_stddev: float = Field(..., description="Rolling 7d stddev used as the baseline")
    z_score: float = Field(
        ..., description="(value - mean) / stddev; negative means below baseline"
    )
    direction: Direction
    severity: Severity
    detected_at: str = Field(..., description="RFC 3339 UTC timestamp of detection")
    resolved_at: str | None = Field(
        None, description="RFC 3339 UTC timestamp when resolved, or null"
    )
    context: str = Field(..., description="Human-readable summary of the anomaly")

    @property
    def detected_at_dt(self) -> datetime:
        s = self.detected_at
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)

    @property
    def resolved_at_dt(self) -> datetime | None:
        if self.resolved_at is None:
            return None
        s = self.resolved_at
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)


class AnomalyAlertsFile(BaseModel):
    schema_: str = Field("anomaly_alerts/v1", alias="schema")
    description: str = Field(_DESCRIPTION)
    alerts: list[AnomalyAlert] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
