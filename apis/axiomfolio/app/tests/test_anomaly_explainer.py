"""
Tests for the AutoOps AnomalyExplainer.

Goals:

* Prove the orchestrator handles every failure mode of the LLM gracefully
  (provider error, malformed JSON, missing fields, hallucinated task slugs).
* Prove the keyword retriever returns deterministic, score-ordered results.
* Prove the markdown chunker handles edge cases (no H2, top-level body,
  empty sections, missing files).
* Lock in the JSON schema and SCHEMA_VERSION so an accidental contract
  bump fails CI.

All tests run without DB, network, or environment variables -- they only
touch the in-memory dataclasses, the stub LLM, and a tmp markdown file.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.services.agent.anomaly_explainer import (
    SCHEMA_VERSION,
    Anomaly,
    AnomalyCategory,
    AnomalyExplainer,
    AnomalySeverity,
    LLMProviderError,
    RunbookKnowledge,
    StubLLMProvider,
    load_runbook_chunks,
)
from app.services.agent.anomaly_explainer.explainer import (
    _to_decimal_confidence,
    explanation_to_dict,
)
from app.services.agent.anomaly_explainer.knowledge import (
    _slugify_anchor,
    query_text_for_anomaly,
)
from app.services.agent.anomaly_explainer.prompts import OUTPUT_JSON_SCHEMA
from app.services.agent.anomaly_explainer.provider import AlwaysFailingProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _good_payload(
    *,
    title: str = "Stage monotonicity broke for 3 symbols",
    confidence: float = 0.8,
    steps: list[dict[str, Any]] | None = None,
) -> str:
    # Use ``is None`` (not ``or``) so callers can pass ``steps=[]`` and
    # actually exercise the empty-steps -> fallback path. The previous
    # ``steps or [...]`` form silently substituted defaults for empty lists,
    # which masked the test on main and broke it once the test ran for
    # real on PR #321.
    if steps is None:
        steps = [
            {
                "order": 1,
                "description": "Inspect MarketSnapshotHistory for duplicates.",
                "runbook_section": "MARKET_DATA_RUNBOOK.md#stage-monotonicity",
                "proposed_task": None,
                "requires_approval": False,
                "rationale": "Read-only diagnostic.",
            },
            {
                "order": 2,
                "description": "Run the stage-quality repair admin action.",
                "runbook_section": None,
                "proposed_task": "tasks.admin.repair_stage_history",
                "requires_approval": True,
                "rationale": None,
            },
        ]
    return json.dumps(
        {
            "title": title,
            "summary": "Three symbols have out-of-order MarketSnapshotHistory rows.",
            "root_cause_hypothesis": "Concurrent backfill overwrote a row.",
            "narrative": "Detail paragraph here.",
            "confidence": confidence,
            "steps": steps,
        }
    )


def _anomaly(
    *,
    cat: AnomalyCategory = AnomalyCategory.MONOTONICITY,
    severity: AnomalySeverity = AnomalySeverity.WARNING,
    title: str = "monotonicity_issues=3",
    facts: dict[str, Any] | None = None,
    raw: str = "AAPL out of order at 2026-04-08",
) -> Anomaly:
    return Anomaly(
        id=f"{cat.value}:test",
        category=cat,
        severity=severity,
        title=title,
        facts=facts or {"affected_symbols": ["AAPL", "MSFT", "GOOG"]},
        raw_evidence=raw,
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_schema_version_locked(self):
        # Bumping this constant is a wire-breaking change; force a deliberate
        # update to the test (and to docs/KNOWLEDGE.md per repo policy).
        assert SCHEMA_VERSION == "1.0.0"

    def test_anomaly_normalized_fills_utc(self):
        a = _anomaly()
        n = a.normalized()
        assert n.detected_at is not None
        assert n.detected_at.tzinfo is not None
        # Idempotent
        assert n.normalized() is n or n.normalized().detected_at == n.detected_at


# ---------------------------------------------------------------------------
# Knowledge / chunker
# ---------------------------------------------------------------------------


class TestChunker:
    def test_h2_chunks_extracted(self, tmp_path: Path):
        md = tmp_path / "rb.md"
        md.write_text(
            "# Title\nIntro line.\n\n"
            "## Stale Snapshots\nWhat to do when snapshots are stale.\n\n"
            "## Stage Monotonicity\nWhat to do when monotonicity breaks.\n",
            encoding="utf-8",
        )
        chunks = load_runbook_chunks(md)
        assert len(chunks) == 3  # Overview + 2 sections
        headings = [c.heading for c in chunks]
        assert headings == ["Overview", "Stale Snapshots", "Stage Monotonicity"]
        assert chunks[1].anchor == "stale-snapshots"
        assert chunks[2].anchor == "stage-monotonicity"
        assert chunks[1].reference() == "rb.md#stale-snapshots"

    def test_missing_file_returns_empty(self, tmp_path: Path):
        chunks = load_runbook_chunks(tmp_path / "does-not-exist.md")
        assert chunks == []

    def test_empty_section_dropped(self, tmp_path: Path):
        md = tmp_path / "rb.md"
        md.write_text("## Empty\n\n## Real\nbody\n", encoding="utf-8")
        chunks = load_runbook_chunks(md)
        # Empty section is dropped, only "Real" survives.
        assert [c.heading for c in chunks] == ["Real"]

    def test_no_h2_yields_overview_only(self, tmp_path: Path):
        md = tmp_path / "rb.md"
        md.write_text("# Top\nflat body\n", encoding="utf-8")
        chunks = load_runbook_chunks(md)
        assert len(chunks) == 1
        assert chunks[0].heading == "Overview"

    def test_slugify_handles_punctuation(self):
        assert _slugify_anchor("Stale Snapshots!") == "stale-snapshots"
        assert _slugify_anchor("  ") == "section"
        assert _slugify_anchor("ASCII / Unicode #1") == "ascii--unicode-1"


class TestKnowledgeRetrieval:
    def _kb(self, tmp_path: Path) -> RunbookKnowledge:
        md = tmp_path / "rb.md"
        md.write_text(
            "## Stale Snapshots\nstale snapshot timestamp refresh universe\n\n"
            "## Stage Monotonicity\nmonotonicity history backfill duplicates\n\n"
            "## Broker Sync\nflexquery oauth refresh token broker session\n",
            encoding="utf-8",
        )
        return RunbookKnowledge(load_runbook_chunks(md))

    def test_returns_top_k_by_overlap(self, tmp_path: Path):
        kb = self._kb(tmp_path)
        out = kb.find_relevant("monotonicity duplicates history", top_k=2)
        assert out[0].heading == "Stage Monotonicity"

    def test_zero_overlap_returns_empty(self, tmp_path: Path):
        kb = self._kb(tmp_path)
        assert kb.find_relevant("kubernetes pod restart", top_k=3) == []

    def test_top_k_zero_returns_empty(self, tmp_path: Path):
        kb = self._kb(tmp_path)
        assert kb.find_relevant("flexquery", top_k=0) == []

    def test_query_text_is_deterministic(self):
        a = _anomaly()
        text = query_text_for_anomaly(
            category=a.category.value,
            title=a.title,
            facts=a.facts,
            raw_evidence=a.raw_evidence,
        )
        # No randomness; same input -> same output.
        assert text == query_text_for_anomaly(
            category=a.category.value,
            title=a.title,
            facts=a.facts,
            raw_evidence=a.raw_evidence,
        )
        assert "monotonicity" in text


# ---------------------------------------------------------------------------
# Confidence coercion
# ---------------------------------------------------------------------------


class TestConfidenceCoercion:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (0.7, Decimal("0.7")),
            ("0.42", Decimal("0.42")),
            (1.5, Decimal("1")),
            (-0.1, Decimal("0")),
            (None, Decimal("0.5")),
            ("not-a-number", Decimal("0.5")),
        ],
    )
    def test_clamping_and_fallback(self, value, expected):
        assert _to_decimal_confidence(value) == expected


# ---------------------------------------------------------------------------
# Explainer happy path
# ---------------------------------------------------------------------------


class TestExplainerHappyPath:
    def test_well_formed_payload_round_trip(self, tmp_path: Path):
        kb = RunbookKnowledge(
            load_runbook_chunks(
                self._write_runbook(tmp_path, "monotonicity", "monotonicity history")
            )
        )
        provider = StubLLMProvider([_good_payload()])
        explainer = AnomalyExplainer(
            provider,
            kb,
            available_tasks={"tasks.admin.repair_stage_history": "Repair stage history rows."},
        )
        exp = explainer.explain(_anomaly())

        assert exp.schema_version == SCHEMA_VERSION
        assert exp.is_fallback is False
        assert exp.title == "Stage monotonicity broke for 3 symbols"
        assert len(exp.steps) == 2
        assert exp.steps[0].requires_approval is False
        assert exp.steps[1].proposed_task == "tasks.admin.repair_stage_history"
        assert exp.confidence == Decimal("0.8")
        assert exp.runbook_excerpts and exp.runbook_excerpts[0].endswith("#monotonicity")
        assert exp.model == "stub"

    def _write_runbook(self, tmp_path: Path, anchor_word: str, body: str) -> Path:
        md = tmp_path / "rb.md"
        md.write_text(f"## {anchor_word}\n{body}\n", encoding="utf-8")
        return md

    def test_explanation_to_dict_is_json_safe(self):
        provider = StubLLMProvider([_good_payload()])
        exp = AnomalyExplainer(provider).explain(_anomaly())
        payload = explanation_to_dict(exp)
        # No Decimals / datetimes left -> json.dumps must not raise.
        json.dumps(payload)
        assert isinstance(payload["confidence"], str)
        assert isinstance(payload["generated_at"], str)
        assert isinstance(payload["steps"], list)


# ---------------------------------------------------------------------------
# Explainer error paths -> deterministic fallback
# ---------------------------------------------------------------------------


class TestExplainerFallback:
    def test_provider_error_returns_fallback(self):
        explainer = AnomalyExplainer(AlwaysFailingProvider())
        exp = explainer.explain(_anomaly())
        assert exp.is_fallback is True
        assert exp.confidence == Decimal("0.30")
        assert exp.title.startswith("[Fallback]")
        # Monotonicity has 2 scripted steps in the fallback table.
        assert len(exp.steps) == 2

    def test_invalid_json_returns_fallback(self):
        provider = StubLLMProvider(["this is not json {oops"])
        exp = AnomalyExplainer(provider).explain(_anomaly())
        assert exp.is_fallback is True

    def test_missing_required_field_returns_fallback(self):
        bad = json.dumps(
            {
                "title": "ok",
                # 'summary' missing
                "root_cause_hypothesis": "x",
                "narrative": "y",
                "steps": [{"order": 1, "description": "z", "requires_approval": False}],
                "confidence": 0.5,
            }
        )
        provider = StubLLMProvider([bad])
        exp = AnomalyExplainer(provider).explain(_anomaly())
        assert exp.is_fallback is True

    def test_top_level_array_returns_fallback(self):
        provider = StubLLMProvider(["[1,2,3]"])
        exp = AnomalyExplainer(provider).explain(_anomaly())
        assert exp.is_fallback is True

    def test_empty_response_returns_fallback(self):
        provider = StubLLMProvider([""])
        exp = AnomalyExplainer(provider).explain(_anomaly())
        assert exp.is_fallback is True

    def test_too_many_steps_returns_fallback(self):
        steps = [
            {"order": i, "description": f"step {i}", "requires_approval": False}
            for i in range(1, 25)
        ]
        provider = StubLLMProvider([_good_payload(steps=steps)])
        exp = AnomalyExplainer(provider).explain(_anomaly())
        assert exp.is_fallback is True

    def test_empty_steps_returns_fallback(self):
        provider = StubLLMProvider([_good_payload(steps=[])])
        exp = AnomalyExplainer(provider).explain(_anomaly())
        assert exp.is_fallback is True

    def test_unknown_category_uses_generic_fallback(self):
        explainer = AnomalyExplainer(AlwaysFailingProvider())
        exp = explainer.explain(_anomaly(cat=AnomalyCategory.OTHER))
        assert exp.is_fallback is True
        assert len(exp.steps) >= 1
        # Generic fallback has the "composite health" step in position 1.
        assert "composite health" in exp.steps[0].description.lower()


# ---------------------------------------------------------------------------
# Hallucinated task drop / step coercion
# ---------------------------------------------------------------------------


class TestStepHardening:
    def test_hallucinated_task_is_stripped(self):
        steps = [
            {
                "order": 1,
                "description": "do thing",
                "proposed_task": "tasks.totally.not.real",
                "requires_approval": True,
            }
        ]
        provider = StubLLMProvider([_good_payload(steps=steps)])
        explainer = AnomalyExplainer(
            provider,
            available_tasks={"tasks.real.one": "real"},
        )
        exp = explainer.explain(_anomaly())
        assert exp.is_fallback is False
        assert exp.steps[0].proposed_task is None
        assert exp.steps[0].description == "do thing"

    def test_known_task_is_kept(self):
        steps = [
            {
                "order": 1,
                "description": "kick task",
                "proposed_task": "tasks.real.one",
                "requires_approval": True,
            }
        ]
        provider = StubLLMProvider([_good_payload(steps=steps)])
        explainer = AnomalyExplainer(
            provider,
            available_tasks={"tasks.real.one": "real"},
        )
        exp = explainer.explain(_anomaly())
        assert exp.steps[0].proposed_task == "tasks.real.one"

    def test_step_without_description_is_dropped(self):
        # Mix one good and one bad step; the orchestrator should keep one.
        steps = [
            {"order": 1, "description": "", "requires_approval": False},
            {"order": 2, "description": "real step", "requires_approval": True},
        ]
        provider = StubLLMProvider([_good_payload(steps=steps)])
        exp = AnomalyExplainer(provider).explain(_anomaly())
        assert exp.is_fallback is False
        assert len(exp.steps) == 1
        assert exp.steps[0].description == "real step"

    def test_step_description_truncated_to_600(self):
        long = "x" * 1000
        steps = [{"order": 1, "description": long, "requires_approval": True}]
        provider = StubLLMProvider([_good_payload(steps=steps)])
        exp = AnomalyExplainer(provider).explain(_anomaly())
        assert len(exp.steps[0].description) == 600


# ---------------------------------------------------------------------------
# Constructor / contract
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_none_provider_raises(self):
        with pytest.raises(ValueError):
            AnomalyExplainer(None)  # type: ignore[arg-type]

    def test_default_knowledge_is_empty(self):
        provider = StubLLMProvider([_good_payload()])
        explainer = AnomalyExplainer(provider)
        assert len(explainer.knowledge) == 0
        # Empty knowledge -> zero excerpts -> still works.
        exp = explainer.explain(_anomaly())
        assert exp.runbook_excerpts == []

    def test_max_runbook_chunks_zero_skips_retrieval(self, tmp_path: Path):
        md = tmp_path / "rb.md"
        md.write_text("## Stale Snapshots\nbody\n", encoding="utf-8")
        kb = RunbookKnowledge(load_runbook_chunks(md))
        provider = StubLLMProvider([_good_payload()])
        explainer = AnomalyExplainer(provider, kb, max_runbook_chunks=0)
        exp = explainer.explain(_anomaly(cat=AnomalyCategory.STALE_SNAPSHOT))
        assert exp.runbook_excerpts == []


# ---------------------------------------------------------------------------
# Output JSON schema sanity
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_schema_is_strict_object(self):
        # additionalProperties=false is critical -- without it, an LLM that
        # adds extra fields would silently drift the wire contract.
        assert OUTPUT_JSON_SCHEMA["additionalProperties"] is False
        assert OUTPUT_JSON_SCHEMA["type"] == "object"
        assert OUTPUT_JSON_SCHEMA["properties"]["steps"]["minItems"] >= 1
        assert OUTPUT_JSON_SCHEMA["properties"]["steps"]["maxItems"] <= 12

    def test_step_schema_requires_approval_flag(self):
        step_schema = OUTPUT_JSON_SCHEMA["properties"]["steps"]["items"]
        assert "requires_approval" in step_schema["required"]
        assert step_schema["properties"]["requires_approval"]["type"] == "boolean"


# ---------------------------------------------------------------------------
# Stub / failing provider primitives
# ---------------------------------------------------------------------------


class TestStubProviders:
    def test_stub_records_calls(self):
        s = StubLLMProvider(["one", "two"])
        assert s.complete_json("sys", "u1") == "one"
        assert s.complete_json("sys", "u2", max_tokens=500) == "two"
        assert len(s.calls) == 2
        assert s.calls[0][0] == "sys"

    def test_stub_exhaustion_raises(self):
        s = StubLLMProvider([])
        with pytest.raises(LLMProviderError):
            s.complete_json("sys", "u")

    def test_stub_rejects_non_list(self):
        with pytest.raises(TypeError):
            StubLLMProvider("not a list")  # type: ignore[arg-type]
