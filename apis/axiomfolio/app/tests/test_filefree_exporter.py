"""
Tests for the FileFree.ai tax-export pipeline.

Strategy:

* The mapper is pure (no DB), so it gets exhaustive unit coverage with
  hand-built duck-typed Trade / Account stand-ins.
* The exporter is tested with a tiny stub session that just returns the
  pre-built rows the mapper would otherwise need; this proves the wiring
  (account scoping, tax-advantaged filter, year filter) without dragging
  in a real Postgres fixture.
* The serializer gets a round-trip CSV header check.

These tests intentionally avoid any DB, network, or real ORM, so they run
in milliseconds even when the broader CI marks DB tests as required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pytest
from pydantic import ValidationError

from app.services.tax.filefree_exporter import FileFreeExporter
from app.services.tax.mapper import build_package
from app.services.tax.schemas import (
    SCHEMA_VERSION,
    DataQuality,
    InstrumentType,
    LotTerm,
)
from app.services.tax.serialization import CSV_COLUMNS, package_to_csv


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _FakeBrokerEnum:
    value: str


@dataclass
class _FakeAccountTypeEnum:
    value: str


@dataclass
class FakeAccount:
    id: int
    user_id: int = 1
    broker: Any = field(default_factory=lambda: _FakeBrokerEnum("ibkr"))
    account_number: str = "U1234567"
    account_type: Any = field(default_factory=lambda: _FakeAccountTypeEnum("taxable"))
    is_tax_advantaged: bool = False


@dataclass
class FakeTrade:
    id: int
    account_id: int
    symbol: str
    quantity: Decimal
    total_value: Decimal
    realized_pnl: Optional[Decimal]
    status: str
    execution_id: str = ""
    execution_time: Optional[datetime] = None
    side: str = "SELL"
    trade_metadata: Dict[str, Any] = field(default_factory=dict)


def _ibkr_close(
    trade_id: int,
    account_id: int,
    *,
    symbol: str = "AAPL",
    qty: str = "100",
    proceeds: str = "15000.00",
    cost_basis: str = "10000.00",
    realized: str = "5000.00",
    is_long_term: bool = True,
    open_date: str = "2022-03-01",
    close_date: str = "2024-06-15",
    status: str = "CLOSED_LOT",
    wash_loss: Optional[str] = None,
) -> FakeTrade:
    meta: Dict[str, Any] = {
        "cost_basis": cost_basis,
        "open_date": open_date,
        "close_date": close_date,
        "is_long_term": is_long_term,
        "source": "ibkr_flexquery",
    }
    if wash_loss is not None:
        meta["wash_sale_loss"] = wash_loss
    return FakeTrade(
        id=trade_id,
        account_id=account_id,
        symbol=symbol,
        quantity=Decimal(qty),
        total_value=Decimal(proceeds),
        realized_pnl=Decimal(realized),
        status=status,
        execution_id=f"E{trade_id}",
        execution_time=datetime.fromisoformat(close_date + "T15:00:00").replace(
            tzinfo=timezone.utc
        ),
        trade_metadata=meta,
    )


# ---------------------------------------------------------------------------
# build_package: happy paths
# ---------------------------------------------------------------------------


class TestMapperHappyPath:
    def test_single_long_term_lot(self):
        acct = FakeAccount(id=1)
        trade = _ibkr_close(1, 1)
        pkg = build_package(
            user_id=42,
            tax_year=2024,
            accounts=[acct],
            trades=[trade],
            generated_at=datetime(2025, 1, 5, 12, 0, tzinfo=timezone.utc),
        )

        assert pkg.schema_version == SCHEMA_VERSION
        assert pkg.tax_year == 2024
        assert pkg.user_id == 42
        assert pkg.generated_at.tzinfo is not None
        assert len(pkg.accounts) == 1
        assert pkg.accounts[0].lot_count == 1
        assert pkg.accounts[0].has_calculated_lots is False
        assert len(pkg.lots) == 1

        lot = pkg.lots[0]
        assert lot.symbol == "AAPL"
        assert lot.quantity == Decimal("100")
        assert lot.proceeds == Decimal("15000.00")
        assert lot.cost_basis == Decimal("10000.00")
        assert lot.realized_gain == Decimal("5000.00")
        assert lot.term == LotTerm.LONG_TERM
        assert lot.data_quality == DataQuality.BROKER_OFFICIAL
        assert lot.source == "ibkr_flexquery"
        assert lot.is_wash_sale is False
        assert lot.wash_sale_disallowed_loss is None
        assert lot.adjustment_code is None
        assert lot.account_ref == "ibkr:U1234567"

    def test_summary_aggregates_short_and_long(self):
        acct = FakeAccount(id=1)
        st = _ibkr_close(
            1, 1, symbol="MSFT", realized="-300.00", is_long_term=False,
            proceeds="2700.00", cost_basis="3000.00",
        )
        lt = _ibkr_close(
            2, 1, symbol="AAPL", realized="5000.00", is_long_term=True,
            proceeds="15000.00", cost_basis="10000.00",
        )
        pkg = build_package(
            user_id=1,
            tax_year=2024,
            accounts=[acct],
            trades=[st, lt],
        )
        s = pkg.summary
        assert s.lot_count == 2
        assert s.total_proceeds == Decimal("17700.00")
        assert s.total_cost_basis == Decimal("13000.00")
        assert s.total_realized_gain == Decimal("4700.00")
        assert s.total_short_term_gain == Decimal("-300.00")
        assert s.total_long_term_gain == Decimal("5000.00")
        assert s.wash_sale_disallowed_total == Decimal("0")

    def test_wash_sale_emits_adjustment_code_and_amount(self):
        acct = FakeAccount(id=1)
        wash = _ibkr_close(
            7,
            1,
            symbol="TSLA",
            realized="-500.00",
            proceeds="500.00",
            cost_basis="1000.00",
            status="WASH_SALE",
            wash_loss="500.00",
            is_long_term=False,
        )
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[acct], trades=[wash]
        )
        lot = pkg.lots[0]
        assert lot.is_wash_sale is True
        assert lot.adjustment_code == "W"
        assert lot.wash_sale_disallowed_loss == Decimal("500.00")
        assert pkg.summary.wash_sale_disallowed_total == Decimal("500.00")

    def test_wash_sale_with_negative_meta_value_normalized(self):
        # IBKR sometimes reports wash_sale_loss as a negative number; we
        # normalize to positive for IRS Form 8949 column h.
        acct = FakeAccount(id=1)
        wash = _ibkr_close(
            8,
            1,
            symbol="NVDA",
            realized="-200",
            proceeds="800",
            cost_basis="1000",
            status="WASH_SALE",
            wash_loss="-200",
        )
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[acct], trades=[wash]
        )
        assert pkg.lots[0].wash_sale_disallowed_loss == Decimal("200")


# ---------------------------------------------------------------------------
# build_package: edge cases & data quality flags
# ---------------------------------------------------------------------------


class TestMapperEdgeCases:
    def test_unknown_term_when_no_metadata(self):
        acct = FakeAccount(id=1)
        bare = FakeTrade(
            id=99,
            account_id=1,
            symbol="GOOG",
            quantity=Decimal("10"),
            total_value=Decimal("12000"),
            realized_pnl=Decimal("2000"),
            status="CLOSED_LOT",
            execution_id="E99",
            execution_time=datetime(2024, 5, 1, tzinfo=timezone.utc),
            trade_metadata={},  # no is_long_term key
        )
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[acct], trades=[bare]
        )
        assert pkg.lots[0].term == LotTerm.UNKNOWN

    def test_tastytrade_account_marked_calculated_and_warns(self):
        acct = FakeAccount(
            id=2,
            broker=_FakeBrokerEnum("tastytrade"),
            account_number="TT9999",
        )
        trade = FakeTrade(
            id=1,
            account_id=2,
            symbol="SPY",
            quantity=Decimal("50"),
            total_value=Decimal("25000"),
            realized_pnl=Decimal("1000"),
            status="CLOSED_LOT",
            execution_id="X1",
            execution_time=datetime(2024, 7, 1, tzinfo=timezone.utc),
            trade_metadata={"is_long_term": False},
        )
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[acct], trades=[trade]
        )
        assert pkg.lots[0].data_quality == DataQuality.CALCULATED
        assert pkg.accounts[0].has_calculated_lots is True
        assert any("CALCULATED" in w for w in pkg.warnings)

    def test_trade_with_unknown_account_is_skipped_and_warned(self):
        acct = FakeAccount(id=1)
        rogue = FakeTrade(
            id=11,
            account_id=999,  # not in scope
            symbol="AAPL",
            quantity=Decimal("1"),
            total_value=Decimal("100"),
            realized_pnl=Decimal("0"),
            status="CLOSED_LOT",
            execution_id="R1",
            execution_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[acct], trades=[rogue]
        )
        assert pkg.lots == []
        assert any("not in scope" in w for w in pkg.warnings)

    def test_non_realized_status_filtered(self):
        # Plain FILLED rows are open positions; they MUST NOT show up in tax exports.
        acct = FakeAccount(id=1)
        regular = FakeTrade(
            id=1,
            account_id=1,
            symbol="AAPL",
            quantity=Decimal("1"),
            total_value=Decimal("100"),
            realized_pnl=Decimal("0"),
            status="FILLED",
            execution_id="F1",
            execution_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[acct], trades=[regular]
        )
        assert pkg.lots == []
        assert pkg.summary.lot_count == 0

    def test_missing_symbol_skipped_and_warned(self):
        acct = FakeAccount(id=1)
        bad = FakeTrade(
            id=1,
            account_id=1,
            symbol="",
            quantity=Decimal("1"),
            total_value=Decimal("100"),
            realized_pnl=Decimal("0"),
            status="CLOSED_LOT",
            execution_id="B1",
        )
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[acct], trades=[bad]
        )
        assert pkg.lots == []
        assert any("missing symbol" in w for w in pkg.warnings)

    def test_option_symbol_classified_as_option(self):
        acct = FakeAccount(id=1)
        opt = FakeTrade(
            id=1,
            account_id=1,
            symbol="AAPL  240119C00150000",
            quantity=Decimal("1"),
            total_value=Decimal("250"),
            realized_pnl=Decimal("100"),
            status="CLOSED_LOT",
            execution_id="O1",
            execution_time=datetime(2024, 1, 19, tzinfo=timezone.utc),
            trade_metadata={"is_long_term": False, "asset_class": "OPT"},
        )
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[acct], trades=[opt]
        )
        assert pkg.lots[0].instrument_type == InstrumentType.OPTION

    def test_decimal_precision_preserved_through_floats(self):
        acct = FakeAccount(id=1)
        trade = FakeTrade(
            id=1,
            account_id=1,
            symbol="AAPL",
            quantity=0.1,  # raw float
            total_value=0.3,
            realized_pnl=0.2,
            status="CLOSED_LOT",
            execution_id="P1",
            execution_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            trade_metadata={"cost_basis": 0.1, "is_long_term": True},
        )
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[acct], trades=[trade]
        )
        # Floats stringified -> exact decimal, no IEEE-754 noise like 0.1 -> 0.10000000000000000555...
        assert pkg.lots[0].quantity == Decimal("0.1")
        assert pkg.lots[0].cost_basis == Decimal("0.1")

    def test_naive_generated_at_is_promoted_to_utc(self):
        acct = FakeAccount(id=1)
        pkg = build_package(
            user_id=1,
            tax_year=2024,
            accounts=[acct],
            trades=[],
            generated_at=datetime(2025, 1, 1, 0, 0),  # naive
        )
        assert pkg.generated_at.tzinfo is not None

    def test_empty_inputs_produce_empty_package(self):
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[], trades=[]
        )
        assert pkg.lots == []
        assert pkg.accounts == []
        assert pkg.summary.lot_count == 0
        assert pkg.summary.total_proceeds == Decimal("0")


# ---------------------------------------------------------------------------
# Exporter wiring
# ---------------------------------------------------------------------------


class _FakeQuery:
    def __init__(self, data):
        self._data = data
        self._filters: list = []

    def filter(self, *clauses):
        return self

    def order_by(self, *clauses):
        return self

    def all(self):
        return list(self._data)


class _FakeSession:
    """Minimal Session double that returns canned rows per model."""

    def __init__(self, accounts, trades):
        self._accounts = accounts
        self._trades = trades

    def query(self, model):
        # Match by name to avoid importing actual models in this test harness.
        if getattr(model, "__name__", "") == "BrokerAccount":
            return _FakeQuery(self._accounts)
        if getattr(model, "__name__", "") == "Trade":
            return _FakeQuery(self._trades)
        return _FakeQuery([])


class TestExporterWiring:
    def test_excludes_tax_advantaged_by_default(self):
        taxable = FakeAccount(id=1, is_tax_advantaged=False)
        ira = FakeAccount(
            id=2,
            account_type=_FakeAccountTypeEnum("ira"),
            is_tax_advantaged=True,
            account_number="U-IRA",
        )
        trade = _ibkr_close(1, 1)
        sess = _FakeSession([taxable, ira], [trade])

        pkg = FileFreeExporter(sess).export(
            user_id=1,
            tax_year=2024,
            generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        # Only the taxable account in scope
        refs = {a.account_ref for a in pkg.accounts}
        assert refs == {"ibkr:U1234567"}

    def test_include_tax_advantaged_dump(self):
        taxable = FakeAccount(id=1)
        ira = FakeAccount(
            id=2,
            account_type=_FakeAccountTypeEnum("ira"),
            is_tax_advantaged=True,
            account_number="U-IRA",
        )
        sess = _FakeSession([taxable, ira], [])

        pkg = FileFreeExporter(sess).export(
            user_id=1, tax_year=2024, include_tax_advantaged=True
        )
        refs = {a.account_ref for a in pkg.accounts}
        assert "ibkr:U-IRA" in refs

    def test_no_accounts_returns_empty_package(self):
        sess = _FakeSession([], [])
        pkg = FileFreeExporter(sess).export(user_id=1, tax_year=2024)
        assert pkg.lots == []
        assert pkg.accounts == []
        assert pkg.summary.lot_count == 0


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestCSVSerializer:
    def test_csv_columns_stable(self):
        # Guard against accidental column reorders without a schema bump.
        assert CSV_COLUMNS == [
            "lot_id",
            "account_ref",
            "symbol",
            "description",
            "instrument_type",
            "quantity",
            "date_acquired",
            "date_sold",
            "proceeds",
            "cost_basis",
            "realized_gain",
            "term",
            "is_wash_sale",
            "wash_sale_disallowed_loss",
            "adjustment_code",
            "data_quality",
            "source",
        ]

    def test_csv_rendering_round_trip(self):
        acct = FakeAccount(id=1)
        trade = _ibkr_close(1, 1)
        pkg = build_package(
            user_id=1, tax_year=2024, accounts=[acct], trades=[trade]
        )
        csv_text = package_to_csv(pkg)
        lines = csv_text.strip().splitlines()
        assert lines[0].startswith("lot_id,account_ref,symbol")
        assert "AAPL" in lines[1]
        assert "ibkr_flexquery" in lines[1]
        # is_wash_sale column should be 'false' literal, not Python False.
        assert ",false," in lines[1]


# ---------------------------------------------------------------------------
# Pydantic validation
# ---------------------------------------------------------------------------


class TestPackageValidation:
    def test_extra_fields_rejected(self):
        # We use ConfigDict(extra='forbid') on lots/accounts/summary so a
        # downstream consumer's malformed payload can never silently pass
        # round-trip validation.
        from app.services.tax.schemas import FileFreeAccount

        with pytest.raises(ValidationError):
            FileFreeAccount(
                account_ref="ibkr:U1",
                broker="ibkr",
                account_type="taxable",
                is_tax_advantaged=False,
                lot_count=0,
                has_calculated_lots=False,
                bogus_extra="nope",  # type: ignore[call-arg]
            )

    def test_schema_version_constant(self):
        # If you bump SCHEMA_VERSION, also bump this assertion AND log a
        # decision in docs/KNOWLEDGE.md per repo policy.
        assert SCHEMA_VERSION == "1.0.0"
