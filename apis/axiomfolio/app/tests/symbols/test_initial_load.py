"""Tests for the symbol master initial-load bootstrap script.

The contract is straightforward but the assertions are strict:

* First run creates one master per seed and one history entry per
  curated change.
* A second run with the same input is a no-op — counters move from
  ``created`` to ``skipped``, history rows do not duplicate, alias
  rows do not duplicate.
* Counters always satisfy ``created + skipped + errored == total``
  (per ``no-silent-fallback.mdc``); the bootstrap raises if they
  ever drift.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.symbol_master import (
    AliasSource,
    SymbolAlias,
    SymbolHistory,
    SymbolMaster,
)
from app.services.symbols.initial_load import (
    SEED_TICKER_CHANGES,
    InitialLoadCounters,
    TickerChangeSeed,
    run_initial_load,
)
from app.services.symbols.symbol_master_service import SymbolMasterService


# A small, deterministic seed list used by the idempotency tests so
# they don't depend on the production seed length (which will grow
# over time as we discover more historical references).
SMALL_SEED: tuple[TickerChangeSeed, ...] = (
    TickerChangeSeed(
        old_ticker="ILTEST_FB",
        new_ticker="ILTEST_META",
        effective_date=date(2022, 6, 9),
        name_after="Meta Platforms, Inc.",
    ),
    TickerChangeSeed(
        old_ticker="ILTEST_TWTR",
        new_ticker="ILTEST_X",
        effective_date=date(2023, 7, 26),
        name_after="X Corp.",
    ),
    TickerChangeSeed(
        old_ticker="ILTEST_ANTM",
        new_ticker="ILTEST_ELV",
        effective_date=date(2022, 6, 28),
        name_after="Elevance Health, Inc.",
    ),
)


def _count_seed_rows(db_session) -> tuple[int, int, int]:
    """Counts restricted to rows touched by ``SMALL_SEED`` so we
    don't pick up unrelated rows from other tests in the same DB."""
    seed_tickers = set()
    for s in SMALL_SEED:
        seed_tickers.add(s.old_ticker)
        seed_tickers.add(s.new_ticker)
    masters = (
        db_session.query(SymbolMaster)
        .filter(SymbolMaster.primary_ticker.in_(seed_tickers))
        .all()
    )
    master_ids = [m.id for m in masters]
    if not master_ids:
        return 0, 0, 0
    history = (
        db_session.query(SymbolHistory)
        .filter(SymbolHistory.symbol_master_id.in_(master_ids))
        .count()
    )
    aliases = (
        db_session.query(SymbolAlias)
        .filter(SymbolAlias.symbol_master_id.in_(master_ids))
        .count()
    )
    return len(masters), history, aliases


# ---------------------------------------------------------------------------
# Counter contract
# ---------------------------------------------------------------------------


class TestCountersContract:
    def test_assert_consistent_passes_when_balanced(self):
        c = InitialLoadCounters(
            masters_total=5,
            masters_created=3,
            masters_skipped=1,
            masters_errored=1,
            changes_total=2,
            changes_applied=1,
            changes_skipped=1,
        )
        c.assert_consistent()

    def test_assert_consistent_raises_on_drift(self):
        c = InitialLoadCounters(masters_total=5, masters_created=2)
        with pytest.raises(RuntimeError, match="counter drift"):
            c.assert_consistent()


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_first_run_creates_expected_rows(self, db_session):
        counters = run_initial_load(
            db_session,
            seeds=SMALL_SEED,
            include_snapshot_symbols=False,
            commit=False,
        )

        # Every seed produces exactly one history entry and one
        # sticky alias. Master counters are governed by phase 1 (off
        # in this test); the changes phase records masters as needed.
        assert counters.changes_applied == len(SMALL_SEED)
        assert counters.changes_skipped == 0
        assert counters.changes_errored == 0

        n_masters, n_history, n_aliases = _count_seed_rows(db_session)
        assert n_masters == len(SMALL_SEED), (
            f"expected {len(SMALL_SEED)} masters for seed tickers, got {n_masters}"
        )
        assert n_history == len(SMALL_SEED)
        # One sticky alias per seed (the legacy ticker).
        assert n_aliases == len(SMALL_SEED)

    def test_second_run_is_no_op(self, db_session):
        run_initial_load(
            db_session,
            seeds=SMALL_SEED,
            include_snapshot_symbols=False,
            commit=False,
        )
        masters_after_first, history_after_first, aliases_after_first = (
            _count_seed_rows(db_session)
        )

        second = run_initial_load(
            db_session,
            seeds=SMALL_SEED,
            include_snapshot_symbols=False,
            commit=False,
        )

        assert second.changes_applied == 0, (
            "Re-running must not append to history; got "
            f"{second.changes_applied} new history entries."
        )
        assert second.changes_skipped == len(SMALL_SEED)
        assert second.changes_errored == 0

        # Hard counts must be unchanged after the second run.
        masters_after_second, history_after_second, aliases_after_second = (
            _count_seed_rows(db_session)
        )
        assert masters_after_second == masters_after_first
        assert history_after_second == history_after_first
        assert aliases_after_second == aliases_after_first

    def test_seeded_changes_are_resolvable(self, db_session):
        run_initial_load(
            db_session,
            seeds=SMALL_SEED,
            include_snapshot_symbols=False,
            commit=False,
        )
        service = SymbolMasterService(db_session)
        for seed in SMALL_SEED:
            new_master = service.resolve(seed.new_ticker)
            old_master = service.resolve(seed.old_ticker)
            assert new_master is not None, f"{seed.new_ticker} should resolve"
            assert old_master is not None, f"{seed.old_ticker} should still resolve"
            assert new_master.id == old_master.id, (
                f"Old and new tickers for {seed.old_ticker}->{seed.new_ticker} "
                "must point to the same master row."
            )


# ---------------------------------------------------------------------------
# Production seed sanity
# ---------------------------------------------------------------------------


class TestProductionSeedSanity:
    """Smoke test the curated seed list to catch typos before they
    reach prod. Doesn't validate financial accuracy of every effective
    date — just structural sanity."""

    def test_seed_list_has_reasonable_size(self):
        n = len(SEED_TICKER_CHANGES)
        assert 20 <= n <= 100, (
            f"Curated seed should hold ~20-100 entries; current size = {n}. "
            "If you've added a lot, consider splitting into a CSV the "
            "script can read."
        )

    @pytest.mark.parametrize("seed", SEED_TICKER_CHANGES)
    def test_seed_entry_shape(self, seed: TickerChangeSeed):
        assert seed.old_ticker, "old_ticker must be non-empty"
        assert seed.new_ticker, "new_ticker must be non-empty"
        assert seed.old_ticker != seed.new_ticker, (
            f"seed for {seed.old_ticker} renames to itself"
        )
        assert seed.old_ticker == seed.old_ticker.upper().strip(), (
            f"old_ticker {seed.old_ticker!r} not normalized"
        )
        assert seed.new_ticker == seed.new_ticker.upper().strip(), (
            f"new_ticker {seed.new_ticker!r} not normalized"
        )
        assert isinstance(seed.source, AliasSource), (
            f"seed.source must be an AliasSource enum (got {type(seed.source)})"
        )
        assert date(1990, 1, 1) <= seed.effective_date <= date(2030, 1, 1), (
            f"seed effective_date {seed.effective_date} outside sanity window"
        )

    def test_full_production_seed_runs_clean(self, db_session):
        """The full curated seed list bootstraps without any errors and
        is itself idempotent."""
        first = run_initial_load(
            db_session,
            include_snapshot_symbols=False,
            commit=False,
        )
        assert first.changes_errored == 0, first.error_samples
        assert first.changes_applied + first.changes_skipped == first.changes_total

        second = run_initial_load(
            db_session,
            include_snapshot_symbols=False,
            commit=False,
        )
        assert second.changes_applied == 0
        assert second.changes_errored == 0
