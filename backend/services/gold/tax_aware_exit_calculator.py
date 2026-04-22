"""Tax-aware exit calculator.

Given an open position, a proposed exit size, and the matched lot cost basis,
compute after-tax proceeds, short- vs long-term capital-gain split, federal +
state + NIIT tax drag, and the "days to long-term" breakeven that tells the
user how much additional price move it would take for waiting to matter.

All monetary math is ``Decimal``. Defaults are deliberately conservative
(top-bracket federal + middle state + NIIT) so the calculator never
understates tax drag when a user's TaxProfile is missing.

There is no user-level ``TaxProfile`` model in the main branch today; the
shape of this module's ``TaxProfile`` dataclass is the interface a future
persistent model will populate. Until then, callers pass either a hand-built
profile or let the calculator fall back to the conservative defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

# match TaxLot.is_long_term: held > 365 per IRS Publication 550
def _is_long_term_held(held_days: int) -> bool:
    return held_days > 365


# Calendar days to first eligibility for long-term treatment (i.e. first day
# when (as_of - acquired).days can exceed 365). Used for cutoff date helper.
_LONG_TERM_MIN_CALENDAR_SPAN = 366

# Conservative defaults. Source: IRS 2025 top brackets. Effective rates for
# most users will be lower; these are the "never under-state tax drag"
# baseline described above.
DEFAULT_FEDERAL_ST_RATE = Decimal("0.37")    # ordinary income top bracket
DEFAULT_FEDERAL_LT_RATE = Decimal("0.20")    # long-term top bracket
DEFAULT_STATE_RATE = Decimal("0.05")         # middle-of-pack state income tax
DEFAULT_NIIT_RATE = Decimal("0.038")         # Net Investment Income Tax
DEFAULT_NIIT_APPLIES = True

TWO_PLACES = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    """Quantize to cents, half-up rounding (money)."""
    return x.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TaxProfile:
    """User-specific tax parameters.

    All rates are fractions (``0.20`` = 20%), not percentages. ``state`` is
    retained for diagnostics / future per-state lookup tables.
    """

    federal_short_term_rate: Decimal = DEFAULT_FEDERAL_ST_RATE
    federal_long_term_rate: Decimal = DEFAULT_FEDERAL_LT_RATE
    state_rate: Decimal = DEFAULT_STATE_RATE
    niit_rate: Decimal = DEFAULT_NIIT_RATE
    niit_applies: bool = DEFAULT_NIIT_APPLIES
    state: Optional[str] = None

    @classmethod
    def conservative_default(cls) -> "TaxProfile":
        return cls()


@dataclass(frozen=True)
class ExitLot:
    """A single cost-basis lot participating in a proposed exit."""

    shares: Decimal
    cost_per_share: Decimal
    acquired_on: date


@dataclass(frozen=True)
class TaxAwareExitResult:
    """Structured output. Every field is ``Decimal`` (money) or explicit bool."""

    symbol: str
    shares_exited: Decimal
    gross_proceeds: Decimal
    cost_basis: Decimal
    realized_gain_loss: Decimal
    short_term_gain_loss: Decimal
    long_term_gain_loss: Decimal
    federal_tax: Decimal
    state_tax: Decimal
    niit_tax: Decimal
    total_tax: Decimal
    after_tax_proceeds: Decimal
    tax_advantaged: bool
    days_to_long_term: Optional[int]
    breakeven_price_for_long_term_wait: Optional[Decimal]
    reasons: List[str] = field(default_factory=list)

    def to_payload(self) -> dict:
        def _f(v: Optional[Decimal]) -> Optional[float]:
            return float(v) if v is not None else None

        return {
            "symbol": self.symbol,
            "shares_exited": float(self.shares_exited),
            "gross_proceeds": _f(self.gross_proceeds),
            "cost_basis": _f(self.cost_basis),
            "realized_gain_loss": _f(self.realized_gain_loss),
            "short_term_gain_loss": _f(self.short_term_gain_loss),
            "long_term_gain_loss": _f(self.long_term_gain_loss),
            "federal_tax": _f(self.federal_tax),
            "state_tax": _f(self.state_tax),
            "niit_tax": _f(self.niit_tax),
            "total_tax": _f(self.total_tax),
            "after_tax_proceeds": _f(self.after_tax_proceeds),
            "tax_advantaged": self.tax_advantaged,
            "days_to_long_term": self.days_to_long_term,
            "breakeven_price_for_long_term_wait": _f(
                self.breakeven_price_for_long_term_wait
            ),
            "reasons": list(self.reasons),
        }


class TaxAwareExitCalculator:
    """Pure calculator. Accepts explicit inputs; performs no DB I/O."""

    def __init__(self, profile: Optional[TaxProfile] = None) -> None:
        self._profile = profile or TaxProfile.conservative_default()

    def evaluate(
        self,
        *,
        symbol: str,
        current_price: Decimal,
        exit_shares: Decimal,
        lots: List[ExitLot],
        as_of: Optional[date] = None,
        tax_advantaged: bool = False,
    ) -> TaxAwareExitResult:
        """Compute tax impact of selling ``exit_shares`` of ``symbol``.

        ``lots`` should be ordered in the sequence the caller wants them
        consumed (FIFO by default from the caller's side). Providing fewer
        lot-shares than ``exit_shares`` is a data-integrity error and returns
        a zeroed result with a clear reason.
        """
        sym = (symbol or "").upper().strip()
        as_of = as_of or date.today()
        reasons: List[str] = []

        if exit_shares <= Decimal("0"):
            reasons.append("proposed exit size is zero or negative")
            return self._empty(sym, tax_advantaged, reasons)

        if current_price <= Decimal("0"):
            reasons.append("current price is zero or negative")
            return self._empty(sym, tax_advantaged, reasons)

        # Consume lots in order until we have filled ``exit_shares``.
        remaining = exit_shares
        cost_basis = Decimal("0")
        st_gain = Decimal("0")
        lt_gain = Decimal("0")
        min_days_to_lt: Optional[int] = None
        filled = Decimal("0")

        for lot in lots:
            if remaining <= Decimal("0"):
                break
            take = lot.shares if lot.shares <= remaining else remaining
            if take <= Decimal("0"):
                continue
            lot_basis = take * lot.cost_per_share
            lot_proceeds = take * current_price
            lot_gain = lot_proceeds - lot_basis
            cost_basis += lot_basis
            held_days = (as_of - lot.acquired_on).days
            if _is_long_term_held(held_days):
                lt_gain += lot_gain
            else:
                st_gain += lot_gain
                days_left = days_to_long_term(lot.acquired_on, as_of)
                if min_days_to_lt is None or days_left < min_days_to_lt:
                    min_days_to_lt = days_left
            remaining -= take
            filled += take

        if filled < exit_shares:
            reasons.append(
                f"lots cover only {filled} of {exit_shares} requested shares"
            )
            return self._empty(sym, tax_advantaged, reasons)

        gross_proceeds = filled * current_price
        realized = st_gain + lt_gain

        if tax_advantaged:
            reasons.append(
                "Tax-advantaged account (IRA / Roth / HSA): no immediate "
                "tax drag on this exit"
            )
            return TaxAwareExitResult(
                symbol=sym,
                shares_exited=filled,
                gross_proceeds=_q(gross_proceeds),
                cost_basis=_q(cost_basis),
                realized_gain_loss=_q(realized),
                short_term_gain_loss=_q(st_gain),
                long_term_gain_loss=_q(lt_gain),
                federal_tax=Decimal("0.00"),
                state_tax=Decimal("0.00"),
                niit_tax=Decimal("0.00"),
                total_tax=Decimal("0.00"),
                after_tax_proceeds=_q(gross_proceeds),
                tax_advantaged=True,
                days_to_long_term=None,
                breakeven_price_for_long_term_wait=None,
                reasons=reasons,
            )

        profile = self._profile
        # Only positive gains are taxable; losses reduce drag (and, depending
        # on the user's other realized gains, can be harvested). We do NOT
        # try to model loss offsetting here because that requires the user's
        # YTD realized-gains ledger.
        taxable_st = st_gain if st_gain > Decimal("0") else Decimal("0")
        taxable_lt = lt_gain if lt_gain > Decimal("0") else Decimal("0")

        federal_tax = (
            taxable_st * profile.federal_short_term_rate
            + taxable_lt * profile.federal_long_term_rate
        )
        state_tax = (taxable_st + taxable_lt) * profile.state_rate
        niit_tax = (
            (taxable_st + taxable_lt) * profile.niit_rate
            if profile.niit_applies
            else Decimal("0")
        )
        total_tax = federal_tax + state_tax + niit_tax
        after_tax = gross_proceeds - total_tax

        breakeven_price: Optional[Decimal] = None
        if min_days_to_lt is not None and st_gain > Decimal("0"):
            # The tax delta per share of ST vs LT federal (the portion that
            # depends on holding period). NIIT + state are holding-period
            # agnostic at this conservative-defaults level, so do not get
            # subtracted. This is the move required to recover the ST->LT
            # federal spread and make "wait" break even with "scale now".
            federal_spread_rate = (
                profile.federal_short_term_rate - profile.federal_long_term_rate
            )
            if federal_spread_rate > Decimal("0") and filled > Decimal("0"):
                savings_if_lt = taxable_st * federal_spread_rate
                breakeven_price = current_price - (savings_if_lt / filled)
                if breakeven_price < Decimal("0"):
                    breakeven_price = Decimal("0")
                reasons.append(
                    f"Waiting {min_days_to_lt} day(s) for long-term converts "
                    f"~${_q(savings_if_lt)} of federal drag; breakeven "
                    f"requires price to hold >= ${_q(breakeven_price)}"
                )
            else:
                reasons.append(
                    "Federal ST rate not greater than LT; no waiting premium"
                )

        if st_gain > Decimal("0"):
            reasons.append(
                f"Short-term gain ${_q(st_gain)} taxed at ordinary rates"
            )
        if lt_gain > Decimal("0"):
            reasons.append(
                f"Long-term gain ${_q(lt_gain)} at preferential rate"
            )
        if realized < Decimal("0"):
            reasons.append(
                f"Net loss ${_q(realized)} -- tax drag set to zero "
                "(loss may offset other realized gains; not modeled here)"
            )

        return TaxAwareExitResult(
            symbol=sym,
            shares_exited=filled,
            gross_proceeds=_q(gross_proceeds),
            cost_basis=_q(cost_basis),
            realized_gain_loss=_q(realized),
            short_term_gain_loss=_q(st_gain),
            long_term_gain_loss=_q(lt_gain),
            federal_tax=_q(federal_tax),
            state_tax=_q(state_tax),
            niit_tax=_q(niit_tax),
            total_tax=_q(total_tax),
            after_tax_proceeds=_q(after_tax),
            tax_advantaged=False,
            days_to_long_term=min_days_to_lt,
            breakeven_price_for_long_term_wait=(
                _q(breakeven_price) if breakeven_price is not None else None
            ),
            reasons=reasons,
        )

    def _empty(
        self, symbol: str, tax_advantaged: bool, reasons: List[str]
    ) -> TaxAwareExitResult:
        zero = Decimal("0.00")
        return TaxAwareExitResult(
            symbol=symbol,
            shares_exited=Decimal("0"),
            gross_proceeds=zero,
            cost_basis=zero,
            realized_gain_loss=zero,
            short_term_gain_loss=zero,
            long_term_gain_loss=zero,
            federal_tax=zero,
            state_tax=zero,
            niit_tax=zero,
            total_tax=zero,
            after_tax_proceeds=zero,
            tax_advantaged=tax_advantaged,
            days_to_long_term=None,
            breakeven_price_for_long_term_wait=None,
            reasons=reasons,
        )


def days_to_long_term(acquired_on: date, as_of: Optional[date] = None) -> int:
    """Calendar days until ``(as_of - acquired_on).days > 365``; 0 if already
    long-term. Aligns with ``TaxLot.is_long_term`` (holding period over 365
    days, IRS Publication 550)."""
    ref = as_of or date.today()
    held = (ref - acquired_on).days
    if _is_long_term_held(held):
        return 0
    return 366 - held


def long_term_cutoff_date(acquired_on: date) -> date:
    """Date on which a lot first becomes long-term-eligible (first ``as_of``
    with ``(as_of - acquired_on).days > 365`` in the day-counting model)."""
    return acquired_on + timedelta(days=_LONG_TERM_MIN_CALENDAR_SPAN)


__all__ = [
    "DEFAULT_FEDERAL_LT_RATE",
    "DEFAULT_FEDERAL_ST_RATE",
    "DEFAULT_NIIT_APPLIES",
    "DEFAULT_NIIT_RATE",
    "DEFAULT_STATE_RATE",
    "ExitLot",
    "TaxAwareExitCalculator",
    "TaxAwareExitResult",
    "TaxProfile",
    "days_to_long_term",
    "long_term_cutoff_date",
]
