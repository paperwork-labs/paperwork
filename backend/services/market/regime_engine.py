"""Market Regime Engine (Stage Analysis spec Section 10)

The Regime Engine is the outermost gate for all downstream modules.
6 daily inputs → individual scores (1–5) → composite → R1–R5.

Regime is computed BEFORE all other pipeline steps (Step 0 of nightly pipeline).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Union

import numpy as np
from sqlalchemy.orm import Session

from backend.models.market_data import MarketRegime

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


# ── Scoring functions (1–5 per Stage Analysis spec thresholds) ──

def score_vix(vix: float) -> float:
    """VIX spot → 1 (low fear) to 5 (extreme fear)."""
    if vix is None or (isinstance(vix, float) and math.isnan(vix)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_vix",
            vix,
        )
        return 3.0
    if vix <= 0:
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_vix",
            vix,
        )
        return 3.0
    if vix <= 13:
        return 1.0
    elif vix <= 16:
        return 2.0
    elif vix <= 22:
        return 3.0
    elif vix <= 30:
        return 4.0
    else:
        return 5.0


def score_vix3m_vix(ratio: float) -> float:
    """VIX3M/VIX ratio → 1 (contango, calm) to 5 (backwardation, panic).

    Ratio > 1.0 = contango (normal); ratio < 1.0 = backwardation (stress).
    """
    if ratio is None or (isinstance(ratio, float) and math.isnan(ratio)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_vix3m_vix",
            ratio,
        )
        return 3.0
    if ratio >= 1.10:
        return 1.0
    elif ratio >= 1.03:
        return 2.0
    elif ratio >= 0.97:
        return 3.0
    elif ratio >= 0.90:
        return 4.0
    else:
        return 5.0


def score_vvix_vix(ratio: float) -> float:
    """VVIX/VIX ratio → 1 (stable vol) to 5 (unstable vol).

    High ratio = vol-of-vol is outsized relative to VIX, uncertainty about direction.
    """
    if ratio is None or (isinstance(ratio, float) and math.isnan(ratio)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_vvix_vix",
            ratio,
        )
        return 3.0
    if ratio <= 4.0:
        return 1.0
    elif ratio <= 5.5:
        return 2.0
    elif ratio <= 7.0:
        return 3.0
    elif ratio <= 9.0:
        return 4.0
    else:
        return 5.0


def score_nh_nl(nh_nl: Optional[Union[int, float]]) -> float:
    """New Highs minus New Lows (S&P 500) → 1 (bullish) to 5 (bearish)."""
    if nh_nl is None or (isinstance(nh_nl, float) and math.isnan(nh_nl)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_nh_nl",
            nh_nl,
        )
        return 3.0
    if nh_nl >= 100:
        return 1.0
    elif nh_nl >= 30:
        return 2.0
    elif nh_nl >= -30:
        return 3.0
    elif nh_nl >= -100:
        return 4.0
    else:
        return 5.0


def score_pct_above_200d(pct: float) -> float:
    """% of S&P 500 stocks above 200D MA → 1 (healthy) to 5 (broken)."""
    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_pct_above_200d",
            pct,
        )
        return 3.0
    if pct >= 70:
        return 1.0
    elif pct >= 55:
        return 2.0
    elif pct >= 40:
        return 3.0
    elif pct >= 25:
        return 4.0
    else:
        return 5.0


def score_pct_above_50d(pct: float) -> float:
    """% of S&P 500 stocks above 50D MA → 1 (healthy) to 5 (broken)."""
    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        logger.warning(
            "Regime scoring: %s received invalid input %s, using neutral score",
            "score_pct_above_50d",
            pct,
        )
        return 3.0
    if pct >= 75:
        return 1.0
    elif pct >= 60:
        return 2.0
    elif pct >= 40:
        return 3.0
    elif pct >= 25:
        return 4.0
    else:
        return 5.0


def compute_composite(scores: list[float]) -> float:
    """Average of 6 scores, rounded to nearest 0.5 (half-up, not round-half-to-even)."""
    avg = float(np.mean(scores))
    return math.floor(avg * 2 + 0.5) / 2


def composite_to_regime(composite: float) -> str:
    """Map composite score to regime state."""
    if composite <= 1.75:
        return REGIME_R1
    elif composite <= 2.50:
        return REGIME_R2
    elif composite <= 3.50:
        return REGIME_R3
    elif composite <= 4.50:
        return REGIME_R4
    else:
        return REGIME_R5


# ── Regime portfolio rules ──

REGIME_RULES = {
    REGIME_R1: {"cash_floor": 5.0, "max_equity": 100.0, "multiplier": 1.0},
    REGIME_R2: {"cash_floor": 10.0, "max_equity": 90.0, "multiplier": 0.75},
    REGIME_R3: {"cash_floor": 25.0, "max_equity": 75.0, "multiplier": 0.5},
    REGIME_R4: {"cash_floor": 40.0, "max_equity": 60.0, "multiplier": 0.4},
    REGIME_R5: {"cash_floor": 60.0, "max_equity": 40.0, "multiplier": 0.25},
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
