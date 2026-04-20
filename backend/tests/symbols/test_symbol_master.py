"""Tests for the symbol master models and resolution service.

The acceptance criterion for this PR is the FB -> META point-in-time
test:

* Register the FB -> META alias with effective_date 2022-06-09.
* ``resolve("FB", as_of=2022-06-08)`` returns the SymbolMaster row.
* ``resolve("FB", as_of=2022-06-10)`` returns the SAME SymbolMaster row.

The other tests in this module exercise edge cases callers will hit
in production: case normalization, unknown-ticker behavior, alias
half-open windows, audit-ledger semantics, idempotency of
``record_ticker_change``, and the multi-tenancy boundary (the master
must remain global — no ``user_id`` may sneak in).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend.models.symbol_master import (
    AliasSource,
    AssetClass,
    SymbolChangeType,
    SymbolHistory,
    SymbolMaster,
    SymbolStatus,
)
from backend.services.symbols.symbol_master_service import (
    HISTORICAL_FLOOR_DATE,
    SymbolMasterError,
    SymbolMasterService,
    UnknownTickerError,
)


# ---------------------------------------------------------------------------
# Schema shape — verifies the migration created what the model expects
# ---------------------------------------------------------------------------


class TestSchemaShape:
    EXPECTED_TABLES = {"symbol_master", "symbol_alias", "symbol_history"}

    def test_all_tables_exist(self, db_session):
        inspector = inspect(db_session.bind)
        existing = set(inspector.get_table_names())
        missing = self.EXPECTED_TABLES - existing
        assert not missing, f"Migration is missing tables: {sorted(missing)}"

    @pytest.mark.parametrize(
        "table,required",
        [
            (
                "symbol_master",
                {
                    "id",
                    "primary_ticker",
                    "cik",
                    "isin",
                    "figi",
                    "asset_class",
                    "exchange",
                    "country",
                    "currency",
                    "name",
                    "sector",
                    "industry",
                    "gics_code",
                    "status",
                    "first_seen_at",
                    "last_seen_at",
                    "delisted_at",
                    "merged_into_symbol_master_id",
                },
            ),
            (
                "symbol_alias",
                {
                    "id",
                    "symbol_master_id",
                    "alias_ticker",
                    "valid_from",
                    "valid_to",
                    "source",
                    "notes",
                },
            ),
            (
                "symbol_history",
                {
                    "id",
                    "symbol_master_id",
                    "change_type",
                    "old_value",
                    "new_value",
                    "effective_date",
                    "recorded_at",
                    "source",
                },
            ),
        ],
    )
    def test_required_columns_present(self, db_session, table, required):
        inspector = inspect(db_session.bind)
        cols = {c["name"] for c in inspector.get_columns(table)}
        missing = required - cols
        assert not missing, f"{table}: migration is missing columns {sorted(missing)}"

    def test_primary_ticker_unique(self, db_session):
        a = SymbolMaster(
            primary_ticker="UQAAPL_TEST",
            asset_class=AssetClass.EQUITY.value,
            status=SymbolStatus.ACTIVE.value,
        )
        db_session.add(a)
        db_session.flush()

        dup = SymbolMaster(
            primary_ticker="UQAAPL_TEST",
            asset_class=AssetClass.EQUITY.value,
            status=SymbolStatus.ACTIVE.value,
        )
        with pytest.raises(IntegrityError):
            db_session.add(dup)
            db_session.flush()
        db_session.rollback()


# ---------------------------------------------------------------------------
# Acceptance criterion: FB -> META point-in-time
# ---------------------------------------------------------------------------


class TestFbToMetaResolution:
    """The flagship test for this PR.

    A single corporate entity (Meta Platforms, Inc.) renamed its
    primary ticker from FB to META on 2022-06-09. Resolving the legacy
    ``FB`` string from any historical date — before *or* after the
    rename — must return the same SymbolMaster row. That's the contract
    the rest of the platform will rely on when migrating ad-hoc
    symbol-string usage to the master.
    """

    def test_fb_resolves_to_meta_row_at_both_as_of_dates(self, db_session):
        service = SymbolMasterService(db_session)

        meta_master, created = service.get_or_create_master(
            "META",
            asset_class=AssetClass.EQUITY,
            name="Meta Platforms, Inc.",
            exchange="NASDAQ",
            country="US",
            currency="USD",
        )
        assert created is True

        result = service.record_ticker_change(
            "FB",
            "META",
            effective_date=date(2022, 6, 9),
            source=AliasSource.TICKER_CHANGE,
            notes="Facebook rebrand to Meta Platforms.",
        )

        assert result.master.id == meta_master.id
        assert result.master.primary_ticker == "META"
        assert result.alias.alias_ticker == "FB"
        assert result.history.change_type == SymbolChangeType.TICKER_CHANGE.value
        assert result.history.effective_date == date(2022, 6, 9)
        assert result.created_history is True

        before = service.resolve("FB", as_of_date=date(2022, 6, 8))
        after = service.resolve("FB", as_of_date=date(2022, 6, 10))

        assert before is not None, "FB should resolve before the rename"
        assert after is not None, "FB should still resolve after the rename"
        assert before.id == after.id == meta_master.id, (
            "Both as_of dates must return the SAME SymbolMaster row "
            "(the legal entity is identical; only the ticker changed)."
        )
        # Sanity: resolving the new ticker also lands on the same row.
        assert service.resolve("META").id == meta_master.id

    def test_record_ticker_change_is_idempotent(self, db_session):
        service = SymbolMasterService(db_session)
        service.get_or_create_master("META", asset_class=AssetClass.EQUITY)

        first = service.record_ticker_change(
            "FB", "META", effective_date=date(2022, 6, 9)
        )
        second = service.record_ticker_change(
            "FB", "META", effective_date=date(2022, 6, 9)
        )
        assert first.master.id == second.master.id
        assert first.alias.id == second.alias.id, (
            "Re-running with the same args must reuse the alias row, "
            "not create a duplicate."
        )
        assert first.history.id == second.history.id, (
            "Audit ledger must dedupe on (master, change_type, effective_date, "
            "old_value, new_value) so reruns don't pollute history."
        )
        # And the bookkeeping flags reflect that.
        assert first.created_history is True
        assert second.created_history is False
        assert second.created_alias is False

        history = service.history_for(first.master.id)
        assert len(history) == 1
        aliases = service.aliases_for(first.master.id)
        assert sum(1 for a in aliases if a.alias_ticker == "FB") == 1


# ---------------------------------------------------------------------------
# resolve() edge cases
# ---------------------------------------------------------------------------


class TestResolveEdgeCases:
    def test_resolve_unknown_ticker_returns_none(self, db_session):
        service = SymbolMasterService(db_session)
        assert service.resolve("ZZZZ_NONEXISTENT") is None
        assert service.resolve("ZZZZ_NONEXISTENT", as_of_date=date(2024, 1, 1)) is None

    def test_resolve_strict_unknown_ticker_raises(self, db_session):
        service = SymbolMasterService(db_session)
        with pytest.raises(UnknownTickerError) as excinfo:
            service.resolve_strict("ZZZZ_NONEXISTENT")
        assert excinfo.value.ticker == "ZZZZ_NONEXISTENT"

    def test_resolve_normalizes_case_and_whitespace(self, db_session):
        service = SymbolMasterService(db_session)
        master, _ = service.get_or_create_master(
            "AAPL_TST", asset_class=AssetClass.EQUITY
        )
        for variant in ("aapl_tst", "  AAPL_TST", "AAPL_TST  ", "AaPl_TsT"):
            resolved = service.resolve(variant)
            assert resolved is not None, f"normalization failed for {variant!r}"
            assert resolved.id == master.id

    def test_resolve_blank_ticker_returns_none(self, db_session):
        service = SymbolMasterService(db_session)
        assert service.resolve("") is None
        assert service.resolve("   ") is None

    def test_resolve_preserves_internal_punctuation(self, db_session):
        service = SymbolMasterService(db_session)
        master, _ = service.get_or_create_master(
            "BRK.B_TST", asset_class=AssetClass.EQUITY
        )
        assert service.resolve("brk.b_tst").id == master.id
        assert service.resolve("BRK.A_TST") is None  # not the same ticker

    def test_alias_window_excludes_dates_after_valid_to(self, db_session):
        """A non-sticky alias bounded by ``[valid_from, valid_to)`` must
        only resolve inside its window when an as_of_date is given."""
        service = SymbolMasterService(db_session)
        master, _ = service.get_or_create_master(
            "NEWCO_TST", asset_class=AssetClass.EQUITY
        )
        service.register_alias(
            master.id,
            "OLDCO_TST",
            valid_from=date(2020, 1, 1),
            valid_to=date(2021, 1, 1),
            source=AliasSource.MANUAL,
        )

        assert service.resolve("OLDCO_TST", as_of_date=date(2020, 6, 1)).id == master.id
        # Edge: valid_to is exclusive, so the boundary date itself is NOT in range.
        assert service.resolve("OLDCO_TST", as_of_date=date(2021, 1, 1)) is None
        assert service.resolve("OLDCO_TST", as_of_date=date(2019, 12, 31)) is None
        # Without an as_of_date, the alias still resolves (sticky lookup).
        assert service.resolve("OLDCO_TST").id == master.id

    def test_resolve_picks_most_recent_alias_when_multiple_match(self, db_session):
        """If the same ticker has been reused (e.g. delisted then reissued
        to a different entity) we want the most recently-effective alias."""
        service = SymbolMasterService(db_session)
        m_old, _ = service.get_or_create_master(
            "OLD_REUSE_TST", asset_class=AssetClass.EQUITY
        )
        m_new, _ = service.get_or_create_master(
            "NEW_REUSE_TST", asset_class=AssetClass.EQUITY
        )

        service.register_alias(
            m_old.id,
            "REUSED_TST",
            valid_from=date(2010, 1, 1),
            valid_to=date(2015, 1, 1),
            source=AliasSource.MANUAL,
        )
        service.register_alias(
            m_new.id,
            "REUSED_TST",
            valid_from=date(2020, 1, 1),
            valid_to=None,
            source=AliasSource.MANUAL,
        )

        assert service.resolve("REUSED_TST", as_of_date=date(2012, 1, 1)).id == m_old.id
        assert service.resolve("REUSED_TST", as_of_date=date(2024, 1, 1)).id == m_new.id

    def test_register_alias_rejects_inverted_window(self, db_session):
        service = SymbolMasterService(db_session)
        master, _ = service.get_or_create_master(
            "SOMECO_TST", asset_class=AssetClass.EQUITY
        )
        with pytest.raises(SymbolMasterError):
            service.register_alias(
                master.id,
                "BAD_TST",
                valid_from=date(2024, 1, 1),
                valid_to=date(2020, 1, 1),
                source=AliasSource.MANUAL,
            )

    def test_record_ticker_change_rejects_self_rename(self, db_session):
        service = SymbolMasterService(db_session)
        with pytest.raises(SymbolMasterError):
            service.record_ticker_change(
                "FOO_TST", "FOO_TST", effective_date=date(2024, 1, 1)
            )

    def test_record_ticker_change_creates_master_when_missing(self, db_session):
        """If neither the old nor new ticker has an existing master row,
        the service creates one keyed on the new ticker (so legacy data
        without a pre-existing master can still record a rename)."""
        service = SymbolMasterService(db_session)
        result = service.record_ticker_change(
            "OLDX_TST", "NEWX_TST", effective_date=date(2024, 6, 1)
        )
        assert result.master.primary_ticker == "NEWX_TST"
        assert result.created_master is True
        assert service.resolve("OLDX_TST").id == result.master.id
        assert service.resolve("NEWX_TST").id == result.master.id

    def test_record_ticker_change_rotates_legacy_master(self, db_session):
        """If the master only exists under the OLD ticker, the rename
        rotates ``primary_ticker`` to the new value (preserving the
        master id)."""
        service = SymbolMasterService(db_session)
        legacy, _ = service.get_or_create_master(
            "LEG_OLD_TST", asset_class=AssetClass.EQUITY, name="Legacy Co."
        )
        legacy_id = legacy.id

        result = service.record_ticker_change(
            "LEG_OLD_TST",
            "LEG_NEW_TST",
            effective_date=date(2023, 5, 1),
            new_name="Legacy Co. (renamed)",
        )
        assert result.master.id == legacy_id
        assert result.master.primary_ticker == "LEG_NEW_TST"
        assert result.master.name == "Legacy Co. (renamed)"
        assert result.created_master is False

    def test_sticky_alias_uses_historical_floor_date(self, db_session):
        """``record_ticker_change`` plants a sticky alias using the
        historical-floor sentinel so as_of dates from the deep past
        still resolve."""
        service = SymbolMasterService(db_session)
        service.get_or_create_master("META_FLR_TST", asset_class=AssetClass.EQUITY)
        result = service.record_ticker_change(
            "FB_FLR_TST", "META_FLR_TST", effective_date=date(2022, 6, 9)
        )
        assert result.alias.valid_from == HISTORICAL_FLOOR_DATE
        assert result.alias.valid_to is None

        # Even an as_of well before the actual ticker existed resolves
        # because the alias is sticky.
        assert (
            service.resolve("FB_FLR_TST", as_of_date=date(2005, 1, 1)).id
            == result.master.id
        )


# ---------------------------------------------------------------------------
# bulk_resolve / history / aliases convenience
# ---------------------------------------------------------------------------


class TestConvenienceHelpers:
    def test_bulk_resolve_returns_dict_with_unknowns_as_none(self, db_session):
        service = SymbolMasterService(db_session)
        service.get_or_create_master("BULK_AAPL", asset_class=AssetClass.EQUITY)
        service.get_or_create_master("BULK_MSFT", asset_class=AssetClass.EQUITY)

        result = service.bulk_resolve(
            ["BULK_AAPL", "bulk_msft", "ZZZZ_BULK_NONE", "  ", ""]
        )
        assert set(result.keys()) == {"BULK_AAPL", "BULK_MSFT", "ZZZZ_BULK_NONE"}
        assert result["BULK_AAPL"] is not None
        assert result["BULK_MSFT"] is not None
        assert result["ZZZZ_BULK_NONE"] is None

    def test_history_and_aliases_return_oldest_first(self, db_session):
        service = SymbolMasterService(db_session)
        master, _ = service.get_or_create_master(
            "HISTSORT_TST", asset_class=AssetClass.EQUITY
        )

        service.register_alias(
            master.id,
            "HSORT_OLDCO",
            valid_from=date(2018, 1, 1),
            source=AliasSource.MANUAL,
        )
        service.register_alias(
            master.id,
            "HSORT_MIDCO",
            valid_from=date(2020, 1, 1),
            source=AliasSource.MANUAL,
        )

        for eff in (date(2019, 1, 1), date(2021, 1, 1)):
            db_session.add(
                SymbolHistory(
                    symbol_master_id=master.id,
                    change_type=SymbolChangeType.NAME_CHANGE.value,
                    effective_date=eff,
                    source="test",
                )
            )
        db_session.flush()

        aliases = service.aliases_for(master.id)
        assert [a.valid_from for a in aliases] == [
            date(2018, 1, 1),
            date(2020, 1, 1),
        ]

        history = service.history_for(master.id)
        assert [h.effective_date for h in history] == [
            date(2019, 1, 1),
            date(2021, 1, 1),
        ]


# ---------------------------------------------------------------------------
# Multi-tenancy boundary check
# ---------------------------------------------------------------------------


class TestGlobalScope:
    def test_master_table_carries_no_user_id_column(self, db_session):
        """Symbol master is a global table per the master plan. If a
        user_id column ever sneaks in, downstream callers will start
        leaking the global catalog through tenant-scoped joins.
        """
        inspector = inspect(db_session.bind)
        for table in ("symbol_master", "symbol_alias", "symbol_history"):
            cols = {c["name"] for c in inspector.get_columns(table)}
            assert "user_id" not in cols, (
                f"{table} must remain global; user_id column would break "
                "the documented contract."
            )
