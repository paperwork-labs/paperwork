"""Conviction Pick Generator.

Multi-year horizon picks for the ``conviction`` sleeve. Consumes the
latest ``MarketSnapshot`` (technical + best-effort fundamentals) row
per symbol and ranks by a composite score that reflects the qualities
we want a multi-year hold to have:

* Long-term Stage 2 posture (Weinstein-refined, SMA150 anchor)
* Sustained relative strength vs benchmark
* Earnings trajectory (EPS growth YoY)
* Fundamentals proxy (PE reasonableness, revenue growth)
* Range position that isn't at 52w highs (mean reversion risk)

The generator is intentionally **read-only** against ``MarketSnapshot``
— no providers, no sessions opened here. A Celery task owns the
session boundary and the persist step (see
``app/tasks/market/conviction.py``).

Per the no-silent-fallback rule, every filter increments a named
counter; every skipped symbol is counted; rejection reasons are logged
in aggregate at the end of each batch for observability without log
spam; the final counters are asserted to sum to ``total`` so a
regression can't hide behind an aggregate "N picks generated" log line.

Score math is pure Python ``Decimal`` so persisted scores do not
round-trip through binary float.

medallion: gold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session, load_only

from app.models.market_data import MarketSnapshot

logger = logging.getLogger(__name__)


GENERATOR_VERSION = "v1"


# ---------------------------------------------------------------------------
# Tunables (frozen at this generator version; bump GENERATOR_VERSION on change)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConvictionThresholds:
    """Admissibility + scoring knobs.

    ``eligible_stages`` — only advancing / early-base stages qualify. A
    Stage 4 name is never a conviction pick by definition.

    ``min_rs_mansfield_pct`` — long-horizon leadership floor. Lower than
    the short-term generator (70) because we're willing to accept "still
    consolidating leadership" names.

    ``min_eps_growth_yoy_pct`` — ``None`` means "accept null/unknown",
    otherwise reject rows with EPS growth below this.

    ``max_range_pos_52w`` — stay away from literal 52w highs to reduce
    exhaustion risk; we want progression, not chase.
    """

    eligible_stages: tuple[str, ...] = ("1B", "2A", "2B")
    min_rs_mansfield_pct: float = 55.0
    min_eps_growth_yoy_pct: Optional[float] = 0.0
    max_pe_ttm: Optional[float] = 60.0
    max_range_pos_52w: float = 0.95
    min_range_pos_52w: float = 0.40
    min_stage_days: int = 20
    max_results: int = 25

    # Score weights — must sum to ~1.0. Adjusted for the metrics
    # currently surfaced on ``MarketSnapshot``; a fundamentals-heavy
    # rebalance lands when the EPS-growth and valuation feeds widen.
    w_stage_posture: float = 0.25
    w_rs: float = 0.25
    w_eps_growth: float = 0.20
    w_valuation: float = 0.15
    w_range_pos: float = 0.15


DEFAULT_THRESHOLDS = ConvictionThresholds()


# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConvictionCandidate:
    """One ranked conviction-sleeve candidate, ready for persistence."""

    symbol: str
    rank: int
    score: Decimal
    stage_label: Optional[str]
    rationale: str
    breakdown: Dict[str, Any]


@dataclass
class GenerationReport:
    """Structured output of a generator run.

    Per the no-silent-fallback rule, callers assert::

        eligible + skipped_stage + skipped_rs + skipped_eps
            + skipped_valuation + skipped_range + skipped_other
        == total_scanned
    """

    total_scanned: int = 0
    eligible: int = 0
    skipped_stage: int = 0
    skipped_rs: int = 0
    skipped_eps: int = 0
    skipped_valuation: int = 0
    skipped_range: int = 0
    skipped_other: int = 0
    candidates: List[ConvictionCandidate] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_scanned": self.total_scanned,
            "eligible": self.eligible,
            "skipped_stage": self.skipped_stage,
            "skipped_rs": self.skipped_rs,
            "skipped_eps": self.skipped_eps,
            "skipped_valuation": self.skipped_valuation,
            "skipped_range": self.skipped_range,
            "skipped_other": self.skipped_other,
            "candidate_count": len(self.candidates),
        }


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class ConvictionPickGenerator:
    """Rank the market universe for multi-year conviction hold picks."""

    name = "conviction_pick"
    version = GENERATOR_VERSION

    def __init__(self, thresholds: Optional[ConvictionThresholds] = None) -> None:
        self.t = thresholds or DEFAULT_THRESHOLDS

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(self, db: Session) -> GenerationReport:
        """Scan latest snapshots, filter, rank, and return a report.

        The caller owns session + commit scope.
        """
        report = GenerationReport()
        rows = self._latest_snapshots(db)
        report.total_scanned = len(rows)

        scored: List[tuple[Decimal, MarketSnapshot, Dict[str, Any], str]] = []
        for row in rows:
            decision = self._evaluate(row)
            if decision["status"] == "eligible":
                report.eligible += 1
                scored.append(
                    (
                        decision["score"],
                        row,
                        decision["breakdown"],
                        decision["rationale"],
                    )
                )
            elif decision["status"] == "skipped_stage":
                report.skipped_stage += 1
            elif decision["status"] == "skipped_rs":
                report.skipped_rs += 1
            elif decision["status"] == "skipped_eps":
                report.skipped_eps += 1
            elif decision["status"] == "skipped_valuation":
                report.skipped_valuation += 1
            elif decision["status"] == "skipped_range":
                report.skipped_range += 1
            else:
                report.skipped_other += 1

        # Counter integrity — sum must equal total scanned (no silent
        # fallback). A drift means a branch returned an unknown status.
        sum_counters = (
            report.eligible
            + report.skipped_stage
            + report.skipped_rs
            + report.skipped_eps
            + report.skipped_valuation
            + report.skipped_range
            + report.skipped_other
        )
        assert sum_counters == report.total_scanned, (
            f"counter drift: {sum_counters} != {report.total_scanned}"
        )

        scored.sort(key=lambda x: x[0], reverse=True)
        scored = scored[: self.t.max_results]
        for rank_idx, (score, row, breakdown, rationale) in enumerate(scored, 1):
            report.candidates.append(
                ConvictionCandidate(
                    symbol=(row.symbol or "").upper(),
                    rank=rank_idx,
                    score=score,
                    stage_label=row.stage_label,
                    rationale=rationale,
                    breakdown=breakdown,
                )
            )

        logger.info(
            "conviction generator complete: %s",
            report.to_dict(),
        )
        return report

    # ------------------------------------------------------------------
    # Snapshot read
    # ------------------------------------------------------------------

    def _latest_snapshots(self, db: Session) -> List[MarketSnapshot]:
        """Latest technical snapshot per symbol meeting cheap stage prefilter."""
        latest_ids = (
            db.query(func.max(MarketSnapshot.id).label("id"))
            .filter(
                MarketSnapshot.analysis_type == "technical_snapshot",
                MarketSnapshot.is_valid.is_(True),
                MarketSnapshot.stage_label.in_(self.t.eligible_stages),
            )
            .group_by(MarketSnapshot.symbol)
            .subquery()
        )
        rows = (
            db.query(MarketSnapshot)
            .options(
                load_only(
                    MarketSnapshot.id,
                    MarketSnapshot.symbol,
                    MarketSnapshot.stage_label,
                    MarketSnapshot.current_stage_days,
                    MarketSnapshot.rs_mansfield_pct,
                    MarketSnapshot.range_pos_52w,
                    MarketSnapshot.eps_growth_yoy,
                    MarketSnapshot.revenue_growth_yoy,
                    MarketSnapshot.pe_ttm,
                    MarketSnapshot.peg_ttm,
                    MarketSnapshot.current_price,
                    MarketSnapshot.sma_150,
                    MarketSnapshot.action_label,
                )
            )
            .filter(MarketSnapshot.id.in_(latest_ids.select()))
            .all()
        )
        return rows

    # ------------------------------------------------------------------
    # Per-row evaluation
    # ------------------------------------------------------------------

    def _evaluate(self, row: MarketSnapshot) -> Dict[str, Any]:
        symbol = (row.symbol or "").upper()
        if not symbol:
            return {"status": "skipped_other"}

        if row.stage_label not in self.t.eligible_stages:
            return {"status": "skipped_stage"}

        # Stage duration — we want a stock that has earned its current
        # posture, not one that flipped in this morning.
        stage_days = row.current_stage_days or 0
        if stage_days < self.t.min_stage_days:
            return {"status": "skipped_stage"}

        rs = _to_float(row.rs_mansfield_pct)
        if rs is None or rs < self.t.min_rs_mansfield_pct:
            return {"status": "skipped_rs"}

        eps_yoy = _to_float(row.eps_growth_yoy)
        if self.t.min_eps_growth_yoy_pct is not None:
            # ``None`` eps_yoy means we couldn't observe; reject for
            # conviction sleeve rather than silently include (no-silent-
            # fallback rule — we don't recommend multi-year holds on
            # unknown fundamentals).
            if eps_yoy is None or eps_yoy < self.t.min_eps_growth_yoy_pct:
                return {"status": "skipped_eps"}

        pe = _to_float(row.pe_ttm)
        if self.t.max_pe_ttm is not None and pe is not None and pe > self.t.max_pe_ttm:
            return {"status": "skipped_valuation"}

        range_pos = _to_float(row.range_pos_52w)
        if range_pos is None:
            return {"status": "skipped_range"}
        if range_pos > self.t.max_range_pos_52w:
            return {"status": "skipped_range"}
        if range_pos < self.t.min_range_pos_52w:
            return {"status": "skipped_range"}

        breakdown = {
            "stage_label": row.stage_label,
            "stage_days": stage_days,
            "rs_mansfield_pct": rs,
            "eps_growth_yoy_pct": eps_yoy,
            "revenue_growth_yoy_pct": _to_float(row.revenue_growth_yoy),
            "pe_ttm": pe,
            "peg_ttm": _to_float(row.peg_ttm),
            "range_pos_52w": range_pos,
            "generator_version": self.version,
        }

        score = self._score(row, rs=rs, eps_yoy=eps_yoy, pe=pe, range_pos=range_pos)
        breakdown["total_score"] = str(score)

        rationale = self._rationale(
            symbol, row, rs=rs, eps_yoy=eps_yoy, pe=pe, range_pos=range_pos
        )

        return {
            "status": "eligible",
            "score": score,
            "rationale": rationale,
            "breakdown": breakdown,
        }

    # ------------------------------------------------------------------
    # Scoring + rationale
    # ------------------------------------------------------------------

    def _score(
        self,
        row: MarketSnapshot,
        *,
        rs: float,
        eps_yoy: Optional[float],
        pe: Optional[float],
        range_pos: float,
    ) -> Decimal:
        """Composite 0-100 conviction score, Decimal end-to-end."""
        # Stage posture: 2A > 2B > 1B; day-count adds up to +10.
        stage_base = {"2A": 90, "2B": 80, "1B": 60}.get(row.stage_label or "", 50)
        stage_bonus = min((row.current_stage_days or 0) / 10.0, 10.0)
        stage_score = Decimal(str(min(stage_base + stage_bonus, 100.0)))

        # RS: already a percentile-ish in [-100, 100]; map to [0, 100].
        rs_score = Decimal(str(max(0.0, min(100.0, (rs + 100.0) / 2.0))))

        # EPS growth: 0 -> 50, 100%+ -> 100; capped.
        eps_component = eps_yoy if eps_yoy is not None else 0.0
        eps_score_val = max(0.0, min(100.0, 50.0 + eps_component * 0.5))
        eps_score = Decimal(str(eps_score_val))

        # Valuation: inverse of PE vs cap; null PE = 50 (neutral).
        if pe is None:
            val_score = Decimal("50")
        else:
            cap = self.t.max_pe_ttm or 60.0
            val_score_val = max(0.0, min(100.0, (1.0 - min(pe, cap) / cap) * 100.0))
            val_score = Decimal(str(val_score_val))

        # Range pos: sweet spot is 60-80% of 52w range; bell curve.
        target = 0.70
        distance = abs(range_pos - target)
        rng_score_val = max(0.0, min(100.0, 100.0 - distance * 200.0))
        rng_score = Decimal(str(rng_score_val))

        total = (
            stage_score * Decimal(str(self.t.w_stage_posture))
            + rs_score * Decimal(str(self.t.w_rs))
            + eps_score * Decimal(str(self.t.w_eps_growth))
            + val_score * Decimal(str(self.t.w_valuation))
            + rng_score * Decimal(str(self.t.w_range_pos))
        )
        return total.quantize(Decimal("0.0001"))

    def _rationale(
        self,
        symbol: str,
        row: MarketSnapshot,
        *,
        rs: float,
        eps_yoy: Optional[float],
        pe: Optional[float],
        range_pos: float,
    ) -> str:
        parts: List[str] = [
            f"{symbol} in Stage {row.stage_label}",
            f"{row.current_stage_days or 0}d in stage",
            f"RS Mansfield {rs:.1f}",
        ]
        if eps_yoy is not None:
            parts.append(f"EPS YoY {eps_yoy:+.1f}%")
        if pe is not None:
            parts.append(f"P/E {pe:.1f}")
        parts.append(f"52w range pos {range_pos * 100:.0f}%")
        return "; ".join(parts) + "."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "ConvictionCandidate",
    "ConvictionPickGenerator",
    "ConvictionThresholds",
    "DEFAULT_THRESHOLDS",
    "GENERATOR_VERSION",
    "GenerationReport",
    "utc_now",
]
