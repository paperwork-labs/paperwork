"""Apply pending corporate actions to user holdings.

Iron laws this module enforces (per ``.cursor/rules/no-silent-fallback``,
``engineering.mdc``, and the user's brief for this PR):

1. **Reversibility.** Every mutation to ``positions`` / ``tax_lots``
   has an ``applied_corporate_actions`` row that snapshots the
   *original* qty / cost basis. :meth:`reverse_action` restores the
   exact pre-application state purely from those snapshots, no audit
   log, no replay needed.

2. **Multi-tenant isolation.** The applier groups positions and lots
   by ``user_id`` and runs each user's adjustment inside its own
   ``session.begin_nested()`` savepoint. If user A's adjustment hits a
   constraint violation, the savepoint rolls back A's mutations only;
   user B's adjustments stay committed.

3. **No silent fallbacks.** Per-user failures are logged AND counted
   AND surfaced on the parent ``CorporateAction.status`` (PARTIAL or
   FAILED) along with ``error_message``. There is no ``except: pass``
   anywhere in the loop. A mid-run exception (e.g. DB outage) bubbles
   to the caller after the parent action's status is updated.

4. **Idempotency.** ``AppliedCorporateAction`` has a unique constraint
   on ``(action, user, position, lot)``; the applier short-circuits any
   action whose status is no longer ``PENDING``. Re-running the daily
   task therefore never double-applies.

5. **Decimal end-to-end.** The math layer (``adjusters.py``) is
   ``Decimal``-only. Conversion to ``Float`` happens *only* at the
   ``TaxLot`` boundary (the legacy ``Float`` schema we're not changing
   in this PR; see commit message).

medallion: silver
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Position, TaxLot
from app.models.corporate_action import (
    AppliedCorporateAction,
    CorporateAction,
    CorporateActionStatus,
    CorporateActionType,
)
from app.models.position import PositionStatus

from .adjusters import (
    AdjustmentResult,
    adjust_for_cash_dividend,
    adjust_for_merger_cash,
    adjust_for_merger_stock,
    adjust_for_reverse_split,
    adjust_for_split,
    adjust_for_stock_dividend,
)
from .historical_ohlcv_adjuster import HistoricalOhlcvAdjuster

logger = logging.getLogger(__name__)


_PASSTHROUGH_TYPES = frozenset(
    {
        # Name / symbol changes have no qty / cost impact in v1; we
        # mark them APPLIED without writing per-user rows. (The
        # downstream sync that picks up the new ticker symbol is out of
        # scope for this PR.)
        CorporateActionType.NAME_CHANGE.value,
        CorporateActionType.SYMBOL_CHANGE.value,
        # Spinoffs require a basis allocation between parent + child
        # which is provider-policy-dependent; deferred to a follow-up.
        CorporateActionType.SPINOFF.value,
    }
)


def _ohlcv_back_adjust_enabled() -> bool:
    """Read the ``FEATURE_BACK_ADJUST_OHLCV`` flag at call time.

    Read at call time (not import time) so operators can flip it
    without a worker restart -- the next ``apply_pending`` run picks
    up the new value. Default OFF in this PR; flip to ON only after
    spot-checking a couple of post-split symbols on staging.
    """
    raw = (os.getenv("FEATURE_BACK_ADJUST_OHLCV") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass
class _PerActionResult:
    """Internal: outcome of applying one CorporateAction across all users."""

    users_processed: int = 0
    users_applied: int = 0
    users_failed: int = 0
    positions_adjusted: int = 0
    tax_lots_adjusted: int = 0
    cash_credited_total: Decimal = Decimal("0")
    ohlcv_rows_adjusted: int = 0
    error_messages: list[str] = field(default_factory=list)


@dataclass
class ApplyReport:
    """Counters returned to the Celery task / admin route."""

    actions_total: int = 0
    actions_applied: int = 0
    actions_partial: int = 0
    actions_failed: int = 0
    actions_skipped: int = 0
    positions_adjusted: int = 0
    tax_lots_adjusted: int = 0
    ohlcv_rows_adjusted: int = 0


class _UnsupportedActionType(Exception):
    """Raised when an action's type isn't routed to a known adjuster."""


class CorporateActionApplier:
    def __init__(
        self,
        session: Session,
        *,
        ohlcv_adjuster: HistoricalOhlcvAdjuster | None = None,
    ) -> None:
        self.session = session
        # Lazily wire the OHLCV adjuster; tests can pass a custom one
        # (e.g. ``enabled=True`` regardless of env) for deterministic
        # back-adjust assertions.
        self._ohlcv_adjuster = ohlcv_adjuster or HistoricalOhlcvAdjuster(
            session,
            enabled=_ohlcv_back_adjust_enabled(),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_pending(self, *, today: date | None = None) -> ApplyReport:
        """Apply every PENDING action whose ex_date <= ``today``."""
        cutoff = today or datetime.utcnow().date()
        report = ApplyReport()

        actions = (
            self.session.execute(
                select(CorporateAction)
                .where(CorporateAction.status == CorporateActionStatus.PENDING.value)
                .where(CorporateAction.ex_date <= cutoff)
                .order_by(CorporateAction.ex_date.asc(), CorporateAction.id.asc())
            )
            .scalars()
            .all()
        )
        report.actions_total = len(actions)

        for action in actions:
            try:
                outcome = self._apply_one(action)
            except _UnsupportedActionType as exc:
                action.status = CorporateActionStatus.SKIPPED.value
                action.error_message = str(exc)
                report.actions_skipped += 1
                logger.info(
                    "corp-action %s SKIPPED (unsupported type %s)",
                    action.id,
                    action.action_type,
                )
                continue

            self._update_action_status(action, outcome)
            report.positions_adjusted += outcome.positions_adjusted
            report.tax_lots_adjusted += outcome.tax_lots_adjusted
            report.ohlcv_rows_adjusted += outcome.ohlcv_rows_adjusted

            status = action.status
            if status == CorporateActionStatus.APPLIED.value:
                report.actions_applied += 1
            elif status == CorporateActionStatus.PARTIAL.value:
                report.actions_partial += 1
            elif status == CorporateActionStatus.FAILED.value:
                report.actions_failed += 1
            elif status == CorporateActionStatus.SKIPPED.value:
                report.actions_skipped += 1

        # Belt-and-suspenders sanity assertion: counter drift would
        # mean we mis-tagged a status above. Cheap to check.
        bucket_sum = (
            report.actions_applied
            + report.actions_partial
            + report.actions_failed
            + report.actions_skipped
        )
        assert bucket_sum == report.actions_total, (
            f"counter drift: total={report.actions_total} sum={bucket_sum}"
        )

        logger.info(
            "corp-action apply_pending: total=%d applied=%d partial=%d "
            "failed=%d skipped=%d positions=%d lots=%d ohlcv_rows=%d",
            report.actions_total,
            report.actions_applied,
            report.actions_partial,
            report.actions_failed,
            report.actions_skipped,
            report.positions_adjusted,
            report.tax_lots_adjusted,
            report.ohlcv_rows_adjusted,
        )
        return report

    def reverse_action(self, action: CorporateAction) -> _PerActionResult:
        """Restore the pre-application state for ``action``.

        Iterates ``AppliedCorporateAction`` rows, restores the
        original_* snapshots onto the live position / tax_lot rows,
        deletes the audit rows, reverses the OHLCV back-adjustment
        (if any), and flips the action status to ``REVERSED``.

        Per-user savepoints again -- a constraint failure on user A
        shouldn't block restoring user B.
        """
        outcome = _PerActionResult()

        applications_by_user: dict[int, list[AppliedCorporateAction]] = defaultdict(list)
        for row in action.applications:
            applications_by_user[row.user_id].append(row)

        for user_id, rows in applications_by_user.items():
            outcome.users_processed += 1
            try:
                with self.session.begin_nested():
                    for row in rows:
                        self._restore_one(row)
                        self.session.delete(row)
                outcome.users_applied += 1
            except SQLAlchemyError as exc:
                outcome.users_failed += 1
                msg = f"user_id={user_id} reverse failed: {exc}"
                outcome.error_messages.append(msg)
                logger.warning("corp-action %s reverse: %s", action.id, msg)

        ohlcv_report = self._ohlcv_adjuster.reverse(action)
        outcome.ohlcv_rows_adjusted = ohlcv_report.rows_updated

        if outcome.users_failed == 0:
            action.status = CorporateActionStatus.REVERSED.value
            action.error_message = None
        else:
            # Partial reverse: leave status as-is (APPLIED / PARTIAL),
            # surface the failure on error_message so admin sees it.
            action.error_message = "; ".join(outcome.error_messages)

        return outcome

    # ------------------------------------------------------------------
    # Per-action plumbing
    # ------------------------------------------------------------------

    def _apply_one(self, action: CorporateAction) -> _PerActionResult:
        outcome = _PerActionResult()

        # Pass-through types (name / symbol change, spinoff) get a no-op
        # APPLIED so we don't keep re-evaluating them.
        if action.action_type in _PASSTHROUGH_TYPES:
            return outcome

        # Eagerly validate that we have an adjuster for this type
        # before pulling holdings.
        try:
            self._compute(action, Decimal("1"), Decimal("0"))
        except _UnsupportedActionType:
            raise
        except Exception:
            # Non-routing errors at this validation step are fine; the
            # real call below uses real values and will surface them.
            pass

        symbol = action.symbol.upper()

        # Pull every open position + tax-lot of the symbol. We use the
        # status='OPEN' filter for positions so cash mergers don't
        # re-close already-closed positions (idempotency vs prior runs).
        positions: list[Position] = (
            self.session.execute(
                select(Position)
                .where(Position.symbol == symbol)
                .where(Position.status == PositionStatus.OPEN)
            )
            .scalars()
            .all()
        )
        # Tax lots: include all (no status enum on TaxLot); the applier
        # short-circuits qty == 0 lots inside _apply_for_user.
        tax_lots: list[TaxLot] = (
            self.session.execute(select(TaxLot).where(TaxLot.symbol == symbol)).scalars().all()
        )

        if not positions and not tax_lots:
            # No holders -> SKIPPED. Recording the result in a
            # _PerActionResult lets _update_action_status mark it.
            return outcome

        positions_by_user: dict[int, list[Position]] = defaultdict(list)
        for pos in positions:
            positions_by_user[pos.user_id].append(pos)
        lots_by_user: dict[int, list[TaxLot]] = defaultdict(list)
        for lot in tax_lots:
            if lot.user_id is None:
                # Defensive: TaxLot.user_id is nullable in the model;
                # the @before_insert hook backfills from broker_account,
                # but ancient rows might lack it. Skip and log -- can't
                # adjust a lot we can't attribute.
                logger.warning(
                    "corp-action %s: skipping orphan tax_lot %s (no user_id)",
                    action.id,
                    lot.id,
                )
                continue
            lots_by_user[lot.user_id].append(lot)

        all_user_ids = set(positions_by_user) | set(lots_by_user)
        for user_id in sorted(all_user_ids):
            outcome.users_processed += 1
            user_positions = positions_by_user.get(user_id, [])
            user_lots = lots_by_user.get(user_id, [])
            try:
                with self.session.begin_nested():
                    per_user = self._apply_for_user(action, user_id, user_positions, user_lots)
                outcome.users_applied += 1
                outcome.positions_adjusted += per_user["positions_adjusted"]
                outcome.tax_lots_adjusted += per_user["tax_lots_adjusted"]
                outcome.cash_credited_total += per_user["cash_credited"]
            except _UnsupportedActionType:
                # Bubble: the parent loop turns this into SKIPPED.
                raise
            except Exception as exc:
                outcome.users_failed += 1
                msg = f"user_id={user_id}: {exc}"
                outcome.error_messages.append(msg)
                logger.warning(
                    "corp-action %s apply failed for user %s: %s",
                    action.id,
                    user_id,
                    exc,
                )

        # OHLCV back-adjustment runs ONCE per action (it's a global
        # symbol-level operation, not per-user). It runs even if
        # individual users failed, because the bars are independent of
        # holdings.
        ohlcv_report = self._ohlcv_adjuster.adjust(action)
        outcome.ohlcv_rows_adjusted = ohlcv_report.rows_updated

        return outcome

    def _apply_for_user(
        self,
        action: CorporateAction,
        user_id: int,
        positions: Iterable[Position],
        tax_lots: Iterable[TaxLot],
    ) -> dict[str, Any]:
        positions_adjusted = 0
        tax_lots_adjusted = 0
        cash_credited = Decimal("0")

        for pos in positions:
            current_qty = _to_decimal(pos.quantity)
            current_basis = _to_decimal(pos.total_cost_basis)
            result = self._compute(action, current_qty, current_basis)

            applied = AppliedCorporateAction(
                corporate_action_id=action.id,
                user_id=user_id,
                position_id=pos.id,
                tax_lot_id=None,
                symbol=pos.symbol,
                original_qty=current_qty,
                original_cost_basis=current_basis,
                original_avg_cost=_to_decimal(pos.average_cost),
                adjusted_qty=result.new_qty,
                adjusted_cost_basis=result.new_cost_basis,
                adjusted_avg_cost=result.new_avg_cost,
                cash_credited=result.cash_credited,
            )
            self.session.add(applied)

            pos.quantity = result.new_qty
            pos.total_cost_basis = result.new_cost_basis
            pos.average_cost = result.new_avg_cost
            if result.new_symbol:
                pos.symbol = result.new_symbol
            if result.new_qty == 0:
                pos.status = PositionStatus.CLOSED
            cash_credited += result.cash_credited
            positions_adjusted += 1

        for lot in tax_lots:
            current_qty = _to_decimal(lot.quantity)
            if current_qty == 0:
                # Skip empty lots silently -- they're an artifact of
                # prior closeouts and would just produce no-op rows.
                continue
            current_basis = _to_decimal(lot.cost_basis or 0)
            result = self._compute(action, current_qty, current_basis)

            applied = AppliedCorporateAction(
                corporate_action_id=action.id,
                user_id=user_id,
                position_id=None,
                tax_lot_id=lot.id,
                symbol=lot.symbol,
                original_qty=current_qty,
                original_cost_basis=current_basis,
                original_avg_cost=_to_decimal(lot.cost_per_share or 0),
                adjusted_qty=result.new_qty,
                adjusted_cost_basis=result.new_cost_basis,
                adjusted_avg_cost=result.new_avg_cost,
                cash_credited=result.cash_credited,
            )
            self.session.add(applied)

            # Float boundary: TaxLot uses Float columns. Convert at
            # write time only; the math layer stays Decimal.
            lot.quantity = float(result.new_qty)
            lot.cost_basis = float(result.new_cost_basis)
            lot.cost_per_share = float(result.new_avg_cost)
            if result.new_symbol:
                lot.symbol = result.new_symbol
            cash_credited += result.cash_credited
            tax_lots_adjusted += 1

        return {
            "positions_adjusted": positions_adjusted,
            "tax_lots_adjusted": tax_lots_adjusted,
            "cash_credited": cash_credited,
        }

    def _restore_one(self, row: AppliedCorporateAction) -> None:
        if row.position_id is not None:
            pos = self.session.get(Position, row.position_id)
            if pos is not None:
                pos.quantity = row.original_qty
                pos.total_cost_basis = row.original_cost_basis
                if row.original_avg_cost is not None:
                    pos.average_cost = row.original_avg_cost
                # If we closed it on apply, re-open it.
                if (
                    pos.status == PositionStatus.CLOSED
                    and row.original_qty
                    and row.original_qty > 0
                ):
                    pos.status = PositionStatus.OPEN
                # If we renamed it (stock merger), restore the symbol.
                if row.symbol and row.symbol != pos.symbol:
                    pos.symbol = row.symbol
        if row.tax_lot_id is not None:
            lot = self.session.get(TaxLot, row.tax_lot_id)
            if lot is not None:
                lot.quantity = float(row.original_qty)
                lot.cost_basis = float(row.original_cost_basis)
                if row.original_avg_cost is not None:
                    lot.cost_per_share = float(row.original_avg_cost)
                if row.symbol and row.symbol != lot.symbol:
                    lot.symbol = row.symbol

    # ------------------------------------------------------------------
    # Status routing + adjuster dispatch
    # ------------------------------------------------------------------

    def _update_action_status(
        self,
        action: CorporateAction,
        outcome: _PerActionResult,
    ) -> None:
        action.applied_at = datetime.utcnow()
        if outcome.users_processed == 0:
            action.status = CorporateActionStatus.SKIPPED.value
            action.error_message = "no holders at ex_date"
            return
        if outcome.users_failed == 0:
            action.status = CorporateActionStatus.APPLIED.value
            action.error_message = None
            return
        if outcome.users_applied == 0:
            action.status = CorporateActionStatus.FAILED.value
        else:
            action.status = CorporateActionStatus.PARTIAL.value
        action.error_message = "; ".join(outcome.error_messages)[:8000]

    def _compute(
        self,
        action: CorporateAction,
        current_qty: Decimal,
        current_cost_basis: Decimal,
    ) -> AdjustmentResult:
        """Dispatch to the right pure adjuster based on ``action.action_type``."""
        atype = action.action_type
        num = action.ratio_numerator
        den = action.ratio_denominator
        cash = action.cash_amount

        if atype == CorporateActionType.SPLIT.value:
            self._require(num is not None and den is not None, action, "split needs ratio")
            return adjust_for_split(current_qty, current_cost_basis, num, den)

        if atype == CorporateActionType.REVERSE_SPLIT.value:
            self._require(num is not None and den is not None, action, "reverse_split needs ratio")
            return adjust_for_reverse_split(current_qty, current_cost_basis, num, den)

        if atype == CorporateActionType.STOCK_DIVIDEND.value:
            self._require(num is not None and den is not None, action, "stock_dividend needs ratio")
            return adjust_for_stock_dividend(current_qty, current_cost_basis, num, den)

        if atype in (
            CorporateActionType.CASH_DIVIDEND.value,
            CorporateActionType.SPECIAL_CASH_DIVIDEND.value,
        ):
            self._require(cash is not None, action, "cash_dividend needs cash_amount")
            return adjust_for_cash_dividend(current_qty, current_cost_basis, cash)

        if atype == CorporateActionType.MERGER_STOCK.value:
            self._require(
                num is not None and den is not None and action.target_symbol,
                action,
                "merger_stock needs ratio + target_symbol",
            )
            return adjust_for_merger_stock(
                current_qty,
                current_cost_basis,
                action.target_symbol or "",
                num,
                den,
            )

        if atype == CorporateActionType.MERGER_CASH.value:
            self._require(cash is not None, action, "merger_cash needs cash_amount")
            return adjust_for_merger_cash(current_qty, current_cost_basis, cash)

        raise _UnsupportedActionType(f"no adjuster for action_type={atype!r}")

    @staticmethod
    def _require(condition: bool, action: CorporateAction, msg: str) -> None:
        if not condition:
            raise ValueError(f"action_id={action.id} {action.action_type}: {msg}")


def _to_decimal(value: Any) -> Decimal:
    """Coerce DB-loaded numerics (Decimal | float | None) to Decimal."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)
