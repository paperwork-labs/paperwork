"""Tests for the candidate generator framework + Stage2ARsStrong.

Covers:
* Registry: subclasses register via __init_subclass__, duplicate names
  raise, get_generator returns the right class.
* persist_candidates: idempotent within a UTC day, valid rows persist,
  empty/invalid symbols are counted.
* run_all_generators: per-generator failure isolation, ``only`` filter.
* Stage2ARsStrongGenerator: filters and rationale on synthetic snapshots.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Sequence

import pytest

from backend.models.market_data import MarketSnapshot
from backend.models.picks import Candidate, CandidateQueueState, PickAction
from backend.services.picks.candidate_generator import (
    CandidateGenerator,
    GeneratedCandidate,
    GeneratorRunReport,
    persist_candidates,
    registered_generators,
    run_all_generators,
)
from backend.services.picks.generators.stage2a_rs_strong import (
    Stage2ARsStrongGenerator,
    Stage2AThresholds,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_concrete_generators_are_registered(self):
        names = {c.name for c in registered_generators()}
        assert "stage2a_rs_strong" in names

    def test_duplicate_name_raises(self):
        with pytest.raises(RuntimeError, match="Duplicate"):

            class _Duplicate(CandidateGenerator):
                name = "stage2a_rs_strong"
                version = "v1"

                def generate(self, db):
                    return []

    def test_subclass_without_name_does_not_register(self):
        starting = set(registered_generators())

        class _Abstract(CandidateGenerator):
            # No name, no version: should be skipped.
            def generate(self, db):
                return []

        assert set(registered_generators()) == starting


# ---------------------------------------------------------------------------
# persist_candidates idempotency
# ---------------------------------------------------------------------------


class _TestGen(CandidateGenerator):
    """Inline generator used only by persist_candidates tests.

    Declared with a unique name so __init_subclass__ does not clash.
    """

    name = "test_persist_only"
    version = "v0"

    def __init__(self, items: Sequence[GeneratedCandidate]):
        self._items = list(items)

    def generate(self, db):
        return list(self._items)


class TestPersistCandidates:
    def test_creates_new_rows(self, db_session):
        gen = _TestGen(
            [
                GeneratedCandidate(
                    symbol="NVDA",
                    action_suggestion=PickAction.BUY,
                    score=Decimal("85.5"),
                    rationale_summary="test",
                ),
                GeneratedCandidate(
                    symbol="MSFT",
                    action_suggestion=PickAction.BUY,
                    score=Decimal("78.0"),
                    rationale_summary="test",
                ),
            ]
        )
        counts = persist_candidates(db_session, gen, gen.generate(db_session))
        assert counts == {"created": 2, "skipped_duplicate": 0, "invalid": 0}

        rows = (
            db_session.query(Candidate)
            .filter(Candidate.generator_name == "test_persist_only")
            .all()
        )
        assert {r.symbol for r in rows} == {"NVDA", "MSFT"}
        assert all(r.status == CandidateQueueState.DRAFT for r in rows)
        assert all(r.action_suggestion == PickAction.BUY for r in rows)

    def test_idempotent_within_same_utc_day(self, db_session):
        gen = _TestGen(
            [
                GeneratedCandidate(
                    symbol="AAPL",
                    action_suggestion=PickAction.BUY,
                    score=Decimal("80"),
                )
            ]
        )
        persist_candidates(db_session, gen, gen.generate(db_session))
        counts = persist_candidates(db_session, gen, gen.generate(db_session))
        assert counts == {"created": 0, "skipped_duplicate": 1, "invalid": 0}

        rows = (
            db_session.query(Candidate)
            .filter(
                Candidate.generator_name == "test_persist_only",
                Candidate.symbol == "AAPL",
            )
            .all()
        )
        assert len(rows) == 1

    def test_empty_symbol_is_invalid(self, db_session):
        gen = _TestGen(
            [
                GeneratedCandidate(
                    symbol="",
                    action_suggestion=PickAction.BUY,
                ),
                GeneratedCandidate(
                    symbol="   ",
                    action_suggestion=PickAction.BUY,
                ),
            ]
        )
        counts = persist_candidates(db_session, gen, gen.generate(db_session))
        assert counts == {"created": 0, "skipped_duplicate": 0, "invalid": 2}

    def test_uppercases_symbol(self, db_session):
        gen = _TestGen(
            [
                GeneratedCandidate(
                    symbol="tsla",
                    action_suggestion=PickAction.BUY,
                )
            ]
        )
        persist_candidates(db_session, gen, gen.generate(db_session))
        row = (
            db_session.query(Candidate)
            .filter(Candidate.generator_name == "test_persist_only")
            .one()
        )
        assert row.symbol == "TSLA"

    def test_subclass_without_name_cannot_be_used(self, db_session):
        # Build a generator object directly without going through
        # __init_subclass__ name registration.
        gen = _TestGen([])
        gen.name = ""  # type: ignore[misc]
        with pytest.raises(RuntimeError, match="must set name and version"):
            persist_candidates(db_session, gen, [])


# ---------------------------------------------------------------------------
# run_all_generators isolation
# ---------------------------------------------------------------------------


class _RaisingGen(CandidateGenerator):
    name = "test_raising"
    version = "v0"

    def generate(self, db):
        raise RuntimeError("boom")


class _OkGen(CandidateGenerator):
    name = "test_ok"
    version = "v0"

    def generate(self, db):
        return [
            GeneratedCandidate(symbol="ONE", action_suggestion=PickAction.BUY)
        ]


class TestRunAllGenerators:
    def test_failure_in_one_does_not_block_others(self, db_session):
        reports = run_all_generators(
            db_session, only=("test_raising", "test_ok")
        )
        by_name = {r.generator: r for r in reports}
        assert by_name["test_raising"].error is not None
        assert by_name["test_raising"].created == 0
        assert by_name["test_ok"].error is None
        assert by_name["test_ok"].created == 1

    def test_only_filter_runs_subset(self, db_session):
        reports = run_all_generators(db_session, only=("test_ok",))
        names = {r.generator for r in reports}
        assert names == {"test_ok"}


# ---------------------------------------------------------------------------
# Stage2ARsStrongGenerator
# ---------------------------------------------------------------------------


def _snap(
    db_session,
    *,
    symbol: str,
    stage_label: str = "2A",
    rs: float = 75.0,
    ext: float = 2.0,
    range_pos: float = 0.75,
    action_label: str = "BUY",
    is_valid: bool = True,
    analysis_type: str = "technical_snapshot",
) -> MarketSnapshot:
    now = datetime.now(timezone.utc)
    row = MarketSnapshot(
        symbol=symbol,
        analysis_type=analysis_type,
        analysis_timestamp=now,
        as_of_timestamp=now,
        expiry_timestamp=now + timedelta(hours=24),
        is_valid=is_valid,
        stage_label=stage_label,
        rs_mansfield_pct=rs,
        ext_pct=ext,
        range_pos_52w=range_pos,
        action_label=action_label,
        current_price=125.50,
        atr_14=2.5,
        sma_21=120.00,
        sma_150=110.00,
    )
    db_session.add(row)
    db_session.flush()
    return row


class TestStage2ARsStrong:
    def test_produces_candidate_for_2a_rs_high(self, db_session):
        _snap(db_session, symbol="NVDA", stage_label="2A", rs=85.0, ext=1.5)
        gen = Stage2ARsStrongGenerator()
        out = list(gen.generate(db_session))
        assert len(out) == 1
        c = out[0]
        assert c.symbol == "NVDA"
        assert c.action_suggestion == PickAction.BUY
        assert c.score is not None and c.score > Decimal("80")
        assert "RS Mansfield" in (c.rationale_summary or "")
        assert c.signals["stage_label"] == "2A"

    def test_filters_out_low_rs(self, db_session):
        _snap(db_session, symbol="LOWRS", rs=50.0)
        gen = Stage2ARsStrongGenerator()
        assert list(gen.generate(db_session)) == []

    def test_filters_out_extended(self, db_session):
        _snap(db_session, symbol="CHASE", rs=80.0, ext=15.0)
        gen = Stage2ARsStrongGenerator()
        assert list(gen.generate(db_session)) == []

    def test_filters_out_thin_range(self, db_session):
        _snap(db_session, symbol="THIN", rs=80.0, range_pos=0.30)
        gen = Stage2ARsStrongGenerator()
        assert list(gen.generate(db_session)) == []

    def test_filters_out_wrong_stage(self, db_session):
        _snap(db_session, symbol="STG3", stage_label="3A", rs=80.0)
        gen = Stage2ARsStrongGenerator()
        assert list(gen.generate(db_session)) == []

    def test_filters_out_invalid_snapshot(self, db_session):
        _snap(db_session, symbol="BADSNP", rs=80.0, is_valid=False)
        gen = Stage2ARsStrongGenerator()
        assert list(gen.generate(db_session)) == []

    def test_action_label_buy_is_optional_by_default(self, db_session):
        _snap(db_session, symbol="WATCH", rs=80.0, action_label="WATCH")
        gen = Stage2ARsStrongGenerator()
        # Default thresholds do not require action_label==BUY.
        out = list(gen.generate(db_session))
        assert len(out) == 1

    def test_action_label_required_when_strict(self, db_session):
        _snap(db_session, symbol="WATCH", rs=80.0, action_label="WATCH")
        strict = Stage2AThresholds(require_action_label_buy=True)
        gen = Stage2ARsStrongGenerator(thresholds=strict)
        assert list(gen.generate(db_session)) == []

    def test_returns_highest_rs_first(self, db_session):
        _snap(db_session, symbol="MED", rs=72.0)
        _snap(db_session, symbol="HIGH", rs=92.0)
        _snap(db_session, symbol="LOW", rs=70.5)
        gen = Stage2ARsStrongGenerator()
        out = list(gen.generate(db_session))
        symbols = [c.symbol for c in out]
        assert symbols == ["HIGH", "MED", "LOW"]

    def test_max_results_caps_output(self, db_session):
        for i in range(7):
            _snap(db_session, symbol=f"SYM{i:02d}", rs=80.0 + i)
        small = Stage2AThresholds(max_results=3)
        gen = Stage2ARsStrongGenerator(thresholds=small)
        assert len(list(gen.generate(db_session))) == 3

    def test_score_penalises_extended_setups(self, db_session):
        _snap(db_session, symbol="FRESH", rs=80.0, ext=1.0)
        _snap(db_session, symbol="EXTENDED", rs=80.0, ext=4.5)
        gen = Stage2ARsStrongGenerator()
        out = {c.symbol: c for c in gen.generate(db_session)}
        assert out["FRESH"].score > out["EXTENDED"].score

    def test_picks_only_latest_snapshot_per_symbol(self, db_session):
        s1 = _snap(db_session, symbol="DUP", rs=80.0)
        # Older, higher-RS snapshot should be ignored in favour of latest
        s1.analysis_timestamp = datetime.now(timezone.utc) - timedelta(days=5)
        db_session.flush()
        _snap(db_session, symbol="DUP", rs=72.0, ext=2.0)
        gen = Stage2ARsStrongGenerator()
        out = list(gen.generate(db_session))
        # Latest row has rs=72 which still passes (>=70). Should appear once.
        assert [c.symbol for c in out] == ["DUP"]
        assert abs(float(out[0].signals["rs_mansfield_pct"]) - 72.0) < 1e-6
