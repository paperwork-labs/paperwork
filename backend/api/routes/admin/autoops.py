"""
AutoOps Anomaly Explainer Routes
================================

Admin-only HTTP surface for the AnomalyExplainer pipeline:

* ``GET  /api/v1/admin/agent/explanations`` -- paginated list of recent
  explanations (sortable by category / severity / fallback flag).
* ``GET  /api/v1/admin/agent/explanations/anomaly/{anomaly_id}`` -- the
  most recent explanation for one anomaly id (used by the dimension
  detail panel in SystemStatus).
* ``POST /api/v1/admin/agent/explain`` -- generate (or reuse, if inside
  the rate-limit window) an explanation for an anomaly the operator
  builds in the UI from a composite-health dimension.

Why a dedicated module instead of folding into ``agent.py``?

* ``agent.py`` is already the largest admin route module
  (AgentAction approvals, autonomy settings, session summaries). Adding
  another four endpoints there would obscure both halves.
* The explainer routes share zero state with the AgentAction model;
  separating them keeps the import graph small and makes the wiring
  obvious to a code reviewer.

Mounting: this router gets included by ``backend.api.routes.admin``
under the same ``/api/v1/admin`` prefix as ``agent_router``. Path
prefix here is ``/agent`` so the URLs above land in the existing admin
agent namespace.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.api.dependencies import get_admin_user, get_db
from backend.models import User
from backend.services.agent.anomaly_explainer import (
    AnomalyCategory,
    AnomalySeverity,
    anomaly_to_dict,
    build_anomaly_from_dimension,
    explanation_row_to_payload,
    latest_for_anomaly,
    list_recent,
    count_recent,
)
from backend.tasks.ops.explain_anomaly import explain_anomaly_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class AutoOpsExplanationOut(BaseModel):
    """Wire shape for one persisted AutoOpsExplanation row."""

    model_config = ConfigDict(extra="forbid")

    id: int
    schema_version: str
    anomaly_id: str
    category: str
    severity: str
    title: str
    summary: str
    confidence: str
    is_fallback: bool
    model: str
    generated_at: Optional[str]
    payload: Dict[str, Any]


class AutoOpsExplanationListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    items: List[AutoOpsExplanationOut]


class ExplainDimensionRequest(BaseModel):
    """Build an Anomaly from one composite-health dimension on the fly.

    The frontend's SystemStatus page already polls
    ``/api/v1/market-data/admin/health`` -- it can lift the dimension
    payload straight from that response and POST it here without the
    operator having to construct an anomaly by hand.
    """

    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(
        ..., min_length=1, max_length=64, description="Composite-health dimension name."
    )
    dimension_payload: Dict[str, Any] = Field(
        ..., description="The dimension dict from /market-data/admin/health."
    )


class ExplainAnomalyRequest(BaseModel):
    """Submit a fully-formed Anomaly produced outside the health probe.

    Used by alert webhooks, broker-sync producers, RiskGate rejections,
    and any future producer that builds an Anomaly upstream and wants the
    same explainer pipeline applied.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=128)
    category: AnomalyCategory
    severity: AnomalySeverity
    title: str = Field(..., min_length=1, max_length=200)
    facts: Dict[str, Any] = Field(default_factory=dict)
    raw_evidence: str = Field("", max_length=8000)
    detected_at: Optional[str] = None


@router.get("/explanations", response_model=AutoOpsExplanationListOut)
def list_explanations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None, max_length=64),
    severity: Optional[str] = Query(None, max_length=16),
    fallback_only: Optional[bool] = Query(
        None,
        description="True -> only degraded explanations; False -> only LLM-grounded.",
    ),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> AutoOpsExplanationListOut:
    """Paginated list of recent AnomalyExplainer outputs."""
    rows = list_recent(
        db,
        limit=limit,
        offset=offset,
        category=category,
        severity=severity,
        fallback_only=fallback_only,
    )
    total = count_recent(
        db,
        category=category,
        severity=severity,
        fallback_only=fallback_only,
    )
    return AutoOpsExplanationListOut(
        total=total,
        items=[AutoOpsExplanationOut(**explanation_row_to_payload(r)) for r in rows],
    )


@router.get(
    "/explanations/anomaly/{anomaly_id}",
    response_model=AutoOpsExplanationOut,
)
def get_latest_explanation(
    anomaly_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> AutoOpsExplanationOut:
    """Latest explanation for one anomaly id, or 404 if none persisted."""
    row = latest_for_anomaly(db, anomaly_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No explanation for this anomaly id.")
    return AutoOpsExplanationOut(**explanation_row_to_payload(row))


@router.post("/explain", response_model=AutoOpsExplanationOut)
def explain_now(
    body: ExplainAnomalyRequest,
    _admin: User = Depends(get_admin_user),
) -> AutoOpsExplanationOut:
    """Generate (or reuse, inside the rate-limit window) an explanation now.

    Synchronous: the operator clicks "Explain" in the UI and gets the
    explanation in the response body. The Celery task path remains
    available for fire-and-forget producers; this route is the
    interactive entry point.
    """
    payload = {
        "id": body.id,
        "category": body.category.value,
        "severity": body.severity.value,
        "title": body.title,
        "facts": body.facts,
        "raw_evidence": body.raw_evidence,
        "detected_at": body.detected_at,
    }
    try:
        result = explain_anomaly_sync(payload)
    except Exception:  # noqa: BLE001 - scrubbed 500; full traceback in logs
        logger.exception("autoops explain failed anomaly_id=%s", body.id)
        raise HTTPException(status_code=500, detail="explain failed")
    return AutoOpsExplanationOut(**{k: v for k, v in result.items() if k != "reused"})


@router.post("/explain/dimension", response_model=AutoOpsExplanationOut)
def explain_dimension(
    body: ExplainDimensionRequest,
    _admin: User = Depends(get_admin_user),
) -> AutoOpsExplanationOut:
    """Build an Anomaly from a composite-health dimension and explain it.

    Convenience wrapper around :func:`build_anomaly_from_dimension` so
    the frontend can hand us the raw dimension dict it already has from
    ``/market-data/admin/health`` instead of recomputing severity /
    category mappings on the client.
    """
    anomaly = build_anomaly_from_dimension(body.dimension, body.dimension_payload)
    if anomaly is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dimension {body.dimension!r} is healthy (status="
                f"{body.dimension_payload.get('status')!r}); nothing to explain."
            ),
        )
    payload = anomaly_to_dict(anomaly)
    try:
        result = explain_anomaly_sync(payload)
    except Exception:  # noqa: BLE001 - scrubbed 500; full traceback in logs
        logger.exception("autoops explain failed dimension=%s", body.dimension)
        raise HTTPException(status_code=500, detail="explain failed")
    return AutoOpsExplanationOut(**{k: v for k, v in result.items() if k != "reused"})


__all__ = ["router"]
