"""IBKR FlexQuery sync completeness validator (G22 — no-silent-success).

The IBKR pipeline historically returned ``status: "success"`` even when the
Flex Query report was missing required sections (e.g. ``OpenPositions``,
``AccountInformation``). The downstream sync_* steps would simply write zero
rows for the missing section, and the orchestrator's ``_total_synced`` check
would still pass as long as *some* other section had rows. This is the exact
silent-fallback class of bug forbidden by ``no-silent-fallback.mdc``.

This module makes section presence/absence a first-class signal:

- Walk the XML and discover which ``FlexStatement`` children are actually
  present (and how many rows each contains).
- Compare against ``EXPECTED_FLEX_SECTIONS`` (canonical list aligned with
  ``IBKRFlexQueryClient.get_setup_instructions`` and ``docs/CONNECTIONS.md``).
- Distinguish *required* sections (missing → partial) from *optional* sections
  (missing → info-level warning, status stays success).
- If the pipeline returned per-step error dicts for sections that *were*
  present in the XML, surface them as explicit warnings — the section was
  there but our writer broke.
- Always populate a structured ``warnings`` list so a downstream observer
  (UI, log, /admin/health) can tell whether the system is healthy or
  degraded. No silent fallbacks (R32, R34, R38).

medallion: bronze
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlexSectionSpec:
    """Canonical metadata for a single FlexQuery report section."""

    name: str
    required: bool
    description: str
    pipeline_result_keys: tuple[str, ...] = ()


# Canonical expected sections per IBKR FlexQuery configuration.
# Aligned with ``app/services/clients/ibkr_flexquery_client.get_setup_instructions``
# and ``docs/CONNECTIONS.md``. Ordered by criticality.
EXPECTED_FLEX_SECTIONS: tuple[FlexSectionSpec, ...] = (
    FlexSectionSpec(
        name="OpenPositions",
        required=True,
        description=(
            "Open positions (Summary + Lot detail). Drives tax lots, current "
            "stock/ETF positions, and option positions."
        ),
        pipeline_result_keys=("tax_lots", "positions", "option_positions"),
    ),
    FlexSectionSpec(
        name="AccountInformation",
        required=True,
        description="Account metadata + balances (NAV, cash, buying power).",
        pipeline_result_keys=("account_balances",),
    ),
    FlexSectionSpec(
        name="Trades",
        required=True,
        description=(
            "Trade history including Closed Lots and Wash Sales. Even an inactive "
            "account in the period emits an empty Trades container; a missing "
            "container element indicates the section is not enabled in the query."
        ),
        pipeline_result_keys=("trades",),
    ),
    FlexSectionSpec(
        name="CashTransactions",
        required=True,
        description=(
            "Deposits, withdrawals, dividends, interest credits. Even an account "
            "with no cash activity emits an empty CashTransactions container."
        ),
        pipeline_result_keys=("cash_transactions",),
    ),
    FlexSectionSpec(
        name="Transfers",
        required=False,
        description=(
            "ACATS / position transfers. Only present when the account had "
            "transfer activity in the period."
        ),
        pipeline_result_keys=("transfers",),
    ),
    FlexSectionSpec(
        name="InterestAccruals",
        required=False,
        description=(
            "Margin interest accruals. Only present when the account used margin."
        ),
        pipeline_result_keys=("margin_interest",),
    ),
    FlexSectionSpec(
        name="OptionEAE",
        required=False,
        description=(
            "Option exercises, assignments, expirations. Only present when one "
            "of those events occurred in the period."
        ),
        pipeline_result_keys=(),
    ),
)


# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------


class SyncCompletenessStatus:
    """String constants used in result['status'] across the pipeline."""

    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class CompletenessReport:
    """Result of validating a FlexQuery sync for completeness.

    Distinguishes "section absent from the report" (Flex query misconfigured →
    partial) from "section present but empty" (legitimate — account had no
    activity in that section during the period).
    """

    status: str
    expected_sections: list[str]
    received_sections: list[str]
    missing_required: list[str]
    missing_optional: list[str]
    section_row_counts: dict[str, int]
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "expected_sections": list(self.expected_sections),
            "received_sections": list(self.received_sections),
            "missing_required": list(self.missing_required),
            "missing_optional": list(self.missing_optional),
            "section_row_counts": dict(self.section_row_counts),
            "warnings": list(self.warnings),
        }

    @property
    def missing_sections(self) -> list[str]:
        """Combined list of all missing sections (required + optional)."""
        return list(self.missing_required) + list(self.missing_optional)


# ---------------------------------------------------------------------------
# Discovery + validation
# ---------------------------------------------------------------------------


def discover_xml_sections(report_xml: str) -> dict[str, dict[str, Any]]:
    """Return the set of FlexStatement child sections actually present in the XML.

    Returns a mapping ``section_name -> {"present": True, "row_count": N}``.
    Sections that are not in the XML are simply absent from the returned
    dict (rather than having ``present: False``) — callers should treat
    "key not in dict" as the missing signal.

    A multi-statement report (multiple ``<FlexStatement>`` blocks) accumulates
    row counts across statements for the same section name.
    """
    discovered: dict[str, dict[str, Any]] = {}
    if not report_xml:
        return discovered
    try:
        root = ET.fromstring(report_xml)
    except ET.ParseError as exc:
        logger.warning(
            "FlexQuery XML could not be parsed for section discovery: %s", exc
        )
        return discovered

    for stmt in root.iter("FlexStatement"):
        for child in stmt:
            name = child.tag
            row_count = sum(1 for _ in child)
            entry = discovered.get(name)
            if entry is None:
                discovered[name] = {"present": True, "row_count": row_count}
            else:
                entry["row_count"] += row_count
    return discovered


def validate_completeness(
    report_xml: str,
    sync_results: dict[str, Any] | None = None,
) -> CompletenessReport:
    """Validate a FlexQuery sync result for completeness.

    Args:
        report_xml: The raw XML returned by ``IBKRFlexQueryClient.get_full_report``.
        sync_results: Optional pipeline results dict so we can also detect the
            "section was present in XML but the pipeline writer errored" case.

    Returns:
        ``CompletenessReport`` whose ``status`` is one of:
          - ``"error"``: XML unparseable / empty, OR all required sections missing.
          - ``"partial"``: at least one required section missing, OR at least one
            pipeline step errored on a section that was present.
          - ``"success"``: all required sections present and no pipeline errors.

    Always populates ``warnings`` with structured entries so the UI and logs
    can communicate the exact degradation. Never returns silently; an empty
    ``warnings`` list is itself a positive signal that the sync was clean.
    """
    discovered = discover_xml_sections(report_xml)
    expected_names = [spec.name for spec in EXPECTED_FLEX_SECTIONS]
    received_names = sorted(discovered.keys())
    missing_required: list[str] = []
    missing_optional: list[str] = []
    section_row_counts: dict[str, int] = {}
    warnings: list[dict[str, Any]] = []

    if not discovered:
        all_required = [s.name for s in EXPECTED_FLEX_SECTIONS if s.required]
        all_optional = [s.name for s in EXPECTED_FLEX_SECTIONS if not s.required]
        return CompletenessReport(
            status=SyncCompletenessStatus.ERROR,
            expected_sections=expected_names,
            received_sections=[],
            missing_required=all_required,
            missing_optional=all_optional,
            section_row_counts={},
            warnings=[
                {
                    "level": "error",
                    "section": "*",
                    "code": "report_unparseable_or_empty",
                    "message": (
                        "FlexQuery report could not be parsed or contained no "
                        "FlexStatement sections. Verify the Flex Web Service token "
                        "is valid, the query ID is correct, and the report has "
                        "finished generating before the fetch."
                    ),
                }
            ],
        )

    for spec in EXPECTED_FLEX_SECTIONS:
        info = discovered.get(spec.name)
        if info is None:
            if spec.required:
                missing_required.append(spec.name)
                warnings.append(
                    {
                        "level": "error",
                        "section": spec.name,
                        "code": "section_missing",
                        "message": (
                            f"Required FlexQuery section '{spec.name}' is missing "
                            f"from the report. Add it to your Flex Query "
                            f"configuration: {spec.description}"
                        ),
                    }
                )
            else:
                missing_optional.append(spec.name)
                warnings.append(
                    {
                        "level": "info",
                        "section": spec.name,
                        "code": "optional_section_missing",
                        "message": (
                            f"Optional FlexQuery section '{spec.name}' is not "
                            f"present. This is fine if no relevant activity "
                            f"occurred ({spec.description})"
                        ),
                    }
                )
            continue

        section_row_counts[spec.name] = int(info["row_count"])

        if sync_results:
            for key in spec.pipeline_result_keys:
                step = sync_results.get(key)
                if isinstance(step, dict) and step.get("error"):
                    warnings.append(
                        {
                            "level": "error",
                            "section": spec.name,
                            "code": "pipeline_step_errored",
                            "message": (
                                f"Section '{spec.name}' was received "
                                f"(rows={info['row_count']}) but pipeline step "
                                f"'{key}' errored: {step.get('error')}"
                            ),
                        }
                    )

    has_pipeline_error = any(
        w["level"] == "error" and w["code"] == "pipeline_step_errored"
        for w in warnings
    )

    if missing_required and len(missing_required) == sum(
        1 for s in EXPECTED_FLEX_SECTIONS if s.required
    ):
        status = SyncCompletenessStatus.ERROR
    elif missing_required or has_pipeline_error:
        status = SyncCompletenessStatus.PARTIAL
    else:
        status = SyncCompletenessStatus.SUCCESS

    return CompletenessReport(
        status=status,
        expected_sections=expected_names,
        received_sections=received_names,
        missing_required=missing_required,
        missing_optional=missing_optional,
        section_row_counts=section_row_counts,
        warnings=warnings,
    )


__all__ = [
    "EXPECTED_FLEX_SECTIONS",
    "CompletenessReport",
    "FlexSectionSpec",
    "SyncCompletenessStatus",
    "discover_xml_sections",
    "validate_completeness",
]
