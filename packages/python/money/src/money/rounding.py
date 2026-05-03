"""Integer half-up division (half away from zero).

Matches common tax/money rounding.
"""


def round_half_up_div(numerator: int, denominator: int) -> int:
    """Return ``round(numerator / denominator)`` using half-up (half away from zero).

    Ties (remainder exactly half of ``|denominator|``) increase magnitude
    (e.g. ``5 // 2 -> 3``, ``-5 // 2 -> -3``), consistent with
    :class:`decimal.Decimal` rounding mode ``ROUND_HALF_UP`` for non-zero results.

    Args:
        numerator: Signed integer dividend.
        denominator: Signed integer divisor; must not be zero.

    Returns:
        The quotient rounded to the nearest ``int``.

    Raises:
        ZeroDivisionError: If ``denominator`` is zero.
    """
    if denominator == 0:
        msg = "integer division or modulo by zero"
        raise ZeroDivisionError(msg)

    n, d = numerator, denominator
    sign = 1 if n * d >= 0 else -1
    n_abs = abs(n)
    d_abs = abs(d)
    q = n_abs // d_abs
    r = n_abs % d_abs
    twice_r = r * 2
    if twice_r > d_abs or twice_r == d_abs:
        q += 1
    return sign * q
