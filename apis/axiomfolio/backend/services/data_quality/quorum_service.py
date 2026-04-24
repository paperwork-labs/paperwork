"""
Quorum Service
==============

Cross-provider agreement check for a single (symbol, field) pair.

Given ``{provider_name: value_or_none}`` from N providers we ask:

* Do at least ``ceil(threshold * R)`` of the ``R`` responding
  providers agree within tolerance, where "agree" means
  ``|x - median| <= tolerance_pct * |median|``?

If yes -> ``QuorumResult(status=QUORUM_REACHED, quorum_value=median)``.
If no  -> ``QuorumResult(status=DISAGREEMENT, quorum_value=None)``.

We never silently pick "the first non-null" or "the most recent" -- a
disagreement above tolerance means we don't actually know the right
value, and the system MUST surface that (R32, R34, R38).

Inputs are ``Optional[Decimal]``. Floats are rejected loudly: comparing
``0.1 + 0.2`` to ``0.3`` would invent disagreements that don't exist
in the underlying data. ``str`` and ``int`` are coerced via
``Decimal(...)``; anything else raises ``TypeError``.

medallion: silver
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from backend.models.provider_quorum import (
    DEFAULT_QUORUM_THRESHOLD,
    ProviderQuorumLog,
    QuorumAction,
    QuorumStatus,
)

from .tolerances import EXACT_TOLERANCE, tolerance_for_field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuorumResult:
    """Immutable summary of one quorum check.

    ``providers_queried`` retains every provider we asked, even ones
    that returned ``None``. That's what gets persisted to
    ``ProviderQuorumLog.providers_queried`` so the admin dashboard can
    show "FMP failed; we still had quorum from yfinance + finnhub".
    """

    symbol: str
    field_name: str
    providers_queried: Dict[str, Optional[Decimal]]
    status: QuorumStatus
    action: QuorumAction
    quorum_value: Optional[Decimal] = None
    quorum_threshold: Decimal = DEFAULT_QUORUM_THRESHOLD
    max_disagreement_pct: Optional[Decimal] = None
    agreeing_providers: Tuple[str, ...] = field(default_factory=tuple)
    disagreeing_providers: Tuple[str, ...] = field(default_factory=tuple)

    def has_quorum(self) -> bool:
        return self.status == QuorumStatus.QUORUM_REACHED

    def to_log_dict(self) -> Dict[str, Optional[str]]:
        """JSONB shape for ``ProviderQuorumLog.providers_queried``."""
        return {
            name: (str(value) if value is not None else None)
            for name, value in self.providers_queried.items()
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class QuorumService:
    """Stateless quorum evaluator. Safe to instantiate per-request."""

    def __init__(self, default_threshold: Decimal = DEFAULT_QUORUM_THRESHOLD):
        if not (Decimal("0") < default_threshold <= Decimal("1")):
            raise ValueError(
                f"default_threshold must be in (0, 1], got {default_threshold}"
            )
        self.default_threshold = default_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self,
        symbol: str,
        field_name: str,
        provider_values: Dict[str, Optional[Decimal]],
        threshold: Optional[Decimal] = None,
        tolerance_pct: Optional[Decimal] = None,
    ) -> QuorumResult:
        """Evaluate one quorum check.

        ``provider_values`` keys MUST be provider names (e.g.,
        ``"fmp"``, ``"yfinance"``). Values are ``Decimal`` or ``None``
        (provider unreachable / didn't return a value).
        """
        if not provider_values:
            raise ValueError(
                "provider_values must contain at least one provider entry"
            )

        if threshold is None:
            threshold = self.default_threshold
        if not (Decimal("0") < threshold <= Decimal("1")):
            raise ValueError(f"threshold must be in (0, 1], got {threshold}")

        if tolerance_pct is None:
            tolerance_pct = tolerance_for_field(field_name)

        # Coerce + validate every input. We do NOT silently drop a
        # bad-typed value -- raise so the caller learns about it.
        normalized: Dict[str, Optional[Decimal]] = {
            provider: self._coerce_decimal(value)
            for provider, value in provider_values.items()
        }

        responding: List[Tuple[str, Decimal]] = [
            (provider, value)
            for provider, value in normalized.items()
            if value is not None
        ]

        # Single-source / no-source short-circuits.
        if len(provider_values) == 1:
            provider, value = next(iter(normalized.items()))
            return QuorumResult(
                symbol=symbol,
                field_name=field_name,
                providers_queried=normalized,
                status=QuorumStatus.SINGLE_SOURCE,
                action=QuorumAction.FLAGGED_FOR_REVIEW,
                quorum_value=value,
                quorum_threshold=threshold,
                max_disagreement_pct=None,
                agreeing_providers=(provider,) if value is not None else (),
                disagreeing_providers=(),
            )

        if len(responding) < 2:
            return QuorumResult(
                symbol=symbol,
                field_name=field_name,
                providers_queried=normalized,
                status=QuorumStatus.INSUFFICIENT_PROVIDERS,
                action=QuorumAction.FLAGGED_FOR_REVIEW,
                quorum_value=None,
                quorum_threshold=threshold,
                max_disagreement_pct=None,
                agreeing_providers=tuple(p for p, _ in responding),
                disagreeing_providers=(),
            )

        if tolerance_pct == EXACT_TOLERANCE:
            return self._validate_exact(
                symbol=symbol,
                field_name=field_name,
                normalized=normalized,
                responding=responding,
                threshold=threshold,
            )

        return self._validate_numeric(
            symbol=symbol,
            field_name=field_name,
            normalized=normalized,
            responding=responding,
            threshold=threshold,
            tolerance_pct=tolerance_pct,
        )

    def persist(
        self,
        db: Session,
        result: QuorumResult,
        check_at=None,
    ) -> Optional[ProviderQuorumLog]:
        """Write a ``QuorumResult`` to ``provider_quorum_log``.

        Caller controls the transaction (commit/rollback) -- per the
        Staff Engineer convention, services don't manage sessions.
        Returns the created row, or ``None`` if a duplicate
        ``(symbol, field_name, check_at)`` already exists (idempotent
        re-runs are not an error).
        """
        from sqlalchemy.exc import IntegrityError

        row = ProviderQuorumLog(
            symbol=result.symbol,
            field_name=result.field_name,
            providers_queried=result.to_log_dict(),
            quorum_value=result.quorum_value,
            quorum_threshold=result.quorum_threshold,
            status=result.status,
            max_disagreement_pct=result.max_disagreement_pct,
            action_taken=result.action,
        )
        if check_at is not None:
            row.check_at = check_at
        db.add(row)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            logger.info(
                "quorum log duplicate suppressed for %s/%s at %s: %s",
                result.symbol,
                result.field_name,
                check_at,
                exc,
            )
            return None
        return row

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_decimal(value) -> Optional[Decimal]:
        """Accept ``None``, ``Decimal``, ``int``, or numeric ``str``.

        Float is rejected: silently coercing ``0.1 + 0.2`` would
        invent quorum failures. The caller should pass
        ``Decimal(str(my_float))`` explicitly if it really wants that.
        """
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, bool):
            # bool is a subclass of int; refuse it explicitly.
            raise TypeError(
                f"QuorumService received bool value, expected Decimal: {value!r}"
            )
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, str):
            try:
                return Decimal(value)
            except (InvalidOperation, ValueError) as exc:
                raise TypeError(
                    f"QuorumService could not parse string {value!r} as Decimal"
                ) from exc
        if isinstance(value, float):
            raise TypeError(
                "QuorumService refuses float input (use Decimal); "
                f"got {value!r}. See no-silent-fallback rule."
            )
        raise TypeError(
            f"QuorumService got unsupported value type {type(value).__name__}: {value!r}"
        )

    def _validate_exact(
        self,
        *,
        symbol: str,
        field_name: str,
        normalized: Dict[str, Optional[Decimal]],
        responding: List[Tuple[str, Decimal]],
        threshold: Decimal,
    ) -> QuorumResult:
        """Exact-match quorum (ticker / sector / industry).

        Buckets responses by exact value, picks the largest bucket,
        and checks if its size meets the threshold.
        """
        buckets: Dict[Decimal, List[str]] = {}
        for provider, value in responding:
            buckets.setdefault(value, []).append(provider)

        winner_value, winner_providers = max(
            buckets.items(), key=lambda kv: len(kv[1])
        )
        agreement_ratio = Decimal(len(winner_providers)) / Decimal(len(responding))

        if agreement_ratio >= threshold:
            disagreeing = tuple(
                provider
                for provider, value in responding
                if value != winner_value
            )
            return QuorumResult(
                symbol=symbol,
                field_name=field_name,
                providers_queried=normalized,
                status=QuorumStatus.QUORUM_REACHED,
                action=(
                    QuorumAction.ACCEPTED
                    if not disagreeing
                    else QuorumAction.FLAGGED_FOR_REVIEW
                ),
                quorum_value=winner_value,
                quorum_threshold=threshold,
                max_disagreement_pct=None,
                agreeing_providers=tuple(winner_providers),
                disagreeing_providers=disagreeing,
            )

        logger.warning(
            "quorum DISAGREEMENT (exact) symbol=%s field=%s buckets=%s",
            symbol,
            field_name,
            {str(k): v for k, v in buckets.items()},
        )
        return QuorumResult(
            symbol=symbol,
            field_name=field_name,
            providers_queried=normalized,
            status=QuorumStatus.DISAGREEMENT,
            action=QuorumAction.REJECTED,
            quorum_value=None,
            quorum_threshold=threshold,
            max_disagreement_pct=None,
            agreeing_providers=tuple(winner_providers),
            disagreeing_providers=tuple(
                provider for provider, value in responding if value != winner_value
            ),
        )

    def _validate_numeric(
        self,
        *,
        symbol: str,
        field_name: str,
        normalized: Dict[str, Optional[Decimal]],
        responding: List[Tuple[str, Decimal]],
        threshold: Decimal,
        tolerance_pct: Decimal,
    ) -> QuorumResult:
        """Numeric quorum: agree if within ``tolerance_pct`` of median."""
        values = [value for _, value in responding]
        median = _median(values)

        # Pairwise spread: largest |x - y| / |median| across all pairs.
        # This matches "max disagreement" the operator dashboard cares
        # about, and is identical to ``(max(values) - min(values)) /
        # |median|`` for a set of N >= 2 values.
        spread = max(values) - min(values)
        if median == 0:
            # Median == 0 is degenerate (e.g., volume genuinely zero).
            # Fall back to "any non-zero value disagrees with the
            # median". Agreement check below uses absolute distance
            # rather than %.
            max_disagreement_pct = None
        else:
            max_disagreement_pct = (spread / abs(median)).copy_abs()

        agreeing: List[str] = []
        disagreeing: List[str] = []
        for provider, value in responding:
            if median == 0:
                if value == 0:
                    agreeing.append(provider)
                else:
                    disagreeing.append(provider)
            else:
                deviation = ((value - median) / median).copy_abs()
                if deviation <= tolerance_pct:
                    agreeing.append(provider)
                else:
                    disagreeing.append(provider)

        agreement_ratio = Decimal(len(agreeing)) / Decimal(len(responding))

        if agreement_ratio >= threshold:
            # Quorum value = median of the agreeing subset, so a fringe
            # outlier that just barely passed tolerance doesn't drag the
            # answer.
            agreeing_values = [
                value for provider, value in responding if provider in agreeing
            ]
            quorum_value = _median(agreeing_values)
            return QuorumResult(
                symbol=symbol,
                field_name=field_name,
                providers_queried=normalized,
                status=QuorumStatus.QUORUM_REACHED,
                action=(
                    QuorumAction.ACCEPTED
                    if not disagreeing
                    else QuorumAction.FLAGGED_FOR_REVIEW
                ),
                quorum_value=quorum_value,
                quorum_threshold=threshold,
                max_disagreement_pct=max_disagreement_pct,
                agreeing_providers=tuple(agreeing),
                disagreeing_providers=tuple(disagreeing),
            )

        logger.warning(
            "quorum DISAGREEMENT (numeric) symbol=%s field=%s "
            "median=%s spread=%s tolerance=%s agreement_ratio=%s",
            symbol,
            field_name,
            median,
            spread,
            tolerance_pct,
            agreement_ratio,
        )
        return QuorumResult(
            symbol=symbol,
            field_name=field_name,
            providers_queried=normalized,
            status=QuorumStatus.DISAGREEMENT,
            action=QuorumAction.REJECTED,
            quorum_value=None,
            quorum_threshold=threshold,
            max_disagreement_pct=max_disagreement_pct,
            agreeing_providers=tuple(agreeing),
            disagreeing_providers=tuple(disagreeing),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _median(values: Sequence[Decimal]) -> Decimal:
    """Decimal-preserving median (no float coercion)."""
    if not values:
        raise ValueError("_median requires at least one value")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal(2)
