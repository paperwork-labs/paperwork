"""Pure adjustment math for corporate actions.

Every function here:

* takes ``Decimal`` inputs (or values that ``_to_decimal`` accepts),
* returns an :class:`AdjustmentResult` with ``Decimal`` fields,
* never touches the database, the ORM, or external services,
* is fully deterministic and side-effect free.

This separation matters: the applier wraps these in per-user savepoints,
the historical OHLCV adjuster reuses ``decimal_ratio``, and unit tests
can exhaustively cover edge cases (3-for-1 splits, 1-for-10 reverse
splits, 5% stock dividends, cash buyouts) without any DB fixtures.

Precision policy
----------------
* Adjustment math runs at ``getcontext().prec >= 28`` so intermediate
  divisions don't drift.
* Output quantities are quantized to 6 dp (matches
  ``Position.quantity`` ``DECIMAL(15, 6)`` and is more precise than
  ``TaxLot.quantity`` ``Float``, which the applier converts at the
  boundary).
* Output cost-basis totals are quantized to 4 dp (matches
  ``Position.average_cost`` ``DECIMAL(15, 4)``).
* Per-share values use 8 dp internally for ratio safety.

ROUND_HALF_EVEN ("banker's rounding") is used everywhere -- it's the
financial-industry default and avoids the systematic upward bias of
ROUND_HALF_UP.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from typing import Optional, Union

# 28 is the cpython default; we set it explicitly so a downstream
# library that lowers it can't silently corrupt our math.
if getcontext().prec < 28:  # pragma: no cover - environment guard
    getcontext().prec = 28


_ZERO = Decimal("0")
_QTY_QUANT = Decimal("0.000001")  # 6 dp -- matches Position.quantity
_COST_TOTAL_QUANT = Decimal("0.0001")  # 4 dp -- matches average_cost
_PER_SHARE_QUANT = Decimal("0.00000001")  # 8 dp -- internal precision

DecimalLike = Union[Decimal, int, str, float]


@dataclass(frozen=True)
class AdjustmentResult:
    """Result of applying one corporate action to one holding.

    All numeric fields are ``Decimal``. ``new_symbol`` is non-None only
    for symbol-changing actions (mergers, name changes); the applier
    uses it to update the live row's ``symbol`` column.
    """

    new_qty: Decimal
    new_cost_basis: Decimal
    new_avg_cost: Decimal
    cash_credited: Decimal = _ZERO
    new_symbol: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_decimal(value: DecimalLike) -> Decimal:
    """Coerce ``value`` to ``Decimal`` without losing precision.

    Python ``float`` -> ``Decimal`` goes through ``str()`` to avoid
    binary-float artifacts (e.g. ``Decimal(0.1) == Decimal("0.10000...555")``).
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


def _quantize_qty(value: Decimal) -> Decimal:
    return value.quantize(_QTY_QUANT, rounding=ROUND_HALF_EVEN)


def _quantize_cost_total(value: Decimal) -> Decimal:
    return value.quantize(_COST_TOTAL_QUANT, rounding=ROUND_HALF_EVEN)


def _quantize_per_share(value: Decimal) -> Decimal:
    return value.quantize(_PER_SHARE_QUANT, rounding=ROUND_HALF_EVEN)


def decimal_ratio(numerator: DecimalLike, denominator: DecimalLike) -> Decimal:
    """Decimal division with explicit zero-denominator guard.

    Used by the applier *and* the OHLCV adjuster to derive the
    multiplier to apply to historical prices/volumes.
    """
    num = _to_decimal(numerator)
    den = _to_decimal(denominator)
    if den == _ZERO:
        raise ValueError("ratio denominator must be non-zero")
    return num / den


def _split_like_adjust(
    current_qty: Decimal,
    current_cost_basis: Decimal,
    multiplier: Decimal,
) -> AdjustmentResult:
    """Shared math for forward splits, reverse splits, stock dividends.

    A multiplier > 1 multiplies share count and divides per-share cost.
    Total cost basis is invariant -- this is the cardinal rule of
    split-style adjustments and the property the unit tests pin down.
    """
    if multiplier <= _ZERO:
        raise ValueError("split-like multiplier must be positive")

    new_qty = _quantize_qty(current_qty * multiplier)
    # Total basis is unchanged; quantize it for storage parity.
    new_cost_basis = _quantize_cost_total(current_cost_basis)

    if new_qty == _ZERO:
        new_avg_cost = _ZERO
    else:
        new_avg_cost = _quantize_per_share(new_cost_basis / new_qty)

    return AdjustmentResult(
        new_qty=new_qty,
        new_cost_basis=new_cost_basis,
        new_avg_cost=new_avg_cost,
    )


# ---------------------------------------------------------------------------
# Public adjusters
# ---------------------------------------------------------------------------


def adjust_for_split(
    current_qty: DecimalLike,
    current_cost_basis: DecimalLike,
    ratio_numerator: DecimalLike,
    ratio_denominator: DecimalLike,
) -> AdjustmentResult:
    """Forward stock split (e.g. 3-for-1 -> numerator=3, denominator=1).

    Pre: ratio > 1 (forward split). Caller should route 1-for-N to
    :func:`adjust_for_reverse_split`; we don't enforce the directionality
    here because some providers report 1-for-10 reverse splits as
    ``num=1, den=10`` and we want :func:`adjust_for_split` to remain the
    safe single entry point.
    """
    multiplier = decimal_ratio(ratio_numerator, ratio_denominator)
    return _split_like_adjust(
        _to_decimal(current_qty),
        _to_decimal(current_cost_basis),
        multiplier,
    )


def adjust_for_reverse_split(
    current_qty: DecimalLike,
    current_cost_basis: DecimalLike,
    ratio_numerator: DecimalLike,
    ratio_denominator: DecimalLike,
) -> AdjustmentResult:
    """Reverse stock split (e.g. 1-for-10 -> numerator=1, denominator=10).

    Mathematically identical to :func:`adjust_for_split`; named
    separately for call-site clarity and because the caller routes off
    ``CorporateActionType``.
    """
    multiplier = decimal_ratio(ratio_numerator, ratio_denominator)
    return _split_like_adjust(
        _to_decimal(current_qty),
        _to_decimal(current_cost_basis),
        multiplier,
    )


def adjust_for_stock_dividend(
    current_qty: DecimalLike,
    current_cost_basis: DecimalLike,
    ratio_numerator: DecimalLike,
    ratio_denominator: DecimalLike,
) -> AdjustmentResult:
    """Stock (bonus-share) dividend.

    Modeled as a tiny split: a 5% stock dividend is ``num=21, den=20``
    (qty grows by 5%). Cost basis stays constant; per-share cost
    drops proportionally. Identical math to a split.
    """
    multiplier = decimal_ratio(ratio_numerator, ratio_denominator)
    return _split_like_adjust(
        _to_decimal(current_qty),
        _to_decimal(current_cost_basis),
        multiplier,
    )


def adjust_for_cash_dividend(
    current_qty: DecimalLike,
    current_cost_basis: DecimalLike,
    cash_per_share: DecimalLike,
) -> AdjustmentResult:
    """Cash dividend.

    Cash dividends do **not** change quantity or cost basis. The applier
    records ``cash_credited = qty * cash_per_share`` so downstream
    accounting (AccountBalance, tax journal) can ingest the cash leg
    without re-querying the action. We deliberately do NOT write to
    AccountBalance here -- that's a separate sync responsibility.
    """
    qty = _to_decimal(current_qty)
    basis = _to_decimal(current_cost_basis)
    cps = _to_decimal(cash_per_share)
    cash = _quantize_cost_total(qty * cps)

    if qty == _ZERO:
        avg_cost = _ZERO
    else:
        avg_cost = _quantize_per_share(basis / qty)

    return AdjustmentResult(
        new_qty=_quantize_qty(qty),
        new_cost_basis=_quantize_cost_total(basis),
        new_avg_cost=avg_cost,
        cash_credited=cash,
    )


def adjust_for_merger_stock(
    current_qty: DecimalLike,
    current_cost_basis: DecimalLike,
    target_symbol: str,
    ratio_numerator: DecimalLike,
    ratio_denominator: DecimalLike,
) -> AdjustmentResult:
    """Stock-for-stock merger (e.g. 1.05 shares of NEWCO per old share).

    The acquirer's symbol is recorded in ``new_symbol`` so the applier
    can re-tag the live ``Position`` / ``TaxLot`` row in place.
    Cost basis carries over to the new symbol unchanged (per IRS Pub.
    550 for tax-free reorganizations); per-share cost adjusts by the
    exchange ratio.

    Cash-and-stock mergers are not modeled here -- v1 routes those to
    ``adjust_for_merger_cash`` (for the cash leg) and would require a
    second adjuster pass for the stock leg. Out of scope until a real
    cash-and-stock event lands.
    """
    if not target_symbol:
        raise ValueError("merger_stock requires target_symbol")
    multiplier = decimal_ratio(ratio_numerator, ratio_denominator)
    base = _split_like_adjust(
        _to_decimal(current_qty),
        _to_decimal(current_cost_basis),
        multiplier,
    )
    return AdjustmentResult(
        new_qty=base.new_qty,
        new_cost_basis=base.new_cost_basis,
        new_avg_cost=base.new_avg_cost,
        cash_credited=_ZERO,
        new_symbol=target_symbol.upper(),
    )


def adjust_for_merger_cash(
    current_qty: DecimalLike,
    current_cost_basis: DecimalLike,
    cash_per_share: DecimalLike,
) -> AdjustmentResult:
    """Cash buyout. Position closes; ``new_qty`` and ``new_cost_basis``
    go to zero; ``cash_credited = qty * cash_per_share``.

    The applier interprets ``new_qty == 0`` as a signal to flip
    ``Position.status`` to ``CLOSED``. ``cash_credited`` is recorded on
    the audit row for downstream cash reconciliation.
    """
    qty = _to_decimal(current_qty)
    cps = _to_decimal(cash_per_share)
    cash = _quantize_cost_total(qty * cps)

    return AdjustmentResult(
        new_qty=_ZERO,
        new_cost_basis=_ZERO,
        new_avg_cost=_ZERO,
        cash_credited=cash,
    )
