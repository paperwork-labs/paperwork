"""Tests for :mod:`money.rounding`."""

from __future__ import annotations

import pytest

from money.rounding import round_half_up_div


def test_half_up_positive() -> None:
    assert round_half_up_div(5, 2) == 3
    assert round_half_up_div(4, 2) == 2
    assert round_half_up_div(1, 2) == 1


def test_half_up_negative_numerator() -> None:
    assert round_half_up_div(-5, 2) == -3
    assert round_half_up_div(-4, 2) == -2


def test_half_up_negative_denominator() -> None:
    assert round_half_up_div(5, -2) == -3
    assert round_half_up_div(-5, -2) == 3


def test_exact_division() -> None:
    assert round_half_up_div(100, 10) == 10


def test_zero_denominator() -> None:
    with pytest.raises(ZeroDivisionError):
        round_half_up_div(1, 0)


def test_zero_numerator() -> None:
    assert round_half_up_div(0, 7) == 0
