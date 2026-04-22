"""Pick quality scoring: 0-100 explainable composite from ``MarketSnapshot``.

Reads pre-computed snapshot fields only (no indicator recompute).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.models.market_data import MarketRegime, MarketSnapshot
from backend.services.gold.pick_scorer_config import (
    BASE_STAGE_LABELS,
    DIST_STAGE_LABELS,
    HIGH_STAGE_LABELS,
    LATE_STAGE_LABELS,
    MID_STAGE_LABELS,
    PickScorerConfig,
    default_config,
    regime_alignment_raw_score,
    regime_multiplier,
)
from backend.services.market.regime_engine import get_current_regime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComponentScore:
    raw_score: Decimal
    weight: Decimal
    weighted_score: Decimal
    reason: str


@dataclass(frozen=True)
class PickQualityScore:
    symbol: str
    total_score: Decimal
    components: Dict[str, ComponentScore]
    computed_at: datetime
    regime_multiplier: Decimal


def _d(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (ArithmeticError, TypeError, ValueError):
        return None


def _clip_score(x: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), x))


def _snapshot_reference_time(row: MarketSnapshot) -> datetime:
    ref = row.as_of_timestamp or row.analysis_timestamp
    if ref is not None:
        if ref.tzinfo is None:
            return ref.replace(tzinfo=timezone.utc)
        return ref
    return datetime.now(timezone.utc)


class PickQualityScorer:
    """Scores a symbol for long-bias pick quality."""

    def __init__(self, config: Optional[PickScorerConfig] = None) -> None:
        self._cfg = config or default_config()

    def score(
        self,
        db: Session,
        symbol: str,
        user_id: int,
        *,
        regime_row: Optional[MarketRegime] = None,
    ) -> PickQualityScore:
        """Compute quality score. ``user_id`` is required for API contract;
        market snapshots are not tenant-scoped today (see module note).
        """
        sym = (symbol or "").upper().strip()
        row = self._load_snapshot(db, sym)
        return self.score_from_row(
            db,
            row,
            sym,
            user_id,
            regime_row=regime_row,
        )

    def score_from_row(
        self,
        db: Session,
        row: Optional[MarketSnapshot],
        symbol: str,
        user_id: int,
        *,
        regime_row: Optional[MarketRegime] = None,
    ) -> PickQualityScore:
        """Score using a pre-fetched snapshot row (or ``None`` if missing).

        ``db`` is used when ``regime_row`` is None (see ``get_current_regime``).
        """
        sym = (symbol or "").upper().strip()
        now = datetime.now(timezone.utc)
        regime = regime_row if regime_row is not None else get_current_regime(db)
        regime_code = regime.regime_state if regime is not None else ""
        mult = regime_multiplier(regime_code)

        if row is None:
            logger.warning(
                "pick quality: snapshot data not available for %s (user_id=%s)",
                sym,
                user_id,
            )
            return self._empty_score(
                sym, now, mult, reason="snapshot data not available"
            )

        components: Dict[str, ComponentScore] = {}
        ref = _snapshot_reference_time(row)

        components["stage"] = self._score_stage(sym, row)
        components["rs"] = self._score_rs(sym, row)
        components["regime"] = self._score_regime_component(regime_code)
        components["td"] = self._score_td(sym, row)
        components["pullback"] = self._score_pullback(sym, row)
        components["liquidity"] = self._score_liquidity(sym, row)
        components["earnings"] = self._score_earnings(sym, row, ref)

        weighted_sum = Decimal("0")
        for c in components.values():
            weighted_sum += c.weighted_score

        pre_clip = weighted_sum * mult
        total = _clip_score(pre_clip)

        return PickQualityScore(
            symbol=sym,
            total_score=total.quantize(Decimal("0.01")),
            components=components,
            computed_at=now,
            regime_multiplier=mult,
        )

    def score_with_counts(
        self,
        db: Session,
        symbol: str,
        user_id: int,
        *,
        regime_row: Optional[MarketRegime] = None,
        snapshot_row: Optional[MarketSnapshot] = None,
        fetch_snapshot: bool = True,
    ) -> tuple[PickQualityScore, str]:
        """Returns (score, outcome) where outcome is scored|skipped|errored."""
        sym = (symbol or "").upper().strip()
        try:
            if fetch_snapshot:
                row = (
                    self._load_snapshot(db, sym)
                    if snapshot_row is None
                    else snapshot_row
                )
            else:
                row = snapshot_row
            pq = self.score_from_row(db, row, sym, user_id, regime_row=regime_row)
            if row is None:
                return pq, "skipped"
            return pq, "scored"
        except Exception:
            logger.exception(
                "pick quality scoring failed for %s (user_id=%s)",
                sym,
                user_id,
            )
            regime = regime_row if regime_row is not None else get_current_regime(db)
            code = regime.regime_state if regime is not None else ""
            mult = regime_multiplier(code)
            return (
                self._empty_score(
                    sym,
                    datetime.now(timezone.utc),
                    mult,
                    reason="scoring_error",
                ),
                "errored",
            )

    def _load_snapshot(self, db: Session, symbol: str) -> Optional[MarketSnapshot]:
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

    def _empty_score(
        self,
        symbol: str,
        computed_at: datetime,
        mult: Decimal,
        *,
        reason: str,
    ) -> PickQualityScore:
        cfg = self._cfg
        z = Decimal("0")
        comps = {
            "stage": self._mk(z, reason, cfg.weight_stage),
            "rs": self._mk(z, reason, cfg.weight_rs),
            "regime": self._mk(z, reason, cfg.weight_regime),
            "td": self._mk(z, reason, cfg.weight_td),
            "pullback": self._mk(z, reason, cfg.weight_pullback),
            "liquidity": self._mk(z, reason, cfg.weight_liquidity),
            "earnings": self._mk(z, reason, cfg.weight_earnings),
        }
        return PickQualityScore(
            symbol=symbol,
            total_score=z,
            components=comps,
            computed_at=computed_at,
            regime_multiplier=mult,
        )

    def _mk(
        self,
        raw: Decimal,
        reason: str,
        weight: Decimal,
    ) -> ComponentScore:
        w = (raw * weight).quantize(Decimal("0.0001"))
        return ComponentScore(
            raw_score=raw.quantize(Decimal("0.01")),
            weight=weight,
            weighted_score=w,
            reason=reason,
        )

    def _score_stage(self, symbol: str, row: MarketSnapshot) -> ComponentScore:
        cfg = self._cfg
        label = (row.stage_label or "").strip().upper()
        if not label:
            return self._mk(
                Decimal("0"),
                "Stage label not available",
                cfg.weight_stage,
            )
        if label in HIGH_STAGE_LABELS:
            raw = Decimal("95")
            reason = f"Stage {row.stage_label} (high-quality advance)"
        elif label in MID_STAGE_LABELS:
            raw = Decimal("72")
            reason = f"Stage {row.stage_label} (later advance; monitor extension)"
        elif label in LATE_STAGE_LABELS:
            raw = Decimal("25")
            reason = f"Stage {row.stage_label} (distribution phase)"
        elif label in DIST_STAGE_LABELS:
            raw = Decimal("8")
            reason = f"Stage {row.stage_label} (weak for new longs)"
        elif label in BASE_STAGE_LABELS:
            raw = Decimal("15")
            reason = f"Stage {row.stage_label} (base-building; early)"
        else:
            raw = Decimal("20")
            reason = f"Stage {row.stage_label} (nonstandard label)"
        return self._mk(_clip_score(raw), reason, cfg.weight_stage)

    def _score_rs(self, symbol: str, row: MarketSnapshot) -> ComponentScore:
        cfg = self._cfg
        rs = row.rs_mansfield_pct
        if rs is None:
            return self._mk(
                Decimal("0"),
                "RS data not available",
                cfg.weight_rs,
            )
        raw = _clip_score(_d(rs) or Decimal("0"))
        return self._mk(
            raw,
            f"RS Mansfield {float(rs):.1f}",
            cfg.weight_rs,
        )

    def _score_regime_component(self, regime_code: str) -> ComponentScore:
        cfg = self._cfg
        raw, reason = regime_alignment_raw_score(regime_code)
        return self._mk(
            _clip_score(raw),
            reason,
            cfg.weight_regime,
        )

    def _score_td(self, symbol: str, row: MarketSnapshot) -> ComponentScore:
        cfg = self._cfg
        buy_n = row.td_buy_setup
        sell_n = row.td_sell_setup
        if buy_n is None and sell_n is None:
            return self._mk(
                Decimal("0"),
                "TD Sequential not yet computed",
                cfg.weight_td,
            )
        b = int(buy_n or 0)
        s = int(sell_n or 0)
        if 7 <= b <= 9:
            raw = Decimal("95")
            reason = f"TD buy setup {b} (favorable pullback structure)"
        elif 4 <= b <= 6:
            raw = Decimal("70")
            reason = f"TD buy setup {b} (developing)"
        elif 1 <= b <= 3:
            raw = Decimal("50")
            reason = f"TD buy setup {b} (early)"
        elif b == 0 and s >= 7:
            raw = Decimal("25")
            reason = f"TD sell setup {s} (caution for longs)"
        elif b == 0 and s > 0:
            raw = Decimal("45")
            reason = f"TD sell setup {s} (monitor)"
        else:
            raw = Decimal("55")
            reason = "TD sequential neutral for this snapshot"
        return self._mk(raw, reason, cfg.weight_td)

    def _score_pullback(self, symbol: str, row: MarketSnapshot) -> ComponentScore:
        cfg = self._cfg
        high = _d(row.high_52w)
        price = _d(row.current_price)
        atr = _d(row.atr_14)
        if high is None or price is None or atr is None or atr <= 0:
            return self._mk(
                Decimal("0"),
                "Pullback/ATR data not available",
                cfg.weight_pullback,
            )
        drop = high - price
        if drop < 0:
            raw = Decimal("85")
            reason = "Price above 52w high print (strong; verify data freshness)"
        else:
            atr_mult = drop / atr
            if atr_mult <= Decimal("2"):
                raw = Decimal("95")
                reason = f"Orderly pullback (~{atr_mult:.1f} ATR off 52w high)"
            elif atr_mult <= Decimal("4"):
                raw = Decimal("75")
                reason = f"Moderate pullback (~{atr_mult:.1f} ATR off 52w high)"
            elif atr_mult <= Decimal("6"):
                raw = Decimal("50")
                reason = f"Deep pullback (~{atr_mult:.1f} ATR off 52w high)"
            else:
                raw = Decimal("25")
                reason = f"Stressed pullback (~{atr_mult:.1f} ATR off 52w high)"
        return self._mk(raw, reason, cfg.weight_pullback)

    def _score_liquidity(self, symbol: str, row: MarketSnapshot) -> ComponentScore:
        cfg = self._cfg
        vol = _d(row.volume_avg_20d)
        px = _d(row.current_price)
        if vol is None or px is None or vol <= 0 or px <= 0:
            return self._mk(
                Decimal("0"),
                "Liquidity inputs not available (volume/price)",
                cfg.weight_liquidity,
            )
        dv = vol * px
        floor = cfg.min_dollar_volume_20d
        if dv < floor:
            return self._mk(
                Decimal("0"),
                f"Estimated ${dv:.0f} 20d dollar volume below floor",
                cfg.weight_liquidity,
            )
        ratio = dv / floor
        if ratio >= Decimal("2"):
            raw = Decimal("100")
        else:
            raw = Decimal("70") + (ratio - Decimal("1")) * Decimal("30")
        raw = _clip_score(raw)
        return self._mk(
            raw,
            f"Estimated dollar volume {dv:.0f} vs floor {floor:.0f}",
            cfg.weight_liquidity,
        )

    def _score_earnings(
        self,
        symbol: str,
        row: MarketSnapshot,
        ref: datetime,
    ) -> ComponentScore:
        cfg = self._cfg
        ne = row.next_earnings
        if ne is None:
            return self._mk(
                Decimal("100"),
                "No upcoming earnings date on snapshot",
                cfg.weight_earnings,
            )
        if ne.tzinfo is None:
            ne = ne.replace(tzinfo=timezone.utc)
        ref_d = ref.date()
        earn_d = ne.date()
        days = (earn_d - ref_d).days
        if days < 0:
            return self._mk(
                Decimal("100"),
                "Next earnings date is in the past on snapshot",
                cfg.weight_earnings,
            )
        if days >= cfg.earnings_lookahead_days:
            return self._mk(
                Decimal("100"),
                f"Earnings in {days}d (outside lookahead window)",
                cfg.weight_earnings,
            )
        hr = cfg.earnings_high_risk_days
        if days <= hr:
            raw = (Decimal(days) / Decimal(hr)) * Decimal("25")
            raw = _clip_score(raw)
            reason = f"Earnings in {days}d (high proximity risk)"
        else:
            span = Decimal(cfg.earnings_lookahead_days - hr)
            frac = (Decimal(days - hr) / span) if span > 0 else Decimal("1")
            raw = Decimal("25") + frac * Decimal("75")
            raw = _clip_score(raw)
            reason = f"Earnings in {days}d (within lookahead)"
        return self._mk(raw, reason, cfg.weight_earnings)


def pick_quality_to_payload(score: PickQualityScore) -> Dict[str, Any]:
    """JSON-serializable dict for API and ``Candidate`` JSON storage."""
    return {
        "symbol": score.symbol,
        "total_score": str(score.total_score),
        "regime_multiplier": str(score.regime_multiplier),
        "computed_at": score.computed_at.isoformat(),
        "components": {
            k: {
                "raw_score": str(v.raw_score),
                "weight": str(v.weight),
                "weighted_score": str(v.weighted_score),
                "reason": v.reason,
            }
            for k, v in score.components.items()
        },
    }
