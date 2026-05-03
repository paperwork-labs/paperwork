# `money`

Shared **integer-cent** money type for Paperwork Labs Python backends: safe
arithmetic, human string parsing, and Pydantic v2 validation hooks.

## Why integer cents (not `Decimal` or `float` in the hot path)?

* **Floats** are unsafe for currency: `0.1 + 0.2 != 0.3` in binary IEEE-754.
  Any aggregate built on floats can drift from ledger truth.
* **`Decimal` in arithmetic** avoids float bugs but still invites subtle
  rounding mistakes if every operation does not share one coordinated
  context (scale, rounding mode, quantize targets).
* **Integer minor units** (here: cents) make every `+ / - / *` exact until
  you *explicitly* choose where to round (e.g. splitting totals across
  lines). Division is the only place this library applies **half-up**
  rounding, via :func:`money.rounding.round_half_up_div`.

`Money.to_dollars()` returns a `Decimal` **for display or boundary conversion
only** — production math stays on integers.

## Public API

```python
from money import Money, parse_currency_string, round_half_up_div

# Construction
Money.from_cents(12345)                    # $123.45 USD
Money.from_dollars("1,234.56")             # commas + optional $
parse_currency_string("USD (1.00)")        # prefix + accounting parens

# Arithmetic (same currency only; else ValueError)
Money.from_cents(100) + Money.from_cents(50)
Money.from_cents(10) / 3                 # half-up cents -> 3

# Display
str(Money.from_cents(-99))               # '-$0.99'
m.to_dollars()                           # Decimal('0.99')

# Pydantic v2
from pydantic import BaseModel

class Row(BaseModel):
    price: Money

Row.model_validate({"price": {"cents": 199, "currency": "USD"}})
Money.model_validate({"cents": 199})
Money.from_orm(some_sqlalchemy_row)      # alias for model_validate
```

### Exported symbols

| Symbol | Role |
| --- | --- |
| `Money` | Frozen dataclass: `cents: int`, `currency: str` |
| `parse_currency_string` | Parse `"$1,234.56"`, `"USD 9.99"`, `"(1.00)"`, etc. |
| `signed_decimal_from_amount_text` | Lower-level amount text → `Decimal` |
| `round_half_up_div` | Integer half-up (half away from zero) quotient |

## Development

```bash
cd packages/python/money
uv sync --extra test
uv run pytest --cov=money --cov-report=term-missing
uv run ruff check . && uv run ruff format --check .
```

## Plan

Wave K6 extraction is tracked in the monorepo platform plan:
`.cursor/plans/plan_1a0d246a.plan.md`.
