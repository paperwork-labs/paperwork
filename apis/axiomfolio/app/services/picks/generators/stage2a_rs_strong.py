"""Stage 2A + Strong RS Mansfield candidate generator.

Thesis (compressed)
-------------------
Per Stage Analysis (Weinstein refined per ``Stage_Analysis.docx``):

* Stage 2A is the early advance phase — the highest-probability long
  entry window in the cycle.
* Mansfield Relative Strength > 0 means the stock is outperforming the
  benchmark; > 70 (percentile-ranked at compute time) is the leadership
  band that historically precedes the strongest legs.
* ATR distance from SMA21 < 5 keeps us out of extended chases (per the
  "do not chase" rule in the swing-trader persona).
* Volume confirmation (52-week range position > 60%) filters thin
  setups.

Read pattern
------------
This generator is **read-only** against the latest ``MarketSnapshot``
rows for the technical universe. It never opens a session, never calls
providers, and never writes — it returns ``GeneratedCandidate`` items
that the orchestrator persists.

Score
-----
``score = rs_mansfield_pct + (10 - min(ext_pct, 10))`` (Decimal). RS
contributes the dominant signal; the extension penalty docks chasers.
The validator queue ranks by score within this generator only, so the
absolute scale does not need to be cross-comparable with other
generators.

medallion: gold
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, load_only

from app.models.market_data import MarketSnapshot
from app.models.picks import PickAction
from app.services.picks.candidate_generator import (
    CandidateGenerator,
    GeneratedCandidate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunables (frozen at this generator version; bump version on change)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage2AThresholds:
    min_rs_mansfield_pct: float = 70.0
    max_ext_pct: float = 5.0
    min_range_pos_52w: float = 0.60
    eligible_stages: tuple[str, ...] = ("2A", "2B")
    require_action_label_buy: bool = False
    max_results: int = 50


_DEFAULT_THRESHOLDS = Stage2AThresholds()


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class Stage2ARsStrongGenerator(CandidateGenerator):
    """Stage 2A/2B + RS Mansfield > 70 + not extended."""

    name = "stage2a_rs_strong"
    version = "v1"

    def __init__(self, thresholds: Stage2AThresholds | None = None) -> None:
        self.t = thresholds or _DEFAULT_THRESHOLDS

    def generate(self, db: Session) -> Sequence[GeneratedCandidate]:
        rows = self._latest_snapshots(db)
        out: list[GeneratedCandidate] = []
        for r in rows:
            cand = self._evaluate(r)
            if cand is not None:
                out.append(cand)
            if len(out) >= self.t.max_results:
                break
        return out

    # ------------------------------------------------------------------
    # Read latest snapshot per symbol
    # ------------------------------------------------------------------

    def _latest_snapshots(self, db: Session) -> list[MarketSnapshot]:
        """Latest valid technical snapshot per symbol that already meets
        the cheap stage filter. Heavier predicates run in Python so the
        rejection path is auditable in logs.
        """
        latest_ids = (
            db.query(func.max(MarketSnapshot.id).label("id"))
            .filter(
                MarketSnapshot.analysis_type == "technical_snapshot",
                MarketSnapshot.is_valid.is_(True),
                MarketSnapshot.stage_label.in_(self.t.eligible_stages),
                MarketSnapshot.rs_mansfield_pct >= self.t.min_rs_mansfield_pct,
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
                    MarketSnapshot.rs_mansfield_pct,
                    MarketSnapshot.range_pos_52w,
                    MarketSnapshot.ext_pct,
                    MarketSnapshot.action_label,
                    MarketSnapshot.current_price,
                    MarketSnapshot.atr_14,
                    MarketSnapshot.sma_21,
                    MarketSnapshot.sma_150,
                )
            )
            .filter(MarketSnapshot.id.in_(latest_ids.select()))
            .order_by(MarketSnapshot.rs_mansfield_pct.desc().nullslast())
            .all()
        )
        return rows

    # ------------------------------------------------------------------
    # Per-row evaluation
    # ------------------------------------------------------------------

    def _evaluate(self, row: MarketSnapshot) -> GeneratedCandidate | None:
        symbol = (row.symbol or "").upper()
        if not symbol:
            return None

        rs = _to_float(row.rs_mansfield_pct)
        ext = _to_float(row.ext_pct)
        range_pos = _to_float(row.range_pos_52w)

        if rs is None or rs < self.t.min_rs_mansfield_pct:
            return None
        if ext is not None and ext > self.t.max_ext_pct:
            return None
        if range_pos is not None and range_pos < self.t.min_range_pos_52w:
            return None
        if self.t.require_action_label_buy and (row.action_label or "").upper() != "BUY":
            return None

        score = self._score(rs=rs, ext=ext)
        rationale = self._rationale(symbol, row, rs=rs, ext=ext, range_pos=range_pos)
        signals = {
            "stage_label": row.stage_label,
            "rs_mansfield_pct": rs,
            "ext_pct": ext,
            "range_pos_52w": range_pos,
            "action_label": row.action_label,
            "current_price": _to_float(row.current_price),
            "sma_150": _to_float(row.sma_150),
            "atr_14": _to_float(row.atr_14),
        }

        return GeneratedCandidate(
            symbol=symbol,
            action_suggestion=PickAction.BUY,
            score=score,
            rationale_summary=rationale,
            signals=signals,
        )

    # ------------------------------------------------------------------
    # Scoring + rationale
    # ------------------------------------------------------------------

    def _score(self, *, rs: float, ext: float | None) -> Decimal:
        # Decimal arithmetic end-to-end so the persisted score does not
        # round-trip through binary float.
        ext_for_penalty = Decimal(str(ext)) if (ext is not None and ext > 0) else Decimal("0")
        penalty = Decimal("10") - min(ext_for_penalty, Decimal("10"))
        rs_d = Decimal(str(rs))
        return (rs_d + penalty).quantize(Decimal("0.0001"))

    def _rationale(
        self,
        symbol: str,
        row: MarketSnapshot,
        *,
        rs: float,
        ext: float | None,
        range_pos: float | None,
    ) -> str:
        parts: list[str] = [
            f"{symbol} in Stage {row.stage_label}",
            f"RS Mansfield {rs:.1f}",
        ]
        if ext is not None:
            parts.append(f"ext {ext:.1f}% from SMA21")
        if range_pos is not None:
            parts.append(f"52w range pos {range_pos * 100:.0f}%")
        if row.action_label:
            parts.append(f"action label {row.action_label}")
        return "; ".join(parts) + "."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
