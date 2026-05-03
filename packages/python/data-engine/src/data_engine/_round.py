"""Shared rounding helper. Matches JS `Math.round((numerator) / denominator)`.

The TS canonical engine in packages/data/src/engine/tax.ts uses
`Math.round((taxableInBracket * bracket.rate_bps) / 10000)`. JavaScript's
Math.round is round-half-toward-positive-infinity (half up). Python's built-in
`round()` is round-half-to-even (banker's). To match the TS engine
byte-for-byte, this module implements explicit half-up using only integers
(no float intermediate, so no precision drift on large dollar amounts).

For all of FileFree's existing test inputs (whole-dollar income), this helper
produces identical results to FileFree's `tax += amount * rate // 100` floor
math, because the products are exact multiples of the divisor.
"""

from __future__ import annotations


def round_half_up_div(numerator: int, denominator: int) -> int:
    """Integer-only round-half-toward-positive-infinity division.

    Equivalent to `Math.round(numerator / denominator)` for any sign of
    numerator. Requires `denominator > 0`.

    Examples (matching JS Math.round):
      round_half_up_div(1, 2)   ==  1   # 0.5  -> 1
      round_half_up_div(-1, 2)  ==  0   # -0.5 -> 0  (toward +inf)
      round_half_up_div(-3, 2)  == -1   # -1.5 -> -1 (toward +inf)
      round_half_up_div(-2, 2)  == -1   # -1.0 -> -1
    """
    if denominator <= 0:
        raise ValueError(f"denominator must be positive, got {denominator}")

    abs_n = numerator if numerator >= 0 else -numerator
    q, r = divmod(abs_n, denominator)

    if numerator >= 0:
        # half-up: r * 2 >= denominator rounds away from zero (i.e., up)
        bump = 1 if r * 2 >= denominator else 0
        return q + bump

    # Negative numerator: Math.round rounds toward +inf, so exact halves
    # round toward zero (e.g. -0.5 -> 0, -1.5 -> -1). Only strictly past
    # the half rounds away from zero.
    bump = 1 if r * 2 > denominator else 0
    return -(q + bump)
