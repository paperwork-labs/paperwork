"""
AutoOps AnomalyExplainer
========================

Operator-facing AgentBrain feature that turns a structured ``Anomaly``
(failed pipeline run, stale snapshot, monotonicity break, broker-sync
error, indicator outlier, ...) into a typed ``Explanation`` containing:

* A short human title and 1-2 sentence summary.
* A root-cause hypothesis grounded in the anomaly's facts.
* A numbered ``RemediationStep`` list, each one referencing a runbook
  section and / or a Celery task slug from ``job_catalog`` so a one-click
  "fix this" UI can execute it.
* Markdown narrative, model name, and a ``confidence`` score.
* The runbook excerpts the LLM was grounded on (transparency).

Design choices (do NOT change without bumping ``SCHEMA_VERSION``):

* ``LLMProvider`` is a Protocol so the explainer can be tested without
  hitting OpenAI and so we can swap providers (Anthropic, local, etc.)
  without touching the explainer.
* If the LLM call fails or returns malformed JSON, we degrade to a
  deterministic rule-based ``_fallback_explanation`` rather than crash.
  AutoOps must never block the operator just because OpenAI is down.
* Knowledge retrieval is a simple keyword scorer over chunked
  ``MARKET_DATA_RUNBOOK.md``. Embeddings/RAG can replace it later
  behind the same ``RunbookKnowledge`` interface.

This package is a *standalone scaffold*. Integration with the existing
``auto_remediate_health`` task in ``app/tasks/ops/auto_ops.py`` is
deliberately out of scope for this PR -- that path is a danger-zone
adjacent file and gets a separate, smaller PR once this is reviewed.

medallion: ops
"""

from .anomaly_builder import (
    anomaly_from_dict,
    anomaly_to_dict,
    build_anomalies_from_health,
    build_anomaly_from_dimension,
    deterministic_id,
)
from .factory import build_default_explainer, get_runbook
from .knowledge import RunbookChunk, RunbookKnowledge, load_runbook_chunks
from .openai_provider import OpenAIChatProvider
from .persistence import (
    DAILY_EXPLANATION_CAP_PER_KEY,
    DEFAULT_RATE_LIMIT_WINDOW,
    MAX_RATE_LIMIT_WINDOW,
    MIN_RATE_LIMIT_WINDOW,
    clamp_rate_limit_window,
    count_recent,
    explanation_count_today_for_key,
    explanation_row_to_payload,
    latest_for_anomaly,
    latest_for_dimension_key,
    list_recent,
    persist_explanation,
    recent_explanation_within,
)
from .provider import (
    LLMProvider,
    LLMProviderError,
    LLMProviderRateLimitedError,
    StubLLMProvider,
)
from .schemas import (
    SCHEMA_VERSION,
    Anomaly,
    AnomalyCategory,
    AnomalySeverity,
    Explanation,
    RemediationStep,
)
from .explainer import AnomalyExplainer, explanation_to_dict

__all__ = [
    "DAILY_EXPLANATION_CAP_PER_KEY",
    "DEFAULT_RATE_LIMIT_WINDOW",
    "MAX_RATE_LIMIT_WINDOW",
    "MIN_RATE_LIMIT_WINDOW",
    "clamp_rate_limit_window",
    "explanation_count_today_for_key",
    "SCHEMA_VERSION",
    "Anomaly",
    "AnomalyCategory",
    "AnomalyExplainer",
    "AnomalySeverity",
    "Explanation",
    "LLMProvider",
    "LLMProviderError",
    "LLMProviderRateLimitedError",
    "OpenAIChatProvider",
    "RemediationStep",
    "RunbookChunk",
    "RunbookKnowledge",
    "StubLLMProvider",
    "anomaly_from_dict",
    "anomaly_to_dict",
    "build_anomalies_from_health",
    "build_anomaly_from_dimension",
    "build_default_explainer",
    "count_recent",
    "deterministic_id",
    "explanation_row_to_payload",
    "explanation_to_dict",
    "get_runbook",
    "latest_for_anomaly",
    "latest_for_dimension_key",
    "list_recent",
    "load_runbook_chunks",
    "persist_explanation",
    "recent_explanation_within",
]
