"""Trade card composition: turn a scored candidate into an executable plan.

A :class:`TradeCard` is the one-screen artifact a user needs to place a trade:
underlying context, contract pick, three limit tiers, position size for the
user's actual account, stops, and alerts. Cards are composed on read (not
persisted) so every field traces back to the current snapshot + regime + chain
data; there is no stale card to expire.

The composer is intentionally additive: if any input is missing (chain data,
sizing inputs, user account balance) the corresponding section of the card is
returned with an explicit ``*_status`` value so the UI can render a
distinguishable loading/empty/degraded state rather than a silent zero.

Monetary math uses :class:`decimal.Decimal`; the one exception is the call into
:func:`backend.services.execution.risk_gate.compute_position_size`, which takes
floats by historical contract. Inputs and outputs are explicitly converted at
the boundary.

medallion: gold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.broker_account import AccountStatus, BrokerAccount
from backend.models.market_data import MarketRegime, MarketSnapshot
from backend.models.picks import Candidate, PickAction
from backend.models.user import User
# medallion: allow cross-layer import (gold -> execution); resolves when backend.services.execution.risk_gate moves during Phase 0.C
from backend.services.execution.risk_gate import (
    DEFAULT_STOP_MULTIPLIER,
    compute_position_size,
)
from backend.services.gold.pick_quality_scorer import (
    PickQualityScore,
    PickQualityScorer,
)
from backend.services.market.regime_engine import get_current_regime

logger = logging.getLogger(__name__)

# Sentinel: ``compose(..., account_value_override=ACCOUNT_VALUE_FETCH)`` (default)
# loads balances from the DB; pass ``None`` or a :class:`~decimal.Decimal` when
# the caller already prefetched (e.g. a route batching per-candidate cards).
ACCOUNT_VALUE_FETCH = object()


# ----------------------------------------------------------------------------
# Contract data protocol
# ----------------------------------------------------------------------------


class ContractType(str, Enum):
    """How the card expresses the directional thesis."""

    CALL_DEBIT = "call_debit"
    PUT_CREDIT = "put_credit"
    STOCK = "stock"


class ContractStatus(str, Enum):
    """Whether the card has a live contract attached and why/why not."""

    READY = "ready"
    CHAIN_UNAVAILABLE = "chain_unavailable"
    STOCK_ONLY = "stock_only"
    SKIPPED_EARNINGS = "skipped_earnings"


class SizingStatus(str, Enum):
    """Whether sizing was computable for this card."""

    COMPUTED = "computed"
    ACCOUNT_UNKNOWN = "account_unknown"
    INPUTS_MISSING = "inputs_missing"
    REGIME_BLOCKED = "regime_blocked"


class SizingTier(str, Enum):
    """Exit-management style derived from premium per trade."""

    T1_LOTTERY = "T1"
    T2_CONVICTION = "T2"
    T3_POSITION = "T3"


class LimitTier(str, Enum):
    PASSIVE = "passive"
    MID = "mid"
    AGGRESSIVE = "aggressive"


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ContractRecommendation:
    """A concrete contract pick (call/put) emitted by an options surface."""

    contract_type: ContractType
    occ_symbol: str
    expiry: date
    strike: Decimal
    bid: Decimal
    mid: Decimal
    ask: Decimal
    spread_pct: Decimal  # (ask-bid) / mid * 100
    delta: Optional[Decimal]
    open_interest: Optional[int]
    volume: Optional[int]


class OptionsChainSurface(Protocol):
    """Protocol for anything that can recommend a concrete contract.

    The real implementation lands with the options-chain PR; until then the
    composer accepts ``None`` and returns a card with
    ``contract_status=CHAIN_UNAVAILABLE`` so the UI can distinguish "we don't
    have data yet" from "we checked and the chain is untradeable".
    """

    def recommend_contract(
        self,
        db: Session,
        *,
        symbol: str,
        current_price: Decimal,
        earnings_date: Optional[datetime],
        bias: ContractType,
    ) -> Optional[ContractRecommendation]:  # pragma: no cover - protocol
        ...


# ----------------------------------------------------------------------------
# Card structure
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class UnderlyingView:
    symbol: str
    name: Optional[str]
    sector: Optional[str]
    stage_label: Optional[str]
    current_price: Optional[Decimal]
    rs_mansfield_pct: Optional[Decimal]
    perf_5d: Optional[Decimal]
    td_buy_setup: Optional[int]
    td_sell_setup: Optional[int]
    next_earnings: Optional[datetime]
    days_to_earnings: Optional[int]
    atr_14: Optional[Decimal]
    atrp_14: Optional[Decimal]
    sma_21: Optional[Decimal]
    volume_avg_20d: Optional[Decimal]


@dataclass(frozen=True)
class RegimeView:
    regime_state: str
    composite_score: Optional[Decimal]
    regime_multiplier: Decimal
    as_of_date: Optional[date]


@dataclass(frozen=True)
class ScoreView:
    pick_quality_score: Decimal
    components: Dict[str, Dict[str, str]]
    regime_multiplier: Decimal


@dataclass(frozen=True)
class ContractView:
    contract_type: ContractType
    occ_symbol: str
    expiry: date
    strike: Decimal
    bid: Decimal
    mid: Decimal
    ask: Decimal
    spread_pct: Decimal
    delta: Optional[Decimal]
    open_interest: Optional[int]
    volume: Optional[int]


@dataclass(frozen=True)
class LimitPriceTier:
    tier: LimitTier
    price: Decimal
    logic: str
    fill_likelihood: str  # "high", "moderate", "low" / "don't"


@dataclass(frozen=True)
class SizingView:
    tier: Optional[SizingTier]
    contracts: int
    shares: int
    premium_dollars: Decimal
    premium_pct_of_account: Decimal
    full_position_dollars: Decimal
    capped_position_dollars: Decimal
    stage_cap: Decimal
    regime_multiplier: Decimal
    account_size: Decimal
    risk_budget: Decimal


@dataclass(frozen=True)
class StopsView:
    premium_stop: Optional[Decimal]
    underlying_stop: Optional[Decimal]
    underlying_stop_reason: Optional[str]
    calendar_stop: Optional[date]
    calendar_stop_reason: Optional[str]


@dataclass(frozen=True)
class AlertItem:
    alert_type: str  # e.g. "earnings", "regime_shift", "stop_trigger", "profit_target"
    level: AlertLevel
    message: str


@dataclass(frozen=True)
class TradeCard:
    rank: int
    candidate_id: int
    generated_at: datetime
    action: str
    underlying: UnderlyingView
    regime: RegimeView
    score: ScoreView
    contract_status: ContractStatus
    contract: Optional[ContractView]
    limit_tiers: List[LimitPriceTier]
    sizing_status: SizingStatus
    sizing: Optional[SizingView]
    stops: StopsView
    alerts: List[AlertItem]
    anti_thesis: str
    notes: List[str] = field(default_factory=list)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


# Matches PickQualityScorer: A high-quality long bias stack requires a Stage 2
# label (with optional rs overlay suffix).
_LONG_STAGE_LABELS = {"2A", "2B", "2C", "2A(RS-)", "2B(RS-)", "2C(RS-)"}
_DISTRIBUTION_LABELS = {"3A", "3B", "4A", "4B", "4C"}


def _d(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _req_d(val: Any) -> Decimal:
    d = _d(val)
    return d if d is not None else Decimal("0")


def _to_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _days_between(earlier: datetime, later: datetime) -> int:
    return (later.date() - earlier.date()).days


def _sum_user_account_value(db: Session, user_id: int) -> Optional[Decimal]:
    """Sum ``total_value`` across the user's active broker accounts.

    Returns ``None`` when the user has no active accounts or every one lacks a
    synced balance. Never silently returns ``0`` for "no data" — callers must
    branch on ``None`` to show the "account unknown" state.
    """
    active = (
        db.query(
            func.count(BrokerAccount.id),
            func.sum(BrokerAccount.total_value),
        )
        .filter(
            BrokerAccount.user_id == user_id,
            BrokerAccount.status == AccountStatus.ACTIVE,
        )
        .one()
    )
    n_accounts, total_sum = int(active[0] or 0), active[1]
    if n_accounts == 0:
        return None
    if total_sum is None:
        return None
    return Decimal(str(total_sum))


def _load_snapshot(db: Session, symbol: str) -> Optional[MarketSnapshot]:
    return (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.is_valid.is_(True),
        )
        .order_by(MarketSnapshot.analysis_timestamp.desc())
        .first()
    )


def _sizing_tier(premium_dollars: Decimal) -> Optional[SizingTier]:
    if premium_dollars <= 0:
        return None
    if premium_dollars < Decimal("1000"):
        return SizingTier.T1_LOTTERY
    if premium_dollars < Decimal("5000"):
        return SizingTier.T2_CONVICTION
    return SizingTier.T3_POSITION


def _underlying_view(snapshot: Optional[MarketSnapshot], symbol: str) -> UnderlyingView:
    if snapshot is None:
        return UnderlyingView(
            symbol=symbol,
            name=None,
            sector=None,
            stage_label=None,
            current_price=None,
            rs_mansfield_pct=None,
            perf_5d=None,
            td_buy_setup=None,
            td_sell_setup=None,
            next_earnings=None,
            days_to_earnings=None,
            atr_14=None,
            atrp_14=None,
            sma_21=None,
            volume_avg_20d=None,
        )
    ne = _to_aware_utc(snapshot.next_earnings)
    today = datetime.now(timezone.utc)
    days_to_earnings = _days_between(today, ne) if ne is not None else None
    return UnderlyingView(
        symbol=symbol,
        name=snapshot.name,
        sector=snapshot.sector,
        stage_label=snapshot.stage_label,
        current_price=_d(snapshot.current_price),
        rs_mansfield_pct=_d(snapshot.rs_mansfield_pct),
        perf_5d=_d(snapshot.perf_5d),
        td_buy_setup=snapshot.td_buy_setup,
        td_sell_setup=snapshot.td_sell_setup,
        next_earnings=ne,
        days_to_earnings=days_to_earnings,
        atr_14=_d(snapshot.atr_14),
        atrp_14=_d(snapshot.atrp_14),
        sma_21=_d(snapshot.sma_21),
        volume_avg_20d=_d(snapshot.volume_avg_20d),
    )


def _regime_view(regime: Optional[MarketRegime]) -> RegimeView:
    if regime is None:
        return RegimeView(
            regime_state="",
            composite_score=None,
            regime_multiplier=Decimal("0"),
            as_of_date=None,
        )
    as_of = regime.as_of_date
    if isinstance(as_of, datetime):
        as_of = as_of.date()
    return RegimeView(
        regime_state=regime.regime_state or "",
        composite_score=_d(regime.composite_score),
        regime_multiplier=_d(regime.regime_multiplier) or Decimal("0"),
        as_of_date=as_of,
    )


def _score_view(score: PickQualityScore) -> ScoreView:
    return ScoreView(
        pick_quality_score=score.total_score,
        regime_multiplier=score.regime_multiplier,
        components={
            name: {
                "raw_score": str(c.raw_score),
                "weight": str(c.weight),
                "weighted_score": str(c.weighted_score),
                "reason": c.reason,
            }
            for name, c in score.components.items()
        },
    )


def _contract_view_from_rec(rec: ContractRecommendation) -> ContractView:
    return ContractView(
        contract_type=rec.contract_type,
        occ_symbol=rec.occ_symbol,
        expiry=rec.expiry,
        strike=rec.strike,
        bid=rec.bid,
        mid=rec.mid,
        ask=rec.ask,
        spread_pct=rec.spread_pct,
        delta=rec.delta,
        open_interest=rec.open_interest,
        volume=rec.volume,
    )


def _limit_tiers_for_option(contract: ContractRecommendation) -> List[LimitPriceTier]:
    """Three limit prices per Kell/Weinstein-style execution discipline.

    Passive sits just above bid so you only fill if supply meets you; mid is
    the midpoint (the "fair" fill); aggressive sits just below ask and is
    flagged ``don't`` because it is the retail-default the product exists to
    discourage.
    """
    bid = contract.bid
    mid = contract.mid
    ask = contract.ask
    passive = (bid + (mid - bid) * Decimal("0.35")).quantize(Decimal("0.01"))
    aggressive = (ask - (ask - mid) * Decimal("0.25")).quantize(Decimal("0.01"))
    return [
        LimitPriceTier(
            tier=LimitTier.PASSIVE,
            price=passive,
            logic=(
                "GTC just above bid; only fills if supply meets you at your "
                "price."
            ),
            fill_likelihood="low",
        ),
        LimitPriceTier(
            tier=LimitTier.MID,
            price=mid.quantize(Decimal("0.01")),
            logic=(
                "Midpoint of bid/ask. Reasonable if thesis is time-sensitive "
                "and spread is tight."
            ),
            fill_likelihood="moderate",
        ),
        LimitPriceTier(
            tier=LimitTier.AGGRESSIVE,
            price=aggressive,
            logic=(
                "Near ask. You pay most of the spread on entry; avoid unless "
                "the setup is tagged urgent."
            ),
            fill_likelihood="don't",
        ),
    ]


def _limit_tiers_for_stock(current_price: Decimal) -> List[LimitPriceTier]:
    """Price tiers when only a stock position is available.

    We anchor the mid tier at the last print, passive at a mild pullback
    (-1.5%), aggressive at a small stretch (+1%). These are intentionally
    conservative; they are not a prediction — they are an execution menu.
    """
    mid = current_price.quantize(Decimal("0.01"))
    passive = (current_price * Decimal("0.985")).quantize(Decimal("0.01"))
    aggressive = (current_price * Decimal("1.01")).quantize(Decimal("0.01"))
    return [
        LimitPriceTier(
            tier=LimitTier.PASSIVE,
            price=passive,
            logic="Pullback buy: 1.5% below last print, GTC day.",
            fill_likelihood="moderate",
        ),
        LimitPriceTier(
            tier=LimitTier.MID,
            price=mid,
            logic="Market-adjacent limit at last print.",
            fill_likelihood="high",
        ),
        LimitPriceTier(
            tier=LimitTier.AGGRESSIVE,
            price=aggressive,
            logic="Chase by 1%. Accepts worse cost basis.",
            fill_likelihood="high",
        ),
    ]


def _calendar_stop(contract: Optional[ContractRecommendation], earnings: Optional[datetime]) -> tuple[Optional[date], Optional[str]]:
    """Calendar stop: earliest of (2 calendar days pre-earnings, contract expiry -7d)."""
    candidates: list[tuple[date, str]] = []
    if earnings is not None:
        pre_earn = earnings.date() - timedelta(days=2)
        candidates.append((pre_earn, f"Exit by {pre_earn.isoformat()} to avoid earnings IV crush"))
    if contract is not None:
        pre_exp = contract.expiry - timedelta(days=7)
        candidates.append((pre_exp, f"Exit by {pre_exp.isoformat()} to avoid gamma-week theta collapse"))
    if not candidates:
        return None, None
    candidates.sort(key=lambda p: p[0])
    return candidates[0]


def _underlying_stop(underlying: UnderlyingView) -> tuple[Optional[Decimal], Optional[str]]:
    """SMA21 break is the default stop anchor per stage analysis; fall back to
    2 ATR below price if SMA21 is missing."""
    if underlying.sma_21 is not None and underlying.sma_21 > 0:
        return underlying.sma_21, "Close below SMA21 = thesis invalidated"
    if underlying.current_price is not None and underlying.atr_14 is not None:
        stop = (underlying.current_price - underlying.atr_14 * Decimal("2")).quantize(
            Decimal("0.01")
        )
        return stop, "Close below 2 ATR from current print"
    return None, None


def _premium_stop(contract_mid: Decimal) -> Decimal:
    """-50% of entry premium is the conviction-tier default (see master plan).

    Returns a per-contract mid threshold. Callers convert to total dollars at
    render.
    """
    return (contract_mid * Decimal("0.5")).quantize(Decimal("0.01"))


def _build_alerts(
    *,
    underlying: UnderlyingView,
    regime: RegimeView,
    contract: Optional[ContractRecommendation],
    calendar_stop: Optional[date],
    pick_score: Decimal,
) -> List[AlertItem]:
    alerts: List[AlertItem] = []
    if underlying.days_to_earnings is not None and underlying.days_to_earnings <= 14:
        alerts.append(
            AlertItem(
                alert_type="earnings",
                level=AlertLevel.CRITICAL if underlying.days_to_earnings <= 7 else AlertLevel.WARNING,
                message=(
                    f"Earnings in {underlying.days_to_earnings}d — confirm "
                    f"contract cashflow exits before the print."
                ),
            )
        )
    if regime.regime_state in {"R4", "R5"}:
        alerts.append(
            AlertItem(
                alert_type="regime_shift",
                level=AlertLevel.WARNING,
                message=(
                    f"Regime {regime.regime_state} — sizing already discounted; "
                    f"exit on any additional regime downgrade."
                ),
            )
        )
    elif regime.regime_state == "R3":
        alerts.append(
            AlertItem(
                alert_type="regime_shift",
                level=AlertLevel.INFO,
                message="Regime R3 (chop) — set a trailing alert for a drop to R4.",
            )
        )
    if contract is not None:
        alerts.append(
            AlertItem(
                alert_type="stop_trigger",
                level=AlertLevel.WARNING,
                message=(
                    f"Premium stop at 50% of entry mid (~"
                    f"{_premium_stop(contract.mid)}) triggers manual close."
                ),
            )
        )
    if calendar_stop is not None:
        alerts.append(
            AlertItem(
                alert_type="calendar",
                level=AlertLevel.INFO,
                message=f"Calendar stop: {calendar_stop.isoformat()} — close before this date regardless of mark.",
            )
        )
    if underlying.td_sell_setup is not None and underlying.td_sell_setup >= 7:
        alerts.append(
            AlertItem(
                alert_type="td_sell",
                level=AlertLevel.WARNING,
                message=f"TD sell setup at {underlying.td_sell_setup} — exhaustion signal forming.",
            )
        )
    if pick_score >= Decimal("70"):
        alerts.append(
            AlertItem(
                alert_type="profit_target",
                level=AlertLevel.INFO,
                message="Scale half at +75% premium; trail the remainder on SMA21.",
            )
        )
    return alerts


def _build_anti_thesis(underlying: UnderlyingView, regime: RegimeView) -> str:
    """One-sentence summary of what would invalidate this trade."""
    reasons: List[str] = []
    stage = (underlying.stage_label or "").upper()
    if stage in _DISTRIBUTION_LABELS:
        reasons.append(f"Stage {underlying.stage_label} is distribution — not a long-bias setup")
    if underlying.td_sell_setup is not None and underlying.td_sell_setup >= 7:
        reasons.append(f"TD sell {underlying.td_sell_setup} signals exhaustion")
    if regime.regime_state == "R5":
        reasons.append("Regime R5 caps equity exposure at 10% — sizing is nominal")
    if underlying.days_to_earnings is not None and underlying.days_to_earnings <= 7:
        reasons.append(f"Earnings in {underlying.days_to_earnings}d — IV crush risk dominates direction")
    if not reasons:
        if underlying.sma_21 is not None and underlying.current_price is not None:
            reasons.append(
                "Close below SMA21 or two consecutive distribution days invalidates the setup"
            )
        else:
            reasons.append("Loss of volume confirmation or a stage transition invalidates the setup")
    return "; ".join(reasons)


def _resolve_contract_status_for_earnings(
    underlying: UnderlyingView,
    contract: Optional[ContractRecommendation],
) -> Optional[ContractStatus]:
    """If earnings land in the pre-expiry window, the chain pick is unsafe.

    The window is two calendar days before contract expiry through expiry
    (inclusive). When earnings falls in that span and the print is still today
    or in the future, return ``SKIPPED_EARNINGS`` so the composer drops the
    chain and falls back to a stock-only card with an explicit alert.
    """
    if contract is None or underlying.next_earnings is None:
        return None
    earn_d = underlying.next_earnings.date()
    window_start = contract.expiry - timedelta(days=2)
    window_end = contract.expiry
    if not (window_start <= earn_d <= window_end):
        return None
    today = datetime.now(timezone.utc).date()
    if today <= earn_d:
        return ContractStatus.SKIPPED_EARNINGS
    return None


# ----------------------------------------------------------------------------
# Public composer
# ----------------------------------------------------------------------------


@dataclass
class TradeCardComposer:
    """Compose :class:`TradeCard` objects from scored candidates.

    ``options_surface`` is optional; when absent the composer returns a card
    with an explicit ``CHAIN_UNAVAILABLE`` contract status. The UI layer is
    responsible for telling the user the surface isn't wired yet.

    ``pick_scorer`` defaults to a fresh :class:`PickQualityScorer`; inject a
    preconfigured one in tests.
    """

    options_surface: Optional[OptionsChainSurface] = None
    pick_scorer: PickQualityScorer = field(default_factory=PickQualityScorer)
    default_bias: ContractType = ContractType.CALL_DEBIT
    risk_budget_fraction: Decimal = Decimal("0.01")  # 1% of equity per trade

    def compose(
        self,
        db: Session,
        *,
        candidate: Candidate,
        user: User,
        rank: int = 1,
        regime: Optional[MarketRegime] = None,
        snapshot: Optional[MarketSnapshot] = None,
        account_value_override: Any = ACCOUNT_VALUE_FETCH,
    ) -> TradeCard:
        """Build a complete trade card for one candidate."""
        symbol = (candidate.symbol or "").upper().strip()
        if snapshot is None:
            snapshot = _load_snapshot(db, symbol)
        regime = regime if regime is not None else get_current_regime(db)
        underlying = _underlying_view(snapshot, symbol)
        regime_v = _regime_view(regime)

        try:
            pick_score = self.pick_scorer.score_from_row(
                db, snapshot, symbol, user.id, regime_row=regime
            )
        except Exception:
            logger.exception(
                "trade_card_composer: pick scoring failed for %s (user_id=%s)",
                symbol,
                user.id,
            )
            raise

        score_v = _score_view(pick_score)

        account_value = (
            _sum_user_account_value(db, user.id)
            if account_value_override is ACCOUNT_VALUE_FETCH
            else account_value_override
        )

        contract_rec: Optional[ContractRecommendation] = None
        contract_status = ContractStatus.CHAIN_UNAVAILABLE
        notes: List[str] = []

        if self.options_surface is not None and underlying.current_price is not None:
            try:
                contract_rec = self.options_surface.recommend_contract(
                    db,
                    symbol=symbol,
                    current_price=underlying.current_price,
                    earnings_date=underlying.next_earnings,
                    bias=self.default_bias,
                )
            except Exception:
                # Log + continue: card must still render a stock-only plan.
                # Raising here would take the whole /trade-cards/today page down
                # when a single provider hiccups.
                logger.exception(
                    "trade_card_composer: options surface failed for %s",
                    symbol,
                )
                contract_rec = None
                notes.append(
                    "Options chain lookup failed; stock-only sizing shown."
                )
            if contract_rec is None:
                contract_status = ContractStatus.CHAIN_UNAVAILABLE
            else:
                contract_status = ContractStatus.READY

        earnings_override = _resolve_contract_status_for_earnings(underlying, contract_rec)
        if earnings_override is not None:
            contract_rec = None
            contract_status = earnings_override
            notes.append(
                "Earnings fall inside contract window — chain pick suppressed; "
                "use stock sizing or wait for post-earnings chain."
            )

        if contract_rec is None and self.options_surface is None:
            # No surface wired at all; we'll still render a stock-only card.
            contract_status = ContractStatus.STOCK_ONLY

        contract_view = _contract_view_from_rec(contract_rec) if contract_rec else None

        sizing_v, sizing_status, limit_tiers = self._size_position(
            underlying=underlying,
            regime=regime_v,
            contract=contract_rec,
            account_value=account_value,
        )

        underlying_stop, underlying_stop_reason = _underlying_stop(underlying)
        cal_stop, cal_reason = _calendar_stop(contract_rec, underlying.next_earnings)
        premium_stop = _premium_stop(contract_rec.mid) if contract_rec is not None else None

        stops = StopsView(
            premium_stop=premium_stop,
            underlying_stop=underlying_stop,
            underlying_stop_reason=underlying_stop_reason,
            calendar_stop=cal_stop,
            calendar_stop_reason=cal_reason,
        )

        alerts = _build_alerts(
            underlying=underlying,
            regime=regime_v,
            contract=contract_rec,
            calendar_stop=cal_stop,
            pick_score=score_v.pick_quality_score,
        )
        if sizing_status is SizingStatus.ACCOUNT_UNKNOWN:
            alerts.append(
                AlertItem(
                    alert_type="account",
                    level=AlertLevel.WARNING,
                    message="Connect a brokerage account to compute exact sizing.",
                )
            )
        if sizing_status is SizingStatus.REGIME_BLOCKED:
            alerts.append(
                AlertItem(
                    alert_type="regime_blocked",
                    level=AlertLevel.CRITICAL,
                    message=(
                        f"Stage {underlying.stage_label} in regime {regime_v.regime_state} "
                        "has zero allowed exposure — the card is informational only."
                    ),
                )
            )

        anti_thesis = _build_anti_thesis(underlying, regime_v)

        action = (
            candidate.action_suggestion.value
            if isinstance(candidate.action_suggestion, PickAction)
            else str(candidate.action_suggestion or "").lower()
        ) or "buy"

        generated_at = _to_aware_utc(candidate.generated_at) or datetime.now(timezone.utc)

        return TradeCard(
            rank=rank,
            candidate_id=int(candidate.id or 0),
            generated_at=generated_at,
            action=action.upper(),
            underlying=underlying,
            regime=regime_v,
            score=score_v,
            contract_status=contract_status,
            contract=contract_view,
            limit_tiers=limit_tiers,
            sizing_status=sizing_status,
            sizing=sizing_v,
            stops=stops,
            alerts=alerts,
            anti_thesis=anti_thesis,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def _size_position(
        self,
        *,
        underlying: UnderlyingView,
        regime: RegimeView,
        contract: Optional[ContractRecommendation],
        account_value: Optional[Decimal],
    ) -> tuple[Optional[SizingView], SizingStatus, List[LimitPriceTier]]:
        """Compute sizing + limit tiers.

        Returns ``(sizing_view, sizing_status, limit_tiers)``. Limit tiers are
        derived here because they depend on whether we have a contract pick.
        """
        if account_value is None or account_value <= 0:
            tiers = (
                _limit_tiers_for_option(contract)
                if contract is not None
                else (
                    _limit_tiers_for_stock(underlying.current_price)
                    if underlying.current_price is not None
                    else []
                )
            )
            return None, SizingStatus.ACCOUNT_UNKNOWN, tiers

        if (
            underlying.current_price is None
            or underlying.atrp_14 is None
            or underlying.stage_label is None
            or regime.regime_state == ""
        ):
            return None, SizingStatus.INPUTS_MISSING, []

        risk_budget = (account_value * self.risk_budget_fraction).quantize(Decimal("0.01"))

        # ``compute_position_size`` is the one capital-protection helper we are
        # allowed to call. It takes floats by historical contract; we cast at
        # the boundary and convert results back to Decimal immediately.
        result = compute_position_size(
            risk_budget=float(risk_budget),
            atrp_14=float(underlying.atrp_14),
            stop_multiplier=float(DEFAULT_STOP_MULTIPLIER),
            regime_state=regime.regime_state,
            stage_label=underlying.stage_label,
            current_price=float(underlying.current_price),
        )

        capped = Decimal(str(result.capped_position_dollars))
        full = Decimal(str(result.full_position_dollars))
        stage_cap = Decimal(str(result.stage_cap))
        shares = int(result.shares)

        if capped <= 0 or stage_cap == 0:
            tiers = (
                _limit_tiers_for_option(contract)
                if contract is not None
                else _limit_tiers_for_stock(underlying.current_price)
            )
            sizing = SizingView(
                tier=None,
                contracts=0,
                shares=0,
                premium_dollars=Decimal("0"),
                premium_pct_of_account=Decimal("0"),
                full_position_dollars=full,
                capped_position_dollars=capped,
                stage_cap=stage_cap,
                regime_multiplier=regime.regime_multiplier,
                account_size=account_value,
                risk_budget=risk_budget,
            )
            return sizing, SizingStatus.REGIME_BLOCKED, tiers

        if contract is not None:
            contracts, premium_dollars = self._contracts_from_cap(capped, contract.mid)
            tier = _sizing_tier(premium_dollars)
            pct = (
                (premium_dollars / account_value * Decimal("100")).quantize(Decimal("0.01"))
                if account_value > 0
                else Decimal("0")
            )
            sizing = SizingView(
                tier=tier,
                contracts=contracts,
                shares=0,
                premium_dollars=premium_dollars,
                premium_pct_of_account=pct,
                full_position_dollars=full,
                capped_position_dollars=capped,
                stage_cap=stage_cap,
                regime_multiplier=regime.regime_multiplier,
                account_size=account_value,
                risk_budget=risk_budget,
            )
            tiers = _limit_tiers_for_option(contract)
        else:
            pct = (
                (capped / account_value * Decimal("100")).quantize(Decimal("0.01"))
                if account_value > 0
                else Decimal("0")
            )
            sizing = SizingView(
                tier=None,
                contracts=0,
                shares=shares,
                premium_dollars=Decimal("0"),
                premium_pct_of_account=pct,
                full_position_dollars=full,
                capped_position_dollars=capped,
                stage_cap=stage_cap,
                regime_multiplier=regime.regime_multiplier,
                account_size=account_value,
                risk_budget=risk_budget,
            )
            tiers = _limit_tiers_for_stock(underlying.current_price)

        return sizing, SizingStatus.COMPUTED, tiers

    @staticmethod
    def _contracts_from_cap(
        capped_dollars: Decimal, contract_mid: Decimal
    ) -> tuple[int, Decimal]:
        """Integer contract count that fits under the capped budget."""
        if contract_mid <= 0:
            return 0, Decimal("0")
        cost_per_contract = contract_mid * Decimal("100")
        contracts = int((capped_dollars / cost_per_contract).to_integral_value(rounding="ROUND_FLOOR"))
        contracts = max(contracts, 0)
        premium = (Decimal(contracts) * cost_per_contract).quantize(Decimal("0.01"))
        return contracts, premium


# ----------------------------------------------------------------------------
# Serialization
# ----------------------------------------------------------------------------


def _d_or_none(v: Optional[Decimal]) -> Optional[str]:
    return str(v) if v is not None else None


def trade_card_to_payload(card: TradeCard) -> Dict[str, Any]:
    """JSON-serializable payload for the trade-cards API."""
    u = card.underlying
    r = card.regime
    s = card.score
    c = card.contract
    z = card.sizing
    st = card.stops
    return {
        "rank": card.rank,
        "candidate_id": card.candidate_id,
        "generated_at": card.generated_at.isoformat(),
        "action": card.action,
        "underlying": {
            "symbol": u.symbol,
            "name": u.name,
            "sector": u.sector,
            "stage_label": u.stage_label,
            "current_price": _d_or_none(u.current_price),
            "rs_mansfield_pct": _d_or_none(u.rs_mansfield_pct),
            "perf_5d": _d_or_none(u.perf_5d),
            "td_buy_setup": u.td_buy_setup,
            "td_sell_setup": u.td_sell_setup,
            "next_earnings": u.next_earnings.isoformat() if u.next_earnings else None,
            "days_to_earnings": u.days_to_earnings,
            "atr_14": _d_or_none(u.atr_14),
            "atrp_14": _d_or_none(u.atrp_14),
            "sma_21": _d_or_none(u.sma_21),
            "volume_avg_20d": _d_or_none(u.volume_avg_20d),
        },
        "regime": {
            "regime_state": r.regime_state,
            "composite_score": _d_or_none(r.composite_score),
            "regime_multiplier": str(r.regime_multiplier),
            "as_of_date": r.as_of_date.isoformat() if r.as_of_date else None,
        },
        "score": {
            "pick_quality_score": str(s.pick_quality_score),
            "regime_multiplier": str(s.regime_multiplier),
            "components": s.components,
        },
        "contract_status": card.contract_status.value,
        "contract": (
            None
            if c is None
            else {
                "contract_type": c.contract_type.value,
                "occ_symbol": c.occ_symbol,
                "expiry": c.expiry.isoformat(),
                "strike": str(c.strike),
                "bid": str(c.bid),
                "mid": str(c.mid),
                "ask": str(c.ask),
                "spread_pct": str(c.spread_pct),
                "delta": _d_or_none(c.delta),
                "open_interest": c.open_interest,
                "volume": c.volume,
            }
        ),
        "limit_tiers": [
            {
                "tier": t.tier.value,
                "price": str(t.price),
                "logic": t.logic,
                "fill_likelihood": t.fill_likelihood,
            }
            for t in card.limit_tiers
        ],
        "sizing_status": card.sizing_status.value,
        "sizing": (
            None
            if z is None
            else {
                "tier": z.tier.value if z.tier is not None else None,
                "contracts": z.contracts,
                "shares": z.shares,
                "premium_dollars": str(z.premium_dollars),
                "premium_pct_of_account": str(z.premium_pct_of_account),
                "full_position_dollars": str(z.full_position_dollars),
                "capped_position_dollars": str(z.capped_position_dollars),
                "stage_cap": str(z.stage_cap),
                "regime_multiplier": str(z.regime_multiplier),
                "account_size": str(z.account_size),
                "risk_budget": str(z.risk_budget),
            }
        ),
        "stops": {
            "premium_stop": _d_or_none(st.premium_stop),
            "underlying_stop": _d_or_none(st.underlying_stop),
            "underlying_stop_reason": st.underlying_stop_reason,
            "calendar_stop": st.calendar_stop.isoformat() if st.calendar_stop else None,
            "calendar_stop_reason": st.calendar_stop_reason,
        },
        "alerts": [
            {
                "alert_type": a.alert_type,
                "level": a.level.value,
                "message": a.message,
            }
            for a in card.alerts
        ],
        "anti_thesis": card.anti_thesis,
        "notes": list(card.notes),
    }


__all__ = [
    "AlertItem",
    "AlertLevel",
    "ContractRecommendation",
    "ContractStatus",
    "ContractType",
    "ContractView",
    "LimitPriceTier",
    "LimitTier",
    "OptionsChainSurface",
    "RegimeView",
    "ScoreView",
    "SizingStatus",
    "SizingTier",
    "SizingView",
    "StopsView",
    "TradeCard",
    "TradeCardComposer",
    "UnderlyingView",
    "trade_card_to_payload",
]
