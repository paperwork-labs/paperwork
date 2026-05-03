"""Tests for :class:`money.types.Money`."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel, TypeAdapter

from money import Money


def test_from_cents() -> None:
    m = Money.from_cents(100)
    assert m.cents == 100
    assert m.currency == "USD"


def test_from_dollars_string_roundtrip() -> None:
    m = Money.from_dollars("1,234.56")
    assert m.cents == 123_456
    assert str(m) == "$1,234.56"


def test_from_dollars_decimal_half_up() -> None:
    assert Money.from_dollars(Decimal("0.005")).cents == 1
    assert Money.from_dollars(Decimal("0.004")).cents == 0


def test_add_sub() -> None:
    a = Money.from_cents(100)
    b = Money.from_cents(50)
    assert a + b == Money.from_cents(150)
    assert a - b == Money.from_cents(50)


def test_add_currency_mismatch() -> None:
    a = Money.from_cents(1, currency="USD")
    b = Money.from_cents(1, currency="EUR")
    with pytest.raises(ValueError, match="currency mismatch"):
        _ = a + b


def test_mul_rmul() -> None:
    m = Money.from_cents(25)
    assert m * 4 == Money.from_cents(100)
    assert 4 * m == Money.from_cents(100)


def test_mul_not_int() -> None:
    assert Money.from_cents(1).__mul__(1.5) is NotImplemented


def test_add_not_money() -> None:
    assert Money.from_cents(1).__add__(99) is NotImplemented


def test_model_validate_dict_missing_cents() -> None:
    with pytest.raises(TypeError, match="cents"):
        Money.model_validate({"currency": "USD"})


def test_model_validate_bad_type() -> None:
    with pytest.raises(TypeError, match="cannot coerce"):
        Money.model_validate(object())


def test_truediv_half_up() -> None:
    assert Money.from_cents(10) / 4 == Money.from_cents(3)  # 2.5 -> 3
    assert Money.from_cents(-10) / 4 == Money.from_cents(-3)


def test_truediv_zero() -> None:
    with pytest.raises(ZeroDivisionError):
        _ = Money.from_cents(1) / 0


def test_truediv_not_int() -> None:
    assert Money.from_cents(1).__truediv__(1.5) is NotImplemented


def test_neg_abs() -> None:
    m = Money.from_cents(-99)
    assert (-m).cents == 99
    assert abs(m).cents == 99


def test_comparisons() -> None:
    a = Money.from_cents(10)
    b = Money.from_cents(20)
    assert a < b
    assert a <= b
    assert b > a
    assert b >= a
    assert a <= a


def test_eq_same_currency() -> None:
    assert Money.from_cents(5) == Money.from_cents(5)


def test_eq_currency_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="currency mismatch"):
        _ = Money.from_cents(1, currency="USD") == Money.from_cents(1, currency="EUR")


def test_eq_not_money() -> None:
    assert Money.from_cents(1).__eq__(42) is NotImplemented


def test_lt_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="currency mismatch"):
        _ = Money.from_cents(1, currency="USD") < Money.from_cents(2, currency="EUR")


def test_str_formatting() -> None:
    assert str(Money.from_cents(0)) == "$0.00"
    assert str(Money.from_cents(-1)) == "-$0.01"
    assert str(Money.from_cents(123456789)) == "$1,234,567.89"


def test_to_dollars_decimal_only() -> None:
    d = Money.from_cents(1).to_dollars()
    assert isinstance(d, Decimal)
    assert d == Decimal("0.01")


def test_currency_normalized() -> None:
    m = Money(0, " eur ")
    assert m.currency == "EUR"


def test_pydantic_model_validate_dict() -> None:
    m = Money.model_validate({"cents": 42, "currency": "usd"})
    assert m == Money.from_cents(42, currency="USD")


def test_pydantic_model_validate_orm_like() -> None:
    class Row:
        cents = 7
        currency = "USD"

    assert Money.model_validate(Row()) == Money.from_cents(7)


def test_pydantic_model_validate_orm_str_cents() -> None:
    class Row:
        cents = "99"

    assert Money.model_validate(Row()).cents == 99


def test_pydantic_model_validate_orm_bool_cents_rejected() -> None:
    class Row:
        cents = True

    with pytest.raises(TypeError, match="bool"):
        Money.model_validate(Row())


def test_pydantic_model_validate_orm_bad_cents_type() -> None:
    class Row:
        cents = 3.14

    with pytest.raises(TypeError, match="int or numeric str"):
        Money.model_validate(Row())


def test_pydantic_nested_model() -> None:
    class Invoice(BaseModel):
        total: Money

    inv = Invoice.model_validate({"total": {"cents": 199, "currency": "USD"}})
    assert inv.total.cents == 199


def test_comparison_not_money() -> None:
    m = Money.from_cents(1)
    assert m.__lt__(1) is NotImplemented
    assert m.__le__(1) is NotImplemented
    assert m.__gt__(1) is NotImplemented
    assert m.__ge__(1) is NotImplemented


def test_from_orm_alias() -> None:
    assert Money.from_orm({"cents": 3}) == Money.from_cents(3)


def test_model_validate_money_identity() -> None:
    m = Money.from_cents(9)
    assert Money.model_validate(m) is m


def test_sub_currency_mismatch() -> None:
    a = Money.from_cents(1, currency="USD")
    b = Money.from_cents(1, currency="EUR")
    with pytest.raises(ValueError, match="currency mismatch"):
        _ = a - b


def test_repr() -> None:
    assert repr(Money.from_cents(12)) == "Money(cents=12, currency='USD')"


def test_type_adapter_validate() -> None:
    adapter = TypeAdapter(Money)
    got = adapter.validate_python({"cents": 55, "currency": "USD"})
    assert got == Money.from_cents(55)


def test_sub_not_money() -> None:
    assert Money.from_cents(1).__sub__(1) is NotImplemented
