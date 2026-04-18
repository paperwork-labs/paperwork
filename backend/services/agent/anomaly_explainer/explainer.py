"""
AnomalyExplainer orchestrator.

Wires together the LLM provider, runbook knowledge, prompt templates, and
JSON-schema validation into a single :meth:`AnomalyExplainer.explain`
call that operators can trust to either:

1. Return a high-quality LLM-generated explanation, or
2. Return a deterministic fallback explanation marked
   ``is_fallback=True`` so the UI can show a "degraded" badge.

It NEVER raises in normal operation. Producers (Celery tasks, admin
routes) can call it inside an ``except`` of their own and forward the
``Explanation`` to alerting / Brain webhooks / dashboards without an
extra try/except wrapper.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional

from .knowledge import (
    EMPTY_KNOWLEDGE,
    RunbookChunk,
    RunbookKnowledge,
    query_text_for_anomaly,
)
from .prompts import OUTPUT_JSON_SCHEMA, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .provider import LLMProvider, LLMProviderError
from .schemas import (
    SCHEMA_VERSION,
    Anomaly,
    AnomalyCategory,
    AnomalySeverity,
    Explanation,
    RemediationStep,
)

logger = logging.getLogger(__name__)

_FALLBACK_CONFIDENCE = Decimal("0.30")
_DEFAULT_MAX_STEPS = 12

# Per-category scripted fallback steps. These are intentionally conservative
# (read-only diagnostics first, mutations require approval) so AutoOps can
# never "auto-remediate" something destructive while degraded.
_FALLBACK_STEPS_BY_CATEGORY: Dict[AnomalyCategory, List[Dict[str, Any]]] = {
    AnomalyCategory.PIPELINE_FAILURE: [
        {
            "description": (
                "Inspect the failed JobRun row and read the full traceback. "
                "Confirm whether the failure is transient (timeout, broker rate "
                "limit) or a code/data bug."
            ),
            "runbook_section": "MARKET_DATA_RUNBOOK.md#troubleshooting",
            "requires_approval": False,
        },
        {
            "description": (
                "If transient, retry the task once via the admin scheduler. "
                "If it fails again, escalate."
            ),
            "requires_approval": True,
        },
    ],
    AnomalyCategory.STALE_SNAPSHOT: [
        {
            "description": (
                "Check MarketSnapshot.as_of_timestamp for the affected symbols "
                "and compare to the upstream feed's last bar."
            ),
            "runbook_section": "MARKET_DATA_RUNBOOK.md#indicators-show-nullunknown",
            "requires_approval": False,
        },
        {
            "description": (
                "If the upstream feed is current, refresh snapshots for the "
                "affected universe via the admin operator action "
                "'Recompute Indicators (Market Snapshot)'."
            ),
            "requires_approval": True,
        },
    ],
    AnomalyCategory.MONOTONICITY: [
        {
            "description": (
                "Identify the symbols listed in `monotonicity_issues` and "
                "spot-check their MarketSnapshotHistory for out-of-order rows."
            ),
            "runbook_section": "MARKET_DATA_RUNBOOK.md#stage_quality-red--high-unknown-rate-or-monotonicity-violations",
            "requires_approval": False,
        },
        {
            "description": (
                "If duplicates or backfill races caused it, reconcile via the "
                "stage-quality repair admin action."
            ),
            "requires_approval": True,
        },
    ],
    AnomalyCategory.BROKER_SYNC: [
        {
            "description": (
                "Verify broker connectivity (FlexQuery token, OAuth refresh, "
                "or session age) before retrying."
            ),
            "runbook_section": "MARKET_DATA_RUNBOOK.md#broker-sync",
            "requires_approval": False,
        },
    ],
    AnomalyCategory.COVERAGE_GAP: [
        {
            "description": (
                "Run the daily-coverage report for the affected universe to "
                "list missing dates and symbols."
            ),
            "requires_approval": False,
        },
        {
            "description": (
                "Backfill the gap via the admin action 'Backfill Daily "
                "Coverage (Tracked)'."
            ),
            "requires_approval": True,
        },
    ],
}

# All other categories share this generic fallback.
_GENERIC_FALLBACK_STEPS: List[Dict[str, Any]] = [
    {
        "description": (
            "Pull the latest composite health JSON from "
            "GET /api/v1/market-data/admin/health and inspect the dimension "
            "this anomaly belongs to."
        ),
        "requires_approval": False,
    },
    {
        "description": (
            "Cross-reference the anomaly facts against the relevant runbook "
            "section before taking any mutating action."
        ),
        "runbook_section": "MARKET_DATA_RUNBOOK.md#troubleshooting",
        "requires_approval": True,
    },
]


def _to_decimal_confidence(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.5")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.5")
    if d < 0:
        return Decimal("0")
    if d > 1:
        return Decimal("1")
    return d


def _coerce_step(raw: Mapping[str, Any], default_order: int) -> Optional[RemediationStep]:
    description = (raw.get("description") or "").strip()
    if not description:
        return None
    try:
        order = int(raw.get("order", default_order))
    except (TypeError, ValueError):
        order = default_order
    if order < 1:
        order = default_order

    runbook = raw.get("runbook_section")
    if isinstance(runbook, str):
        runbook = runbook.strip() or None
    elif runbook is not None:
        runbook = None

    proposed = raw.get("proposed_task")
    if isinstance(proposed, str):
        proposed = proposed.strip() or None
    elif proposed is not None:
        proposed = None

    rationale = raw.get("rationale")
    if isinstance(rationale, str):
        rationale = rationale.strip() or None
    elif rationale is not None:
        rationale = None

    return RemediationStep(
        order=order,
        description=description[:600],
        runbook_section=runbook,
        proposed_task=proposed,
        requires_approval=_coerce_bool(
            raw.get("requires_approval"), default=True
        ),
        rationale=rationale,
    )


def _coerce_bool(value: Any, *, default: bool) -> bool:
    """Tolerantly coerce LLM output to bool.

    Crucial: ``bool("false")`` is ``True`` in Python, so a literal call to
    ``bool(...)`` here would misread JSON-as-string ``"false"`` payloads as
    requires-approval-True. We accept the JSON canonical bools, the common
    string aliases, and 0/1 ints; anything else falls back to ``default``.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1"}:
            return True
        if normalized in {"false", "no", "n", "0"}:
            return False
    return default


def _build_runbook_block(chunks: List[RunbookChunk]) -> str:
    if not chunks:
        return "(no relevant runbook excerpts found)"
    blocks = []
    for chunk in chunks:
        body = chunk.body
        if len(body) > 1500:
            body = body[:1500].rstrip() + "\n... (truncated)"
        blocks.append(
            f"---\nreference: {chunk.reference()}\nheading: {chunk.heading}\n"
            f"---\n{body}"
        )
    return "\n\n".join(blocks)


class AnomalyExplainer:
    """Build :class:`Explanation` objects for operator anomalies."""

    SCHEMA_VERSION = SCHEMA_VERSION

    def __init__(
        self,
        provider: LLMProvider,
        knowledge: Optional[RunbookKnowledge] = None,
        *,
        available_tasks: Optional[Mapping[str, str]] = None,
        max_runbook_chunks: int = 3,
    ) -> None:
        if provider is None:
            raise ValueError("AnomalyExplainer requires an LLMProvider")
        self.provider = provider
        self.knowledge = knowledge or EMPTY_KNOWLEDGE
        self._available_tasks: Dict[str, str] = dict(available_tasks or {})
        self._max_runbook_chunks = max(0, int(max_runbook_chunks))

    def explain(self, anomaly: Anomaly) -> Explanation:
        anomaly = anomaly.normalized()
        chunks = self._retrieve_chunks(anomaly)
        try:
            raw = self._call_llm(anomaly, chunks)
            payload = self._parse_and_validate(raw)
            return self._build_explanation(anomaly, payload, chunks, is_fallback=False)
        except LLMProviderError as e:
            logger.warning(
                "anomaly_explainer: provider %s failed for %s: %s",
                self.provider.name,
                anomaly.id,
                e,
            )
            return self._fallback_explanation(anomaly, chunks)
        except _MalformedLLMOutput as e:
            logger.warning(
                "anomaly_explainer: provider %s returned malformed output for %s: %s",
                self.provider.name,
                anomaly.id,
                e,
            )
            return self._fallback_explanation(anomaly, chunks)
        except Exception as e:  # noqa: BLE001 -- belt-and-suspenders
            logger.exception(
                "anomaly_explainer: unexpected error for %s: %s",
                anomaly.id,
                e,
            )
            return self._fallback_explanation(anomaly, chunks)

    def _retrieve_chunks(self, anomaly: Anomaly) -> List[RunbookChunk]:
        if self._max_runbook_chunks == 0 or len(self.knowledge) == 0:
            return []
        query = query_text_for_anomaly(
            category=anomaly.category.value,
            title=anomaly.title,
            facts=anomaly.facts,
            raw_evidence=anomaly.raw_evidence,
        )
        return self.knowledge.find_relevant(query, top_k=self._max_runbook_chunks)

    def _call_llm(self, anomaly: Anomaly, chunks: List[RunbookChunk]) -> str:
        anomaly_payload = {
            "id": anomaly.id,
            "category": anomaly.category.value,
            "severity": anomaly.severity.value,
            "title": anomaly.title,
            "facts": anomaly.facts,
            "raw_evidence": anomaly.raw_evidence[:2000],
            "detected_at": anomaly.detected_at.isoformat()
            if anomaly.detected_at
            else None,
        }
        user_prompt = USER_PROMPT_TEMPLATE.format(
            anomaly_json=json.dumps(anomaly_payload, sort_keys=True, default=str),
            available_tasks_json=json.dumps(self._available_tasks, sort_keys=True),
            runbook_block=_build_runbook_block(chunks),
            schema_json=json.dumps(OUTPUT_JSON_SCHEMA, sort_keys=True),
        )
        return self.provider.complete_json(SYSTEM_PROMPT, user_prompt)

    def _parse_and_validate(self, raw: str) -> Dict[str, Any]:
        if not raw or not raw.strip():
            raise _MalformedLLMOutput("empty response")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            raise _MalformedLLMOutput(f"invalid JSON: {e}") from e
        if not isinstance(payload, dict):
            raise _MalformedLLMOutput("top-level value is not an object")
        for key in ("title", "summary", "root_cause_hypothesis", "narrative", "steps"):
            if key not in payload:
                raise _MalformedLLMOutput(f"missing required field: {key}")
        steps = payload.get("steps")
        if not isinstance(steps, list) or not steps:
            raise _MalformedLLMOutput("steps must be a non-empty list")
        if len(steps) > _DEFAULT_MAX_STEPS:
            raise _MalformedLLMOutput(
                f"too many steps ({len(steps)} > {_DEFAULT_MAX_STEPS})"
            )
        return payload

    def _build_explanation(
        self,
        anomaly: Anomaly,
        payload: Dict[str, Any],
        chunks: List[RunbookChunk],
        *,
        is_fallback: bool,
    ) -> Explanation:
        steps_raw = payload.get("steps", [])
        steps: List[RemediationStep] = []
        for idx, step_raw in enumerate(steps_raw, start=1):
            if not isinstance(step_raw, dict):
                continue
            step = _coerce_step(step_raw, default_order=idx)
            if step is None:
                continue
            if (
                step.proposed_task
                and self._available_tasks
                and step.proposed_task not in self._available_tasks
            ):
                # Drop hallucinated task names but keep the step description.
                step = RemediationStep(
                    order=step.order,
                    description=step.description,
                    runbook_section=step.runbook_section,
                    proposed_task=None,
                    requires_approval=step.requires_approval,
                    rationale=step.rationale,
                )
            steps.append(step)

        used_scripted_fallback_steps = False
        if not steps:
            steps = self._fallback_steps(anomaly)
            used_scripted_fallback_steps = True

        confidence = _to_decimal_confidence(payload.get("confidence", 0.5))
        if is_fallback or used_scripted_fallback_steps:
            # If we substituted scripted steps because the LLM's steps were
            # all unusable, this Explanation is no longer fully grounded in
            # the LLM response. Pin the confidence to the fallback level so
            # downstream consumers don't over-trust it.
            confidence = _FALLBACK_CONFIDENCE

        return Explanation(
            schema_version=SCHEMA_VERSION,
            anomaly_id=anomaly.id,
            title=str(payload.get("title") or anomaly.title)[:200],
            summary=str(payload.get("summary") or "")[:500],
            root_cause_hypothesis=str(payload.get("root_cause_hypothesis") or "")[:800],
            narrative=str(payload.get("narrative") or "")[:6000],
            steps=steps,
            confidence=confidence,
            runbook_excerpts=[chunk.reference() for chunk in chunks],
            generated_at=datetime.now(timezone.utc),
            model=self.provider.name,
            is_fallback=is_fallback,
        )

    def _fallback_steps(self, anomaly: Anomaly) -> List[RemediationStep]:
        templates = _FALLBACK_STEPS_BY_CATEGORY.get(
            anomaly.category, _GENERIC_FALLBACK_STEPS
        )
        return [
            RemediationStep(
                order=i,
                description=tpl["description"],
                runbook_section=tpl.get("runbook_section"),
                proposed_task=tpl.get("proposed_task"),
                requires_approval=bool(tpl.get("requires_approval", True)),
                rationale=tpl.get("rationale"),
            )
            for i, tpl in enumerate(templates, start=1)
        ]

    def _fallback_explanation(
        self, anomaly: Anomaly, chunks: List[RunbookChunk]
    ) -> Explanation:
        title = f"[Fallback] {anomaly.title}"
        summary = (
            "AutoOps could not reach the LLM provider; surfacing a "
            "rule-based runbook so the operator can act manually."
        )
        narrative = (
            f"Anomaly `{anomaly.id}` ({anomaly.category.value}, "
            f"severity={anomaly.severity.value}) was detected. The LLM "
            "explainer is degraded -- this is the deterministic fallback "
            "explanation. Follow the steps below and inspect the relevant "
            "runbook section before taking any mutating action."
        )
        return Explanation(
            schema_version=SCHEMA_VERSION,
            anomaly_id=anomaly.id,
            title=title[:200],
            summary=summary,
            root_cause_hypothesis="Unknown -- LLM unavailable.",
            narrative=narrative,
            steps=self._fallback_steps(anomaly),
            confidence=_FALLBACK_CONFIDENCE,
            runbook_excerpts=[chunk.reference() for chunk in chunks],
            generated_at=datetime.now(timezone.utc),
            model=self.provider.name,
            is_fallback=True,
        )


class _MalformedLLMOutput(ValueError):
    """Internal signal that the LLM payload didn't pass our schema gate."""


def explanation_to_dict(exp: Explanation) -> Dict[str, Any]:
    """Serialize an :class:`Explanation` to a JSON-friendly dict.

    Convenience for routes/Celery tasks that need to push the result over
    the wire. Keeps Decimal -> string conversion in one place so consumers
    never see a `TypeError: Object of type Decimal is not JSON serializable`.
    """
    payload = asdict(exp)
    payload["confidence"] = str(exp.confidence)
    payload["generated_at"] = exp.generated_at.isoformat()
    payload["steps"] = [asdict(step) for step in exp.steps]
    return payload
