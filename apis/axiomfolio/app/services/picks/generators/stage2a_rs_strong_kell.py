"""Stage 2A/2B + RS-strong (quintile) candidate generator — Kell / Weinstein sweet spot.

This is an additive variant alongside :class:`Stage2ARsStrongGenerator` in
``stage2a_rs_strong.py`` (RS > 70 + extension filter). That legacy generator
is unchanged; this module encodes the SMA150-anchored filter stack requested
for Stage 2 advance + leadership + volume + proximity to 52w highs.

Gated by ``settings.ENABLE_STAGE2A_GENERATOR`` (default off).

medallion: gold
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.picks import PickAction
from app.services.picks.candidate_generator import (
    CandidateGenerator,
    GeneratedCandidate,
)

_MAX_ROWS = 50

# Five explainable dimensions; each passes at full weight when filters pass.
_DIM_WEIGHT = Decimal("20")

# Early Stage 2 substages (SMA150 anchor). Matches labels from
# :func:`app.services.market.stage_classifier.classify_stage_for_timeframe`.
_EARLY_STAGE_2_SUBSTAGES: tuple[str, ...] = ("2A", "2B")

_STAGES_SQL = ", ".join(f"'{s}'" for s in _EARLY_STAGE_2_SUBSTAGES)

_SELECT_SQL = text(
    f"""
WITH latest AS (
  SELECT MAX(id) AS id
  FROM market_snapshot
  WHERE analysis_type = 'technical_snapshot'
    AND is_valid IS TRUE
  GROUP BY symbol
),
ranked AS (
  SELECT
    ms.symbol,
    ms.stage_label,
    ms.rs_mansfield_pct,
    ms.current_price,
    ms.sma_150,
    ms.sma150_slope,
    ms.vol_ratio,
    ms.high_52w,
    CASE
      WHEN COUNT(*) OVER () <= 1 THEN 1.0
      ELSE PERCENT_RANK() OVER (
        ORDER BY ms.rs_mansfield_pct ASC NULLS LAST
      )
    END AS rs_mansfield_rank_fraction
  FROM market_snapshot AS ms
  INNER JOIN latest ON ms.id = latest.id
  WHERE ms.rs_mansfield_pct IS NOT NULL
    AND ms.rs_mansfield_pct >= 0
    AND ms.stage_label IN ({_STAGES_SQL})
)
SELECT
  symbol,
  stage_label,
  rs_mansfield_pct,
  rs_mansfield_rank_fraction,
  current_price,
  sma_150,
  sma150_slope,
  vol_ratio,
  high_52w,
  ((high_52w - current_price) / high_52w * 100.0) AS distance_from_52w_high_pct
FROM ranked
WHERE stage_label IN ({_STAGES_SQL})
  AND rs_mansfield_pct IS NOT NULL
  AND rs_mansfield_pct >= 0
  AND rs_mansfield_rank_fraction >= 0.8
  AND current_price IS NOT NULL
  AND sma_150 IS NOT NULL
  AND current_price >= sma_150
  AND sma150_slope IS NOT NULL
  AND sma150_slope >= 0
  AND vol_ratio IS NOT NULL
  AND vol_ratio >= 1.2
  AND high_52w IS NOT NULL
  AND high_52w > 0
  AND ((high_52w - current_price) / high_52w * 100.0) <= 15
ORDER BY rs_mansfield_pct DESC NULLS LAST
LIMIT :lim
"""
)


class Stage2ARsStrongKellGenerator(CandidateGenerator):
    """Stage 2A/2B + RS quintile variant (SMA150 anchor). Sibling to ``Stage2ARsStrongGenerator``."""

    name = "stage2a_rs_strong_kell"
    version = "v1"

    def generate(self, db: Session) -> Sequence[GeneratedCandidate]:
        if not settings.ENABLE_STAGE2A_GENERATOR:
            return []

        result = db.execute(_SELECT_SQL, {"lim": _MAX_ROWS})
        rows: List[Mapping[str, Any]] = list(result.mappings().all())

        out: List[GeneratedCandidate] = []
        for r in rows:
            cand = self._row_to_candidate(r)
            if cand is not None:
                out.append(cand)
        return out

    def _row_to_candidate(self, r: Mapping[str, Any]) -> Optional[GeneratedCandidate]:
        symbol = (r.get("symbol") or "").strip().upper()
        if not symbol:
            return None

        rs = r.get("rs_mansfield_pct")
        rank_frac = r.get("rs_mansfield_rank_fraction")
        price = r.get("current_price")
        sma150 = r.get("sma_150")
        slope = r.get("sma150_slope")
        vol_r = r.get("vol_ratio")
        dist_52 = r.get("distance_from_52w_high_pct")
        stage = r.get("stage_label")

        breakdown: Dict[str, Decimal] = {
            "stage_substage": _DIM_WEIGHT,
            "rs_mansfield_and_rank": _DIM_WEIGHT,
            "sma150_anchor": _DIM_WEIGHT,
            "volume_ratio_20d": _DIM_WEIGHT,
            "distance_from_52w_high_pct": _DIM_WEIGHT,
        }
        total = sum(breakdown.values(), Decimal("0"))

        rs_rank_pct = (
            Decimal(str(float(rank_frac) * 100.0)).quantize(Decimal("0.0001"))
            if rank_frac is not None
            else None
        )

        rationale_parts = [
            f"{symbol} Stage {stage}",
            f"RS Mansfield {float(rs):.2f}" if rs is not None else "RS Mansfield n/a",
        ]
        if rs_rank_pct is not None:
            rationale_parts.append(f"RS universe rank {float(rs_rank_pct):.1f}pct")
        rationale_parts.append("SMA150 anchor + slope ≥ 0")
        rationale_parts.append(f"vol×20d {float(vol_r):.2f}" if vol_r is not None else "")
        rationale_parts.append(
            f"{float(dist_52):.1f}% below 52w high" if dist_52 is not None else ""
        )
        rationale = "; ".join(p for p in rationale_parts if p) + "."

        signals: Dict[str, Any] = {
            "stage_label": stage,
            "rs_mansfield_pct": float(rs) if rs is not None else None,
            "rs_mansfield_rank_pct": float(rs_rank_pct) if rs_rank_pct is not None else None,
            "current_price": float(price) if price is not None else None,
            "sma_150": float(sma150) if sma150 is not None else None,
            "sma150_slope": float(slope) if slope is not None else None,
            "vol_ratio": float(vol_r) if vol_r is not None else None,
            "distance_from_52w_high_pct": float(dist_52) if dist_52 is not None else None,
            "score_breakdown": {k: str(v) for k, v in breakdown.items()},
        }

        return GeneratedCandidate(
            symbol=symbol,
            action_suggestion=PickAction.BUY,
            score=total.quantize(Decimal("0.0001")),
            rationale_summary=rationale,
            signals=signals,
        )
