"""Tests for G22 — IBKR FlexQuery Sync Completeness Validation.

Asserts that ``validate_completeness`` correctly classifies sync outcomes as
``success`` / ``partial`` / ``error`` based on which sections the FlexQuery
report contains, and that ``warnings`` is populated for every degraded
dimension. These tests are the regression net for the silent-partial-success
class of bug that produced the "BrokerAccount=success but no positions /
balances were synced" outcome (G22 founder anchor).
"""

from __future__ import annotations

import pytest

from app.services.portfolio.ibkr.sync_validator import (
    EXPECTED_FLEX_SECTIONS,
    SyncCompletenessStatus,
    discover_xml_sections,
    validate_completeness,
)

pytestmark = pytest.mark.no_db


def _make_xml(sections: dict[str, int]) -> str:
    """Build a minimal FlexQueryResponse XML with the requested section row counts."""
    children: list[str] = []
    for name, count in sections.items():
        rows = "<Row/>" * int(count)
        children.append(f"<{name}>{rows}</{name}>")
    body = "".join(children)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<FlexQueryResponse>"
        "<FlexStatements>"
        '<FlexStatement accountId="U12345" fromDate="20250101" toDate="20251231">'
        f"{body}"
        "</FlexStatement>"
        "</FlexStatements>"
        "</FlexQueryResponse>"
    )


def _full_report_xml() -> str:
    return _make_xml(
        {
            "OpenPositions": 10,
            "AccountInformation": 1,
            "Trades": 50,
            "CashTransactions": 20,
            "Transfers": 0,
            "InterestAccruals": 0,
            "OptionEAE": 0,
        }
    )


# ---------------------------------------------------------------------------
# discover_xml_sections
# ---------------------------------------------------------------------------


def test_discover_counts_rows_per_section():
    xml = _make_xml({"Trades": 3, "CashTransactions": 5})
    discovered = discover_xml_sections(xml)
    assert "Trades" in discovered and discovered["Trades"]["row_count"] == 3
    assert "CashTransactions" in discovered and discovered["CashTransactions"]["row_count"] == 5


def test_discover_returns_empty_dict_for_unparseable_xml():
    assert discover_xml_sections("<<<not-xml>>>") == {}
    assert discover_xml_sections("") == {}
    assert discover_xml_sections("   ") == {}


def test_discover_accumulates_rows_across_multiple_flex_statements():
    xml = (
        "<FlexQueryResponse><FlexStatements>"
        '<FlexStatement accountId="U1"><Trades><Row/><Row/></Trades></FlexStatement>'
        '<FlexStatement accountId="U2"><Trades><Row/></Trades></FlexStatement>'
        "</FlexStatements></FlexQueryResponse>"
    )
    discovered = discover_xml_sections(xml)
    assert discovered["Trades"]["row_count"] == 3


# ---------------------------------------------------------------------------
# validate_completeness — happy path
# ---------------------------------------------------------------------------


def test_full_report_returns_success():
    report = validate_completeness(_full_report_xml())
    assert report.status == SyncCompletenessStatus.SUCCESS
    assert report.missing_required == []
    error_warnings = [w for w in report.warnings if w["level"] == "error"]
    assert error_warnings == []


def test_expected_sections_matches_constant():
    report = validate_completeness(_full_report_xml())
    assert set(report.expected_sections) == {s.name for s in EXPECTED_FLEX_SECTIONS}


def test_section_row_counts_populated_from_xml():
    xml = _make_xml(
        {"OpenPositions": 7, "AccountInformation": 1, "Trades": 23, "CashTransactions": 11}
    )
    report = validate_completeness(xml)
    assert report.section_row_counts["OpenPositions"] == 7
    assert report.section_row_counts["AccountInformation"] == 1
    assert report.section_row_counts["Trades"] == 23
    assert report.section_row_counts["CashTransactions"] == 11


def test_missing_only_optional_sections_is_success_with_info_warnings():
    """An empty Joint Taxable account with no transfers/margin/options events
    should still be SUCCESS — the absence of optional sections is normal."""
    xml = _make_xml(
        {
            "OpenPositions": 5,
            "AccountInformation": 1,
            "Trades": 50,
            "CashTransactions": 20,
        }
    )
    report = validate_completeness(xml)
    assert report.status == SyncCompletenessStatus.SUCCESS
    info_warnings = [w for w in report.warnings if w["level"] == "info"]
    info_sections = {w["section"] for w in info_warnings}
    assert {"Transfers", "InterestAccruals", "OptionEAE"} <= info_sections
    error_warnings = [w for w in report.warnings if w["level"] == "error"]
    assert error_warnings == []


# ---------------------------------------------------------------------------
# validate_completeness — partial paths (the founder bug)
# ---------------------------------------------------------------------------


def test_missing_open_positions_is_partial_with_error_warning():
    """The exact founder-anchor failure: Trades + CashTransactions came through
    but OpenPositions did not, so positions and tax_lots were silently empty."""
    xml = _make_xml({"AccountInformation": 1, "Trades": 50, "CashTransactions": 20})
    report = validate_completeness(xml)
    assert report.status == SyncCompletenessStatus.PARTIAL
    assert "OpenPositions" in report.missing_required
    assert any(
        w["section"] == "OpenPositions" and w["code"] == "section_missing" and w["level"] == "error"
        for w in report.warnings
    )


def test_missing_account_information_is_partial():
    xml = _make_xml({"OpenPositions": 5, "Trades": 50, "CashTransactions": 20})
    report = validate_completeness(xml)
    assert report.status == SyncCompletenessStatus.PARTIAL
    assert "AccountInformation" in report.missing_required


def test_missing_multiple_required_is_still_partial_unless_all():
    xml = _make_xml({"Trades": 50, "CashTransactions": 20})
    report = validate_completeness(xml)
    assert report.status == SyncCompletenessStatus.PARTIAL
    assert {"OpenPositions", "AccountInformation"} <= set(report.missing_required)


def test_pipeline_step_error_promotes_to_partial_even_if_xml_complete():
    """Section was present in XML but our writer broke — must surface, not hide."""
    xml = _full_report_xml()
    sync_results = {
        "tax_lots": {"error": "DB unique-constraint violation on lot_id"},
        "trades": {"synced": 50},
        "account_balances": {"synced": 1},
        "cash_transactions": {"synced": 20},
    }
    report = validate_completeness(xml, sync_results)
    assert report.status == SyncCompletenessStatus.PARTIAL
    assert any(
        w["code"] == "pipeline_step_errored" and w["section"] == "OpenPositions"
        for w in report.warnings
    )


# ---------------------------------------------------------------------------
# validate_completeness — error paths
# ---------------------------------------------------------------------------


def test_unparseable_xml_returns_error():
    report = validate_completeness("<<<not-xml>>>")
    assert report.status == SyncCompletenessStatus.ERROR
    assert any(w["code"] == "report_unparseable_or_empty" for w in report.warnings)


def test_empty_xml_returns_error():
    report = validate_completeness("")
    assert report.status == SyncCompletenessStatus.ERROR


def test_all_required_missing_escalates_to_error():
    xml = _make_xml({"Transfers": 1})  # only an optional section
    report = validate_completeness(xml)
    assert report.status == SyncCompletenessStatus.ERROR
    required = {s.name for s in EXPECTED_FLEX_SECTIONS if s.required}
    assert required <= set(report.missing_required)


# ---------------------------------------------------------------------------
# CompletenessReport contract
# ---------------------------------------------------------------------------


def test_to_dict_round_trip_preserves_all_fields():
    report = validate_completeness(_full_report_xml())
    d = report.to_dict()
    assert set(d.keys()) >= {
        "status",
        "expected_sections",
        "received_sections",
        "missing_required",
        "missing_optional",
        "section_row_counts",
        "warnings",
    }
    # JSON-serializable: no dataclasses or sets leak through
    import json

    json.dumps(d)


def test_missing_sections_property_is_union_of_required_and_optional():
    xml = _make_xml({"AccountInformation": 1, "Trades": 50, "CashTransactions": 20})
    report = validate_completeness(xml)
    assert "OpenPositions" in report.missing_sections
    assert set(report.missing_sections) == set(report.missing_required) | set(
        report.missing_optional
    )


def test_clean_success_has_empty_warnings():
    """A clean sync's empty warnings list is the positive signal that the
    pipeline is healthy — must not be polluted with info-level chatter."""
    report = validate_completeness(_full_report_xml())
    assert report.warnings == []


def test_warnings_are_structured_dicts_with_required_keys():
    xml = _make_xml({"AccountInformation": 1})
    report = validate_completeness(xml)
    for w in report.warnings:
        assert {"level", "section", "code", "message"} <= set(w.keys())
        assert w["level"] in {"error", "info"}


# ---------------------------------------------------------------------------
# _build_partial_sync_message — Copilot review on PR #383 (PARTIAL message
# must surface pipeline_step_errored, not just missing_required)
# ---------------------------------------------------------------------------


def test_partial_message_surfaces_missing_required_sections():
    from app.services.portfolio.broker_sync_service import (
        _build_partial_sync_message,
    )

    completeness = {
        "missing_required": ["OpenPositions", "AccountInformation"],
        "warnings": [],
    }
    msg = _build_partial_sync_message(completeness)
    assert "missing required broker report sections" in msg
    assert "OpenPositions" in msg and "AccountInformation" in msg


def test_partial_message_surfaces_pipeline_step_errored_when_no_missing():
    """The Copilot anchor: PARTIAL caused only by a writer error on a present
    section must NOT render as 'missing required broker report sections []'."""
    from app.services.portfolio.broker_sync_service import (
        _build_partial_sync_message,
    )

    completeness = {
        "missing_required": [],
        "warnings": [
            {
                "level": "error",
                "section": "OpenPositions",
                "code": "pipeline_step_errored",
                "message": "writer DB error",
            }
        ],
    }
    msg = _build_partial_sync_message(completeness)
    assert "[]" not in msg
    assert "pipeline writer errored on" in msg
    assert "OpenPositions" in msg


def test_partial_message_surfaces_both_missing_and_errored():
    from app.services.portfolio.broker_sync_service import (
        _build_partial_sync_message,
    )

    completeness = {
        "missing_required": ["AccountInformation"],
        "warnings": [
            {
                "level": "error",
                "section": "OpenPositions",
                "code": "pipeline_step_errored",
                "message": "writer DB error",
            }
        ],
    }
    msg = _build_partial_sync_message(completeness)
    assert "missing required broker report sections" in msg
    assert "AccountInformation" in msg
    assert "pipeline writer errored on" in msg
    assert "OpenPositions" in msg


def test_partial_message_falls_back_to_generic_when_no_signal():
    """Empty completeness dict (defensive): never silently render '[]'."""
    from app.services.portfolio.broker_sync_service import (
        _build_partial_sync_message,
    )

    msg = _build_partial_sync_message({})
    assert "[]" not in msg
    assert "degraded completeness" in msg or "see sync history" in msg


def test_partial_message_truncates_to_500_chars():
    from app.services.portfolio.broker_sync_service import (
        _build_partial_sync_message,
    )

    completeness = {
        "missing_required": [f"Section{i}" for i in range(200)],
        "warnings": [],
    }
    msg = _build_partial_sync_message(completeness)
    assert len(msg) <= 500
