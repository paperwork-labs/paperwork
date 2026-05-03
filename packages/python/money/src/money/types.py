"""Core :class:`Money` type: integer cents, currency-safe arithmetic."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

from money.rounding import round_half_up_div

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler
    from pydantic_core import CoreSchema


def _currency_mismatch(a: str, b: str) -> ValueError:
    return ValueError(f"currency mismatch: {a!r} vs {b!r}")


@dataclass(frozen=True, slots=True)
class Money:
    """Fixed-point money stored as integer **cents** (never floats).

    Arithmetic requires matching ``currency``. Dividing by ``int`` uses
    integer **half-up** rounding (see :func:`money.rounding.round_half_up_div`).
    """

    cents: int
    currency: str = "USD"

    def __post_init__(self) -> None:
        cur = self.currency.strip().upper() or "USD"
        object.__setattr__(self, "currency", cur)

    @classmethod
    def from_cents(cls, cents: int, *, currency: str = "USD") -> Money:
        """Construct from a signed integer cent amount."""
        return cls(cents=cents, currency=currency)

    @classmethod
    def from_dollars(cls, value: str | Decimal, *, currency: str = "USD") -> Money:
        """Parse dollars text (commas, ``$``) or ``Decimal`` into ``Money``.

        Examples::

            Money.from_dollars("1,234.56")  # Money(cents=123456)
            Money.from_dollars(Decimal("0.005"))  # half-up -> 1 cent
        """
        from money.parsing import signed_decimal_from_amount_text

        if isinstance(value, Decimal):
            d = value
        else:
            d = signed_decimal_from_amount_text(value)
        cents_dec = (d * Decimal(100)).to_integral_value(rounding=ROUND_HALF_UP)
        return cls(cents=int(cents_dec), currency=currency)

    # ------------------------------------------------------------------
    # Pydantic v2 integration
    # ------------------------------------------------------------------

    @classmethod
    def model_validate(cls, obj: Any) -> Money:
        """Build ``Money`` from ``Money``, a ``dict``, or an ORM-like object."""
        if isinstance(obj, Money):
            return obj
        if isinstance(obj, dict):
            try:
                c = obj["cents"]
            except KeyError as e:
                msg = "Money mapping must include key 'cents'"
                raise TypeError(msg) from e
            return cls(cents=int(c), currency=str(obj.get("currency", "USD")))
        _sentinel = object()
        cents_attr = getattr(obj, "cents", _sentinel)
        if cents_attr is not _sentinel:
            if isinstance(cents_attr, bool):
                msg = "Money ORM source 'cents' must not be a bool"
                raise TypeError(msg)
            if isinstance(cents_attr, int):
                c = cents_attr
            elif isinstance(cents_attr, str):
                c = int(cents_attr)
            else:
                msg = "Money ORM source 'cents' must be int or numeric str"
                raise TypeError(msg)
            return cls(
                cents=c,
                currency=str(getattr(obj, "currency", "USD")),
            )
        msg = f"cannot coerce {type(obj).__name__!r} to Money"
        raise TypeError(msg)

    @classmethod
    def from_orm(cls, obj: Any) -> Money:
        """Compatibility alias for :meth:`model_validate` (Pydantic v1 naming)."""
        return cls.model_validate(obj)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        from pydantic_core import core_schema

        return core_schema.no_info_plain_validator_function(cls._pydantic_validate)

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        _core_schema: object,
        _handler: object,
    ) -> dict[str, Any]:
        return {
            "title": "Money",
            "type": "object",
            "properties": {
                "cents": {"title": "Cents", "type": "integer"},
                "currency": {"title": "Currency", "type": "string", "default": "USD"},
            },
            "required": ["cents"],
        }

    @classmethod
    def _pydantic_validate(cls, value: Any) -> Money:
        return cls.model_validate(value)

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise _currency_mismatch(self.currency, other.currency)
        return Money(self.cents + other.cents, self.currency)

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise _currency_mismatch(self.currency, other.currency)
        return Money(self.cents - other.cents, self.currency)

    def __mul__(self, other: object) -> Money:
        if not isinstance(other, int):
            return NotImplemented
        return Money(self.cents * other, self.currency)

    def __rmul__(self, other: object) -> Money:
        return self.__mul__(other)

    def __truediv__(self, other: object) -> Money:
        if not isinstance(other, int):
            return NotImplemented
        q = round_half_up_div(self.cents, other)
        return Money(q, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.cents, self.currency)

    def __abs__(self) -> Money:
        return Money(abs(self.cents), self.currency)

    # ------------------------------------------------------------------
    # Comparisons
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise _currency_mismatch(self.currency, other.currency)
        return self.cents == other.cents

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise _currency_mismatch(self.currency, other.currency)
        return self.cents < other.cents

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise _currency_mismatch(self.currency, other.currency)
        return self.cents <= other.cents

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise _currency_mismatch(self.currency, other.currency)
        return self.cents > other.cents

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise _currency_mismatch(self.currency, other.currency)
        return self.cents >= other.cents

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def to_dollars(self) -> Decimal:
        """Exact :class:`~decimal.Decimal` dollars for display (not ``float``)."""
        return Decimal(self.cents) / Decimal(100)

    def __str__(self) -> str:
        neg = self.cents < 0
        n = abs(self.cents)
        dollars = n // 100
        frac = n % 100
        body = f"{dollars:,}.{frac:02d}"
        if neg:
            return f"-${body}"
        return f"${body}"

    def __repr__(self) -> str:
        return f"Money(cents={self.cents}, currency={self.currency!r})"
