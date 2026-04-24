"""Tests for ``QuorumService``.

Covers every status path required by the spec:

* QUORUM_REACHED -- 3-of-3 agree, 2-of-3 within tolerance, exact match.
* DISAGREEMENT -- all three diverge beyond tolerance.
* INSUFFICIENT_PROVIDERS -- only one of three returns a value.
* SINGLE_SOURCE -- exactly one provider configured.

Plus the iron-law guards:

* float input is rejected loudly,
* string input is coerced to Decimal,
* threshold and tolerance defaults map onto the configured per-field
  values from ``tolerances.py``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.provider_quorum import QuorumAction, QuorumStatus
from app.services.data_quality import QuorumService
from app.services.data_quality.tolerances import (
    EXACT_TOLERANCE,
    PRICE_TOLERANCE_PCT,
    VOLUME_TOLERANCE_PCT,
)


@pytest.fixture
def service() -> QuorumService:
    return QuorumService()


# ---------------------------------------------------------------------------
# QUORUM_REACHED
# ---------------------------------------------------------------------------


def test_three_providers_all_agree_within_tolerance(service: QuorumService) -> None:
    result = service.validate(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider_values={
            "fmp": Decimal("100.10"),
            "yfinance": Decimal("100.20"),
            "finnhub": Decimal("100.15"),
        },
    )
    assert result.status == QuorumStatus.QUORUM_REACHED
    assert result.action == QuorumAction.ACCEPTED
    assert result.quorum_value is not None
    # All three are within 0.5% of the median (100.15) so the agreeing
    # set is the full responding set; quorum value is the median.
    assert result.quorum_value == Decimal("100.15")
    assert set(result.agreeing_providers) == {"fmp", "yfinance", "finnhub"}
    assert result.disagreeing_providers == ()


def test_two_of_three_within_tolerance_yields_quorum(service: QuorumService) -> None:
    # finnhub is the outlier (>0.5% off the median of 100.10/100.20/120).
    result = service.validate(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider_values={
            "fmp": Decimal("100.10"),
            "yfinance": Decimal("100.20"),
            "finnhub": Decimal("120.00"),
        },
    )
    assert result.status == QuorumStatus.QUORUM_REACHED
    # Outlier present -> action is FLAGGED_FOR_REVIEW, not ACCEPTED.
    assert result.action == QuorumAction.FLAGGED_FOR_REVIEW
    assert "finnhub" in result.disagreeing_providers
    assert set(result.agreeing_providers) == {"fmp", "yfinance"}


# ---------------------------------------------------------------------------
# DISAGREEMENT
# ---------------------------------------------------------------------------


def test_all_three_providers_disagree_yields_disagreement(
    service: QuorumService,
) -> None:
    # Spread these so no two providers are within 0.5% of the median.
    # Median is 110; 100, 110, 120 -> deviations 9.1%, 0%, 9.1%. Only
    # one provider (110) is within tolerance, which is below the 2-of-3
    # threshold.
    result = service.validate(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider_values={
            "fmp": Decimal("100"),
            "yfinance": Decimal("110"),
            "finnhub": Decimal("120"),
        },
    )
    assert result.status == QuorumStatus.DISAGREEMENT
    assert result.action == QuorumAction.REJECTED
    assert result.quorum_value is None
    # Spread / |median| = 20 / 110 ~= 0.181818
    assert result.max_disagreement_pct is not None
    assert result.max_disagreement_pct > Decimal("0.18")


# ---------------------------------------------------------------------------
# INSUFFICIENT_PROVIDERS
# ---------------------------------------------------------------------------


def test_only_one_of_three_returns_value_yields_insufficient(
    service: QuorumService,
) -> None:
    result = service.validate(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider_values={
            "fmp": Decimal("100.10"),
            "yfinance": None,
            "finnhub": None,
        },
    )
    assert result.status == QuorumStatus.INSUFFICIENT_PROVIDERS
    assert result.action == QuorumAction.FLAGGED_FOR_REVIEW
    assert result.quorum_value is None


# ---------------------------------------------------------------------------
# SINGLE_SOURCE
# ---------------------------------------------------------------------------


def test_single_configured_source_logs_single_source(service: QuorumService) -> None:
    result = service.validate(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider_values={"fmp": Decimal("100.10")},
    )
    assert result.status == QuorumStatus.SINGLE_SOURCE
    assert result.action == QuorumAction.FLAGGED_FOR_REVIEW
    # We still surface the value so a caller can choose to use it; the
    # FLAGGED_FOR_REVIEW action is the not-silent signal.
    assert result.quorum_value == Decimal("100.10")
    assert result.agreeing_providers == ("fmp",)


# ---------------------------------------------------------------------------
# Per-field tolerance + thresholds
# ---------------------------------------------------------------------------


def test_volume_tolerance_uses_field_specific_threshold(
    service: QuorumService,
) -> None:
    # Volume tolerance = 2%. Spread of 1% (101k vs 100k vs 99k) should
    # easily clear, where the same spread would fail for LAST_PRICE
    # (0.5% tolerance).
    spread_within_volume = service.validate(
        symbol="AAPL",
        field_name="VOLUME",
        provider_values={
            "fmp": Decimal("99000"),
            "yfinance": Decimal("100000"),
            "finnhub": Decimal("101000"),
        },
    )
    assert spread_within_volume.status == QuorumStatus.QUORUM_REACHED

    spread_outside_price = service.validate(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider_values={
            "fmp": Decimal("99"),
            "yfinance": Decimal("100"),
            "finnhub": Decimal("101"),
        },
    )
    # Median 100, 99/100/101 -> +/-1% deviation, exceeds 0.5% price
    # tolerance. Only the median value itself is within tolerance, so
    # we fall short of the 2-of-3 threshold.
    assert spread_outside_price.status == QuorumStatus.DISAGREEMENT
    # Sanity: the documented constants are the ones in play.
    assert PRICE_TOLERANCE_PCT < VOLUME_TOLERANCE_PCT


def test_explicit_threshold_override_tightens_quorum(service: QuorumService) -> None:
    # Two of three agree (100.10 + 100.20 within 0.5% of median 100.20),
    # one diverges. Default 0.667 threshold = quorum reached. Bumping
    # to 1.0 means we require unanimous agreement -> disagreement.
    values = {
        "fmp": Decimal("100.10"),
        "yfinance": Decimal("100.20"),
        "finnhub": Decimal("120.00"),
    }
    default = service.validate(
        symbol="AAPL", field_name="LAST_PRICE", provider_values=values
    )
    assert default.status == QuorumStatus.QUORUM_REACHED

    strict = service.validate(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider_values=values,
        threshold=Decimal("1.0"),
    )
    assert strict.status == QuorumStatus.DISAGREEMENT


# ---------------------------------------------------------------------------
# Input hygiene
# ---------------------------------------------------------------------------


def test_float_input_is_rejected_loudly(service: QuorumService) -> None:
    with pytest.raises(TypeError, match="refuses float"):
        service.validate(
            symbol="AAPL",
            field_name="LAST_PRICE",
            provider_values={
                "fmp": Decimal("100.10"),
                "yfinance": 100.20,  # float -- forbidden
            },
        )


def test_string_input_is_coerced_to_decimal(service: QuorumService) -> None:
    result = service.validate(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider_values={
            "fmp": "100.10",
            "yfinance": "100.20",
            "finnhub": "100.15",
        },
    )
    assert result.status == QuorumStatus.QUORUM_REACHED
    assert result.quorum_value == Decimal("100.15")


def test_bool_input_is_rejected(service: QuorumService) -> None:
    with pytest.raises(TypeError, match="bool"):
        service.validate(
            symbol="AAPL",
            field_name="LAST_PRICE",
            provider_values={
                "fmp": Decimal("100.10"),
                "yfinance": True,
            },
        )


# ---------------------------------------------------------------------------
# Exact-match (string-ish) fields
# ---------------------------------------------------------------------------


def test_exact_match_field_quorum(service: QuorumService) -> None:
    # 2 of 3 agree on the same numeric placeholder (we use Decimal
    # encoding for exact-match fields too -- the ticker hash is fed in
    # as a Decimal by the caller).
    result = service.validate(
        symbol="AAPL",
        field_name="TICKER",
        provider_values={
            "fmp": Decimal("1"),
            "yfinance": Decimal("1"),
            "finnhub": Decimal("2"),
        },
    )
    assert result.status == QuorumStatus.QUORUM_REACHED
    assert result.quorum_value == Decimal("1")
    assert "finnhub" in result.disagreeing_providers


def test_exact_match_field_all_disagree(service: QuorumService) -> None:
    result = service.validate(
        symbol="AAPL",
        field_name="TICKER",
        provider_values={
            "fmp": Decimal("1"),
            "yfinance": Decimal("2"),
            "finnhub": Decimal("3"),
        },
    )
    # Largest bucket has 1 of 3 = 0.333 < 0.667 threshold.
    assert result.status == QuorumStatus.DISAGREEMENT
    assert result.quorum_value is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_zero_median_treats_only_zero_as_agreeing(service: QuorumService) -> None:
    # Volume genuinely zero (e.g., halted symbol). Two providers report
    # 0, one reports 100. Quorum reached on zero.
    result = service.validate(
        symbol="HALTED",
        field_name="VOLUME",
        provider_values={
            "fmp": Decimal("0"),
            "yfinance": Decimal("0"),
            "finnhub": Decimal("100"),
        },
    )
    assert result.status == QuorumStatus.QUORUM_REACHED
    assert result.quorum_value == Decimal("0")


def test_threshold_must_be_in_unit_interval() -> None:
    with pytest.raises(ValueError):
        QuorumService(default_threshold=Decimal("0"))
    with pytest.raises(ValueError):
        QuorumService(default_threshold=Decimal("1.5"))


def test_empty_provider_values_raises(service: QuorumService) -> None:
    with pytest.raises(ValueError):
        service.validate(
            symbol="AAPL", field_name="LAST_PRICE", provider_values={}
        )


def test_quorum_result_fields_present_for_disagreement(
    service: QuorumService,
) -> None:
    result = service.validate(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider_values={
            "fmp": Decimal("100"),
            "yfinance": Decimal("110"),
            "finnhub": Decimal("120"),
        },
    )
    log = result.to_log_dict()
    assert log == {"fmp": "100", "yfinance": "110", "finnhub": "120"}
    assert result.quorum_threshold > 0
    assert result.symbol == "AAPL"
    assert result.field_name == "LAST_PRICE"


def test_exact_tolerance_constant_is_zero() -> None:
    assert EXACT_TOLERANCE == Decimal("0")
