"""Back-adjust historical OHLCV after a split or stock dividend.

For a forward split with multiplier ``M`` (e.g. 3-for-1, M=3), every
``price_data`` row strictly **before** the ex-date must have its prices
divided by ``M`` and its volume multiplied by ``M``. This keeps charts
visually continuous and -- crucially -- keeps every indicator that
ingests historical bars (RSI, ATR, MACD, ADX, Stage classifier) honest.

Without back-adjustment, a 3-for-1 split looks like a -67% gap on the
chart and detonates ATR, ADX, and the SMA200 crossover that anchors the
Weinstein stage classification.

This adjuster is gated by ``FEATURE_BACK_ADJUST_OHLCV`` so the
operator can disable it independently of the position-level applier --
useful when investigating chart anomalies or migrating to a
provider-supplied adjusted-close column.

Reverse semantics: :meth:`reverse` undoes the math (multiplies prices,
divides volume) so an admin who applied a bad split can fully restore
the original bars.

Out of scope (deliberately): cash dividends. Adjusting OHLCV for cash
dividends is provider-policy-dependent and would require a separate
toggle. The position-level applier handles cash dividends without
touching ``price_data``.

medallion: silver
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import PriceData
from app.models.corporate_action import (
    CorporateAction,
    CorporateActionType,
)

from .adjusters import decimal_ratio

logger = logging.getLogger(__name__)


# Action types that warrant historical price adjustment. Reverse splits
# share the same math (multiplier < 1 is fine).
_OHLCV_ADJUSTABLE_TYPES = frozenset(
    {
        CorporateActionType.SPLIT.value,
        CorporateActionType.REVERSE_SPLIT.value,
        CorporateActionType.STOCK_DIVIDEND.value,
    }
)


@dataclass
class OhlcvAdjustReport:
    """Per-action result of a back-adjust pass."""

    symbol: str
    ex_date: date
    multiplier: Decimal
    rows_updated: int
    skipped_reason: Optional[str] = None  # set when adjustment was a no-op


class HistoricalOhlcvAdjuster:
    """Back-adjust ``price_data`` rows for split-style corporate actions.

    The adjuster is **session-bound** but does not commit; callers
    (typically :class:`CorporateActionApplier`) own the transaction
    boundary so the OHLCV mutation is atomic with the
    ``CorporateAction.ohlcv_adjusted`` flag flip.
    """

    def __init__(self, session: Session, *, enabled: bool = True) -> None:
        self.session = session
        self.enabled = enabled

    def adjust(self, action: CorporateAction) -> OhlcvAdjustReport:
        """Apply the back-adjustment for ``action``.

        Idempotent: ``CorporateAction.ohlcv_adjusted`` short-circuits
        re-runs. Returns an :class:`OhlcvAdjustReport` describing the
        outcome (rows updated or skip reason).
        """
        symbol = action.symbol
        ex_date = action.ex_date
        multiplier = self._multiplier(action)

        if multiplier is None:
            return OhlcvAdjustReport(
                symbol=symbol,
                ex_date=ex_date,
                multiplier=Decimal("1"),
                rows_updated=0,
                skipped_reason="not_split_like",
            )
        if not self.enabled:
            return OhlcvAdjustReport(
                symbol=symbol,
                ex_date=ex_date,
                multiplier=multiplier,
                rows_updated=0,
                skipped_reason="feature_disabled",
            )
        if action.ohlcv_adjusted:
            return OhlcvAdjustReport(
                symbol=symbol,
                ex_date=ex_date,
                multiplier=multiplier,
                rows_updated=0,
                skipped_reason="already_adjusted",
            )

        rows = self._apply_multiplier(symbol, ex_date, multiplier)
        action.ohlcv_adjusted = True
        logger.info(
            "ohlcv back-adjust: symbol=%s ex_date=%s mult=%s rows=%d",
            symbol,
            ex_date,
            multiplier,
            rows,
        )
        return OhlcvAdjustReport(
            symbol=symbol,
            ex_date=ex_date,
            multiplier=multiplier,
            rows_updated=rows,
        )

    def reverse(self, action: CorporateAction) -> OhlcvAdjustReport:
        """Undo a previously-applied back-adjustment.

        Inverts the multiplier (1/M) and divides volume by M. Flips
        ``CorporateAction.ohlcv_adjusted`` back to False.
        """
        symbol = action.symbol
        ex_date = action.ex_date
        multiplier = self._multiplier(action)

        if multiplier is None:
            return OhlcvAdjustReport(
                symbol=symbol,
                ex_date=ex_date,
                multiplier=Decimal("1"),
                rows_updated=0,
                skipped_reason="not_split_like",
            )
        if not action.ohlcv_adjusted:
            return OhlcvAdjustReport(
                symbol=symbol,
                ex_date=ex_date,
                multiplier=multiplier,
                rows_updated=0,
                skipped_reason="not_adjusted",
            )

        inverse = Decimal("1") / multiplier
        rows = self._apply_multiplier(symbol, ex_date, inverse)
        action.ohlcv_adjusted = False
        logger.info(
            "ohlcv back-adjust REVERSE: symbol=%s ex_date=%s mult=%s rows=%d",
            symbol,
            ex_date,
            inverse,
            rows,
        )
        return OhlcvAdjustReport(
            symbol=symbol,
            ex_date=ex_date,
            multiplier=inverse,
            rows_updated=rows,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _multiplier(action: CorporateAction) -> Optional[Decimal]:
        if action.action_type not in _OHLCV_ADJUSTABLE_TYPES:
            return None
        if action.ratio_numerator is None or action.ratio_denominator is None:
            return None
        try:
            return decimal_ratio(action.ratio_numerator, action.ratio_denominator)
        except (ValueError, ArithmeticError):
            return None

    def _apply_multiplier(
        self,
        symbol: str,
        ex_date: date,
        multiplier: Decimal,
    ) -> int:
        """Divide pre-ex-date prices by ``multiplier``, multiply volume by it.

        Returns the number of ``price_data`` rows touched.
        """
        # PriceData.date is a DateTime; the ex-date cutoff must include
        # the entire calendar day BEFORE ex_date. Using `< midnight of
        # ex_date` is the correct half-open interval.
        cutoff = _ex_date_to_datetime(ex_date)

        # Float multiplier: PriceData.* are SQLAlchemy Float columns. We
        # accept the boundary float conversion here because the
        # alternative -- converting the entire OHLCV history to Numeric
        # -- would be a multi-day, multi-table migration. A 3.0 multiplier
        # round-trips exactly; provider-supplied non-integer ratios
        # (e.g. 1.05 stock dividend) lose at most ~1 ULP per row, which
        # is invisible at chart precision.
        mult_float = float(multiplier)

        # Standard split-adjustment math (e.g. for a 3-for-1 forward
        # split with multiplier=3): pre-ex-date prices are divided by 3
        # AND pre-ex-date volume is multiplied by 3 -- because each
        # historical share is now equivalent to three post-split shares,
        # so the trading activity expressed in post-split share units is
        # 3x the original count. Yahoo / Polygon / FMP all use this
        # convention.
        stmt = (
            update(PriceData)
            .where(PriceData.symbol == symbol)
            .where(PriceData.date < cutoff)
            .values(
                open_price=PriceData.open_price / mult_float,
                high_price=PriceData.high_price / mult_float,
                low_price=PriceData.low_price / mult_float,
                close_price=PriceData.close_price / mult_float,
                adjusted_close=PriceData.adjusted_close / mult_float,
                volume=(PriceData.volume * mult_float),
            )
            .execution_options(synchronize_session=False)
        )
        result = self.session.execute(stmt)
        # Row count semantics depend on dialect; SQLAlchemy normalizes
        # `result.rowcount` for UPDATEs across PG / SQLite.
        return int(result.rowcount or 0)


def _ex_date_to_datetime(ex_date: date) -> datetime:
    """Midnight of ex_date -- the half-open cutoff for back-adjustment.

    Bars dated strictly before this value are pre-ex-date and must be
    adjusted. The ex-date bar itself is the *new* basis and must NOT be
    touched.
    """
    return datetime.combine(ex_date, time.min)
