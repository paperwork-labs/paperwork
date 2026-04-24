"""Market Regime Engine (Stage Analysis spec Section 10)

The Regime Engine is the outermost gate for all downstream modules.
6 daily inputs → individual scores (1–5) → composite → R1–R5.

Regime is computed BEFORE all other pipeline steps (Step 0 of nightly pipeline).

Medallion layer: silver. See docs/ARCHITECTURE.md and D127.

medallion: silver
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Union
from sqlalchemy.orm import Session

from app.models.market_data import MarketRegime

logger = logging.getLogger(__name__)


# ── Regime states ──

REGIME_R1 = "R1"  # Bull
REGIME_R2 = "R2"  # Bull Extended
REGIME_R3 = "R3"  # Chop
REGIME_R4 = "R4"  # Bear Rally
REGIME_R5 = "R5"  # Bear


@dataclass
class RegimeInputs:
    """Raw daily inputs for the Regime Engine."""
    vix_spot: float
    vix3m_vix_ratio: float
    vvix_vix_ratio: float
    nh_nl: int
    pct_above_200d: float
    pct_above_50d: float


@dataclass
class RegimeResult:
    """Full regime computation output."""
    as_of_date: date
    inputs: RegimeInputs
    score_vix: float
    score_vix3m_vix: float
    score_vvix_vix: float
    score_nh_nl: float
    score_above_200d: float
    score_above_50d: float
    composite_score: float
    regime_state: str
    cash_floor_pct: float
    max_equity_exposure_pct: float
    regime_multiplier: float
    weights_used: list[float]


# ── Scoring functions (1–5 per non-overlapping boundaries) ──
# Boundary rule: on-boundary = more bearish score.

def _safe_input(func_name: str, value, *, allow_negative: bool = False) -> Optional[float]:
    """Return None if value is invalid (None/NaN/non-positive), else float."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            func_name, value,
        )
        return None
    val = float(value)
    if not allow_negative and val <= 0:
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            func_name, value,
        )
        return None
    return val


def score_vix(vix: float) -> float:
    """VIX spot → 1 (low fear) to 5 (extreme fear).

    Boundaries: <17 / 17–20 / 20–27 / 27–35 / ≥35
    """
    val = _safe_input("score_vix", vix)
    if val is None:
        return 3.0
    if val < 17:
        return 1.0
    if val < 20:
        return 2.0
    if val < 27:
        return 3.0
    if val < 35:
        return 4.0
    return 5.0


def score_vix3m_vix(ratio: float) -> float:
    """VIX3M/VIX ratio → 1 (contango, calm) to 5 (backwardation, panic).

    Boundaries: >1.10 / (1.05,1.10] / (1.00,1.05] / (0.90,1.00] / ≤0.90
    """
    if ratio is None or (isinstance(ratio, float) and math.isnan(ratio)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_vix3m_vix", ratio,
        )
        return 3.0
    if ratio > 1.10:
        return 1.0
    if ratio > 1.05:
        return 2.0
    if ratio > 1.00:
        return 3.0
    if ratio > 0.90:
        return 4.0
    return 5.0


def score_vvix_vix(ratio: float) -> float:
    """VVIX/VIX ratio → 1 (stable vol) to 5 (unstable vol).

    Non-monotonic scoring: both extremes (< 2.5 or ≥ 7.0) are bearish.
    Boundaries: ≥7.0→5 / (5.5,7.0)→1 / (4.5,5.5]→2 / (3.5,4.5]→3 / (2.5,3.5]→4 / ≤2.5→5
    """
    if ratio is None or (isinstance(ratio, float) and math.isnan(ratio)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_vvix_vix", ratio,
        )
        return 3.0
    if ratio >= 7.0:
        return 5.0
    if ratio <= 2.5:
        return 5.0
    if ratio > 5.5:
        return 1.0
    if ratio > 4.5:
        return 2.0
    if ratio > 3.5:
        return 3.0
    return 4.0


def score_nh_nl(nh_nl: Optional[Union[int, float]]) -> float:
    """New Highs minus New Lows (S&P 500) → 1 (bullish) to 5 (bearish).

    Boundaries: >100 / (20,100] / (-50,20] / (-150,-50] / ≤-150
    """
    if nh_nl is None or (isinstance(nh_nl, float) and math.isnan(nh_nl)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_nh_nl", nh_nl,
        )
        return 3.0
    if nh_nl > 100:
        return 1.0
    if nh_nl > 20:
        return 2.0
    if nh_nl > -50:
        return 3.0
    if nh_nl > -150:
        return 4.0
    return 5.0


def score_pct_above_200d(pct: float) -> float:
    """% of S&P 500 stocks above 200D MA → 1 (healthy) to 5 (broken).

    Boundaries: >65 / (55,65] / (45,55] / (30,45] / ≤30
    """
    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_pct_above_200d", pct,
        )
        return 3.0
    if pct > 65:
        return 1.0
    if pct > 55:
        return 2.0
    if pct > 45:
        return 3.0
    if pct > 30:
        return 4.0
    return 5.0


def score_pct_above_50d(pct: float) -> float:
    """% of S&P 500 stocks above 50D MA → 1 (healthy) to 5 (broken).

    Boundaries: >65 / (50,65] / (35,50] / (15,35] / ≤15
    """
    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_pct_above_50d", pct,
        )
        return 3.0
    if pct > 65:
        return 1.0
    if pct > 50:
        return 2.0
    if pct > 35:
        return 3.0
    if pct > 15:
        return 4.0
    return 5.0


# ── Weighted composite ──

WEIGHTS = [1.00, 1.25, 0.75, 1.00, 1.00, 0.75]
WEIGHT_SUM = 5.75


def compute_composite(scores: list[float]) -> float:
    """Weighted average of 6 scores, rounded to nearest 0.25.

    Formula: sum(score_i * weight_i) / 5.75, then snap to 0.25 grid.
    Weights: VIX=1.0, VIX3M/VIX=1.25, VVIX/VIX=0.75, NH-NL=1.0, %200D=1.0, %50D=0.75
    """
    weighted = sum(s * w for s, w in zip(scores, WEIGHTS))
    avg = weighted / WEIGHT_SUM
    return round(avg * 4) / 4


def composite_to_regime(composite: float) -> str:
    """Map composite score to regime state.

    On-boundary values (2.50, 3.50, 4.50) are assigned to the more
    defensive (higher-numbered) regime.
    """
    if composite < 2.0:
        return REGIME_R1
    if composite < 2.5:
        return REGIME_R2
    if composite < 3.5:
        return REGIME_R3
    if composite < 4.5:
        return REGIME_R4
    return REGIME_R5


# ── Regime portfolio rules ──

REGIME_RULES = {
    REGIME_R1: {"cash_floor": 5.0, "max_equity": 90.0, "multiplier": 1.0},
    REGIME_R2: {"cash_floor": 15.0, "max_equity": 75.0, "multiplier": 0.75},
    REGIME_R3: {"cash_floor": 35.0, "max_equity": 50.0, "multiplier": 0.5},
    REGIME_R4: {"cash_floor": 50.0, "max_equity": 30.0, "multiplier": 0.4},
    REGIME_R5: {"cash_floor": 70.0, "max_equity": 10.0, "multiplier": 0.0},
}


def compute_regime(inputs: RegimeInputs, as_of: date) -> RegimeResult:
    """Compute the full regime from 6 daily inputs."""
    s_vix = score_vix(inputs.vix_spot)
    s_vix3m = score_vix3m_vix(inputs.vix3m_vix_ratio)
    s_vvix = score_vvix_vix(inputs.vvix_vix_ratio)
    s_nhnl = score_nh_nl(inputs.nh_nl)
    s_200d = score_pct_above_200d(inputs.pct_above_200d)
    s_50d = score_pct_above_50d(inputs.pct_above_50d)

    scores = [s_vix, s_vix3m, s_vvix, s_nhnl, s_200d, s_50d]
    composite = compute_composite(scores)
    regime = composite_to_regime(composite)
    rules = REGIME_RULES[regime]

    return RegimeResult(
        as_of_date=as_of,
        inputs=inputs,
        score_vix=s_vix,
        score_vix3m_vix=s_vix3m,
        score_vvix_vix=s_vvix,
        score_nh_nl=s_nhnl,
        score_above_200d=s_200d,
        score_above_50d=s_50d,
        composite_score=composite,
        regime_state=regime,
        cash_floor_pct=rules["cash_floor"],
        max_equity_exposure_pct=rules["max_equity"],
        regime_multiplier=rules["multiplier"],
        weights_used=list(WEIGHTS),
    )


def persist_regime(db: Session, result: RegimeResult) -> MarketRegime:
    """Upsert a MarketRegime row for the given date.

    Caller owns the transaction — this function does not commit.
    """
    from sqlalchemy import select

    dt = datetime.combine(result.as_of_date, datetime.min.time())
    stmt = select(MarketRegime).where(MarketRegime.as_of_date == dt)
    row = db.execute(stmt).scalar_one_or_none()

    if row is None:
        row = MarketRegime(as_of_date=dt)
        db.add(row)

    row.vix_spot = result.inputs.vix_spot
    row.vix3m_vix_ratio = result.inputs.vix3m_vix_ratio
    row.vvix_vix_ratio = result.inputs.vvix_vix_ratio
    row.nh_nl = result.inputs.nh_nl
    row.pct_above_200d = result.inputs.pct_above_200d
    row.pct_above_50d = result.inputs.pct_above_50d
    row.score_vix = result.score_vix
    row.score_vix3m_vix = result.score_vix3m_vix
    row.score_vvix_vix = result.score_vvix_vix
    row.score_nh_nl = result.score_nh_nl
    row.score_above_200d = result.score_above_200d
    row.score_above_50d = result.score_above_50d
    row.composite_score = result.composite_score
    row.regime_state = result.regime_state
    row.cash_floor_pct = result.cash_floor_pct
    row.max_equity_exposure_pct = result.max_equity_exposure_pct
    row.regime_multiplier = result.regime_multiplier
    row.weights_used = result.weights_used

    db.flush()
    logger.info(
        "Regime %s: composite=%.1f, state=%s (VIX=%.1f, NH-NL=%d, %%>200d=%.0f, %%>50d=%.0f)",
        result.as_of_date,
        result.composite_score,
        result.regime_state,
        result.inputs.vix_spot,
        result.inputs.nh_nl,
        result.inputs.pct_above_200d,
        result.inputs.pct_above_50d,
    )
    return row


def get_current_regime(db: Session) -> Optional[MarketRegime]:
    """Get the most recent regime row."""
    from sqlalchemy import select

    stmt = select(MarketRegime).order_by(MarketRegime.as_of_date.desc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def get_current_and_previous_regime(
    db: Session,
) -> tuple[Optional[MarketRegime], Optional[MarketRegime]]:
    """Get current and previous regime rows for transition detection.
    
    Returns:
        Tuple of (current_regime, previous_regime). Either may be None.
    """
    from sqlalchemy import select

    current = get_current_regime(db)
    if not current:
        return None, None
    
    stmt = (
        select(MarketRegime)
        .where(MarketRegime.as_of_date < current.as_of_date)
        .order_by(MarketRegime.as_of_date.desc())
        .limit(1)
    )
    previous = db.execute(stmt).scalar_one_or_none()
    return current, previous


def get_regime_for_date(db: Session, as_of: date) -> Optional[MarketRegime]:
    """Get regime for a specific date."""
    from sqlalchemy import select

    dt = datetime.combine(as_of, datetime.min.time())
    stmt = select(MarketRegime).where(MarketRegime.as_of_date == dt)
    return db.execute(stmt).scalar_one_or_none()
