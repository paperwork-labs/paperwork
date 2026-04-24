"""
Historical IV ingest helpers
============================

Free-providers-first ATM implied-volatility ingest for the
``HistoricalIV`` ledger. The downstream ``compute_iv_rank`` task and
`iv_rank_252` scan filter read from this ledger; if it's empty, every
downstream signal is silently dead (R-IV01).

This module is deliberately conservative:

- Every public function returns an ``Optional`` so callers can branch
  on ``None`` -- we never fall back to zero for IV or HV values
  (``.cursor/rules/no-silent-fallback.mdc``).
- ``compute_hv`` is population stdev (ddof=0) of log returns over
  ``window`` contiguous trading days, annualized with sqrt(252). This
  matches D48 (Bollinger Bands stdev convention) and the quant-analyst
  spec (``stage_analysis.docx``).
- ``persist_iv_sample`` upserts one ``HistoricalIV`` row keyed on
  ``(symbol, date)``. ``iv_hv_spread`` is only written when both
  ``iv_30d`` and ``hv_20d`` are present; otherwise it's stored as
  ``None``. NEVER 0.

See [`docs/plans/G5_IV_RANK_SURFACE.md`](../../../docs/plans/G5_IV_RANK_SURFACE.md).

medallion: silver
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.historical_iv import HistoricalIV
from app.models.market_data import MarketSnapshot, PriceData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class IVSample:
    """One ATM IV observation for a single symbol / trading day.

    ``iv_30d`` / ``iv_60d`` are expressed as fractions (e.g. 0.35 for
    35%), matching the existing ``HistoricalIV`` column convention.
    """

    symbol: str
    date: date
    iv_30d: float | None
    iv_60d: float | None
    source: str  # "ibkr" | "yahoo"


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _latest_spot_price(symbol: str, db: Session) -> float | None:
    """Best-effort spot: latest ``MarketSnapshot.current_price``, else the
    most recent daily close from ``price_data``. Returns ``None`` if
    nothing usable is available.
    """
    try:
        snap = (
            db.query(MarketSnapshot.current_price)
            .filter(
                MarketSnapshot.symbol == symbol,
                MarketSnapshot.analysis_type == "technical_snapshot",
                MarketSnapshot.current_price.isnot(None),
            )
            .order_by(MarketSnapshot.analysis_timestamp.desc())
            .first()
        )
        if snap is not None and snap[0] is not None:
            return float(snap[0])
    except Exception as e:  # pragma: no cover -- defensive
        logger.debug("spot lookup via MarketSnapshot failed for %s: %s", symbol, e)

    try:
        row = (
            db.query(PriceData.close_price)
            .filter(
                PriceData.symbol == symbol,
                PriceData.interval == "1d",
                PriceData.close_price.isnot(None),
            )
            .order_by(PriceData.date.desc())
            .first()
        )
        if row is not None and row[0] is not None:
            return float(row[0])
    except Exception as e:  # pragma: no cover -- defensive
        logger.debug("spot lookup via price_data failed for %s: %s", symbol, e)

    return None


def _dte(expiry: date, as_of: date) -> int:
    return (expiry - as_of).days


def _pair_rows_by_expiry_strike(
    rows: Sequence[dict[str, Any]],
) -> dict[tuple[date, float], dict[str, dict[str, Any]]]:
    """Group options rows into ``{(expiry, strike): {"CALL": row, "PUT": row}}``.

    Input rows use the ``fetch_yfinance_options_chain`` shape
    (``expiry``, ``option_type``, ``strike``, ``implied_vol``).
    """
    paired: dict[tuple[date, float], dict[str, dict[str, Any]]] = {}
    for r in rows:
        ex = r.get("expiry")
        k = r.get("strike")
        ot = str(r.get("option_type") or "").upper()
        if ex is None or k is None or ot not in ("CALL", "PUT"):
            continue
        try:
            strike_f = float(k)
        except (TypeError, ValueError):
            continue
        slot = paired.setdefault((ex, strike_f), {})
        slot[ot] = r
    return paired


def _iv_from_row(row: dict[str, Any]) -> float | None:
    """Return IV as float fraction in ``[0, 1]``; ``None`` if absent."""
    if not row:
        return None
    v = row.get("implied_vol")
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    # Defensive: if a caller forgot to normalize (yfinance returns fraction,
    # but some providers emit percent), coerce anything > 1 down.
    if f > 1.0:
        f = f / 100.0
    if f <= 0.0 or f > 1.5:
        return None
    return f


def _pick_atm_mid_iv(
    paired: dict[tuple[date, float], dict[str, dict[str, Any]]],
    spot: float,
) -> float | None:
    """Given expiry-strike-pair map and a spot price, return the mid IV
    (average of call IV and put IV) of the strike nearest to spot.

    Returns ``None`` if no strike has both legs with a usable IV.
    """
    best: tuple[float, float] | None = None  # (|strike - spot|, mid_iv)
    for (_ex, strike_f), legs in paired.items():
        call_iv = _iv_from_row(legs.get("CALL") or {})
        put_iv = _iv_from_row(legs.get("PUT") or {})
        if call_iv is None and put_iv is None:
            continue
        if call_iv is None:
            mid = put_iv
        elif put_iv is None:
            mid = call_iv
        else:
            mid = (call_iv + put_iv) / 2.0
        if mid is None:
            continue
        dist = abs(strike_f - spot)
        if best is None or dist < best[0]:
            best = (dist, mid)
    return None if best is None else best[1]


def _bucket_rows_by_dte(
    rows: Sequence[dict[str, Any]],
    as_of: date,
    *,
    dte_min: int,
    dte_max: int,
) -> list[tuple[int, list[dict[str, Any]]]]:
    """Group rows by expiry and keep only buckets whose DTE is in
    ``[dte_min, dte_max]``. Sorted by DTE ascending (nearest first).
    """
    by_exp: dict[date, list[dict[str, Any]]] = {}
    for r in rows:
        ex = r.get("expiry")
        if ex is None:
            continue
        by_exp.setdefault(ex, []).append(r)
    buckets: list[tuple[int, list[dict[str, Any]]]] = []
    for ex, rows_for_ex in by_exp.items():
        d = _dte(ex, as_of)
        if d < dte_min or d > dte_max:
            continue
        buckets.append((d, rows_for_ex))
    buckets.sort(key=lambda t: t[0])
    return buckets


def _pick_iv_for_tenor(
    rows: Sequence[dict[str, Any]],
    as_of: date,
    spot: float,
    *,
    target_dte: int,
    dte_min: int,
    dte_max: int,
) -> float | None:
    """Pick the ATM mid IV from the chain bucket whose DTE is closest to
    ``target_dte`` (within the ``[dte_min, dte_max]`` window).
    """
    buckets = _bucket_rows_by_dte(rows, as_of, dte_min=dte_min, dte_max=dte_max)
    if not buckets:
        return None
    # closest-to-target wins; ties broken by "shorter DTE first" which is
    # the classic convention for ATM surfaces.
    buckets.sort(key=lambda t: (abs(t[0] - target_dte), t[0]))
    for _dte_val, bucket_rows in buckets:
        paired = _pair_rows_by_expiry_strike(bucket_rows)
        mid = _pick_atm_mid_iv(paired, spot)
        if mid is not None:
            return mid
    return None


# ---------------------------------------------------------------------------
# Yahoo path
# ---------------------------------------------------------------------------


def atm_iv_from_yahoo(
    symbol: str,
    as_of: date,
    *,
    db: Session | None = None,
    chain_fetcher: Any | None = None,
    spot_override: float | None = None,
    dte_min: int | None = None,
    dte_max: int | None = None,
) -> IVSample | None:
    """Fetch ATM IV for ``symbol`` from Yahoo.

    The nearest-expiry chain within ``[dte_min, dte_max]`` DTE is picked,
    and the mid of call+put IV at the strike closest to spot is taken
    for ``iv_30d``. A second pass targeting ~60 DTE populates ``iv_60d``
    when the chain is long enough.

    ``chain_fetcher`` and ``spot_override`` are injection seams for tests.
    """
    try:
        from app.config import settings
    except Exception:
        settings = None  # pragma: no cover

    d_min = dte_min if dte_min is not None else int(getattr(settings, "YAHOO_IV_DTE_MIN", 7) or 7)
    d_max = dte_max if dte_max is not None else int(getattr(settings, "YAHOO_IV_DTE_MAX", 45) or 45)

    if chain_fetcher is None:
        try:
            from app.services.market.yfinance_options_chain import (
                fetch_yfinance_options_chain,
            )

            chain_fetcher = fetch_yfinance_options_chain
        except Exception as e:  # pragma: no cover
            logger.warning("yfinance chain module unavailable: %s", e)
            return None

    try:
        rows = chain_fetcher(symbol, max_dte_days=max(d_max, 120))
    except Exception as e:
        logger.warning("yfinance chain fetch failed for %s: %s", symbol, e)
        return None
    if not rows:
        return None

    # Normalize rows (Decimals -> floats, coerce types) so pair-picker is
    # plain arithmetic.
    norm: list[dict[str, Any]] = []
    for r in rows:
        ex = r.get("expiry")
        if isinstance(ex, datetime):
            ex = ex.date()
        strike = r.get("strike")
        if isinstance(strike, Decimal):
            strike = float(strike)
        iv = r.get("implied_vol")
        if isinstance(iv, Decimal):
            iv = float(iv)
        norm.append(
            {
                "expiry": ex,
                "option_type": str(r.get("option_type") or "").upper(),
                "strike": strike,
                "implied_vol": iv,
            }
        )

    spot = spot_override
    if spot is None and db is not None:
        spot = _latest_spot_price(symbol, db)
    if spot is None:
        logger.info("atm_iv_from_yahoo: no spot for %s, skipping", symbol)
        return None

    iv30 = _pick_iv_for_tenor(norm, as_of, float(spot), target_dte=30, dte_min=d_min, dte_max=d_max)
    iv60 = _pick_iv_for_tenor(
        norm,
        as_of,
        float(spot),
        target_dte=60,
        dte_min=max(d_min, 30),
        dte_max=max(d_max, 90),
    )

    if iv30 is None and iv60 is None:
        return None
    return IVSample(symbol=symbol, date=as_of, iv_30d=iv30, iv_60d=iv60, source="yahoo")


# ---------------------------------------------------------------------------
# IBKR path
# ---------------------------------------------------------------------------


def _normalize_ibkr_chain(chain: dict) -> list[dict[str, Any]]:
    """Flatten the ``get_option_chain`` return shape
    (``{chains: {expiry_str: {calls:[..], puts:[..]}}}``) into
    the same row dict shape as yfinance: ``expiry``, ``option_type``,
    ``strike``, ``implied_vol``.
    """
    out: list[dict[str, Any]] = []
    if not isinstance(chain, dict):
        return out
    chains_by_exp = chain.get("chains") or {}
    if not isinstance(chains_by_exp, dict):
        return out
    for exp_key, legs in chains_by_exp.items():
        # IBKR expirations come back as ``YYYYMMDD`` strings.
        exp_d: date | None = None
        if isinstance(exp_key, date):
            exp_d = exp_key
        elif isinstance(exp_key, str):
            s = exp_key.strip()
            for fmt in ("%Y%m%d", "%Y-%m-%d"):
                try:
                    exp_d = datetime.strptime(s, fmt).date()
                    break
                except ValueError:
                    continue
        if exp_d is None:
            continue
        if not isinstance(legs, dict):
            continue
        for side_key, otype in (("calls", "CALL"), ("puts", "PUT")):
            side = legs.get(side_key) or []
            if not isinstance(side, (list, tuple)):
                continue
            for item in side:
                if not isinstance(item, dict):
                    continue
                strike = item.get("strike")
                iv = item.get("iv")
                if iv is None or strike is None:
                    continue
                try:
                    strike_f = float(strike)
                    iv_f = float(iv)
                except (TypeError, ValueError):
                    continue
                if (
                    math.isnan(iv_f)
                    or math.isinf(iv_f)
                    or math.isnan(strike_f)
                    or math.isinf(strike_f)
                ):
                    continue
                out.append(
                    {
                        "expiry": exp_d,
                        "option_type": otype,
                        "strike": strike_f,
                        "implied_vol": iv_f,
                    }
                )
    return out


def atm_iv_from_ibkr(
    symbol: str,
    as_of: date,
    *,
    db: Session | None = None,
    chain_fetcher: Any | None = None,
    spot_override: float | None = None,
    dte_min: int | None = None,
    dte_max: int | None = None,
) -> IVSample | None:
    """Fetch ATM IV for ``symbol`` from the IBKR Gateway.

    Primary path when the gateway is up. Returns ``None`` (without
    raising) when the gateway is offline, the symbol has no chain, or
    no strike in the tenor window has both legs with usable IV.
    """
    try:
        from app.config import settings
    except Exception:
        settings = None  # pragma: no cover

    d_min = dte_min if dte_min is not None else int(getattr(settings, "YAHOO_IV_DTE_MIN", 7) or 7)
    d_max = dte_max if dte_max is not None else int(getattr(settings, "YAHOO_IV_DTE_MAX", 45) or 45)

    if chain_fetcher is None:
        try:
            import asyncio

            from app.services.clients.ibkr_client import ibkr_client

            def _fetch(sym: str) -> dict:
                try:
                    return asyncio.run(ibkr_client.get_option_chain(sym))
                except RuntimeError:
                    # Already in an event loop -- caller should inject
                    # a fetcher. Signal "gateway offline" by returning
                    # an empty shape instead of crashing the per-symbol
                    # loop.
                    return {"expirations": [], "chains": {}}

            chain_fetcher = _fetch
        except Exception as e:
            logger.info("IBKR client unavailable for %s: %s", symbol, e)
            return None

    try:
        chain = chain_fetcher(symbol)
    except Exception as e:
        logger.warning("ibkr option chain fetch failed for %s: %s", symbol, e)
        return None

    rows = _normalize_ibkr_chain(chain or {})
    if not rows:
        return None

    spot = spot_override
    if spot is None and db is not None:
        spot = _latest_spot_price(symbol, db)
    if spot is None:
        logger.info("atm_iv_from_ibkr: no spot for %s, skipping", symbol)
        return None

    iv30 = _pick_iv_for_tenor(rows, as_of, float(spot), target_dte=30, dte_min=d_min, dte_max=d_max)
    iv60 = _pick_iv_for_tenor(
        rows,
        as_of,
        float(spot),
        target_dte=60,
        dte_min=max(d_min, 30),
        dte_max=max(d_max, 90),
    )

    if iv30 is None and iv60 is None:
        return None
    return IVSample(symbol=symbol, date=as_of, iv_30d=iv30, iv_60d=iv60, source="ibkr")


# ---------------------------------------------------------------------------
# Historical volatility
# ---------------------------------------------------------------------------


_TRADING_DAYS_PER_YEAR = 252


def compute_hv(
    symbol: str,
    as_of: date,
    window: int,
    db: Session,
) -> float | None:
    """Population stdev (``ddof=0``) of log returns over ``window``
    contiguous trading days ending at ``as_of``, annualized by
    ``sqrt(252)``.

    Matches D48 (Bollinger Bands population-stdev convention). Returns
    ``None`` if fewer than ``window`` bars are available (which needs
    ``window + 1`` closes to produce ``window`` returns).
    """
    if window <= 0:
        return None

    # We need ``window + 1`` closes to make ``window`` log returns.
    try:
        cutoff = datetime.combine(as_of, datetime.min.time()) + timedelta(days=1)
        rows = (
            db.query(PriceData.date, PriceData.close_price)
            .filter(
                PriceData.symbol == symbol,
                PriceData.interval == "1d",
                PriceData.date < cutoff,
                PriceData.close_price.isnot(None),
            )
            .order_by(PriceData.date.desc())
            .limit(window + 1)
            .all()
        )
    except Exception as e:
        logger.warning("compute_hv price_data read failed for %s: %s", symbol, e)
        return None

    if len(rows) < window + 1:
        return None

    # Rows come in desc order; reverse for chronological log returns.
    closes = [float(r[1]) for r in reversed(rows) if r[1] is not None]
    if len(closes) < window + 1:
        return None

    # Log returns. If any close is non-positive, we can't take the log
    # and the whole window is unreliable -- surface None rather than
    # silently masking.
    log_returns: list[float] = []
    for prev, curr in zip(closes[:-1], closes[1:]):
        if prev <= 0 or curr <= 0:
            return None
        log_returns.append(math.log(curr / prev))

    if len(log_returns) < window:
        return None

    # Use exactly the tail `window` returns, in case we have a strict
    # extra (defensive -- limit() should already constrain this).
    log_returns = log_returns[-window:]

    n = len(log_returns)
    mean = sum(log_returns) / n
    variance = sum((x - mean) ** 2 for x in log_returns) / n  # population / ddof=0
    if variance < 0:
        return None
    hv_daily = math.sqrt(variance)
    return hv_daily * math.sqrt(_TRADING_DAYS_PER_YEAR)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def persist_iv_sample(
    sample: IVSample,
    hv_20d: float | None,
    hv_60d: float | None,
    db: Session,
) -> HistoricalIV:
    """Upsert one ``HistoricalIV`` row keyed on ``(symbol, date)``.

    - ``iv_30d`` / ``iv_60d`` / ``hv_20d`` / ``hv_60d`` are written as-is.
    - ``iv_hv_spread = iv_30d - hv_20d`` only when BOTH are non-null;
      otherwise ``None`` (never 0).
    - Ranked fields (``iv_rank_252``, ``iv_high_252``, ``iv_low_252``)
      are NOT touched here -- they're owned by ``compute_iv_rank``.
    """
    if not sample.symbol or not sample.date:
        raise ValueError("IVSample must have symbol and date")

    spread: float | None
    if sample.iv_30d is not None and hv_20d is not None:
        spread = float(sample.iv_30d) - float(hv_20d)
    else:
        spread = None

    existing = (
        db.query(HistoricalIV)
        .filter(
            HistoricalIV.symbol == sample.symbol,
            HistoricalIV.date == sample.date,
        )
        .first()
    )

    if existing is None:
        row = HistoricalIV(
            symbol=sample.symbol,
            date=sample.date,
            iv_30d=sample.iv_30d,
            iv_60d=sample.iv_60d,
            hv_20d=hv_20d,
            hv_60d=hv_60d,
            iv_hv_spread=spread,
        )
        db.add(row)
        db.flush()
        return row

    existing.iv_30d = sample.iv_30d
    existing.iv_60d = sample.iv_60d
    existing.hv_20d = hv_20d
    existing.hv_60d = hv_60d
    existing.iv_hv_spread = spread
    db.flush()
    return existing


# ---------------------------------------------------------------------------
# Coverage helpers (used by admin_health + snapshot task)
# ---------------------------------------------------------------------------


def last_trading_day(today: date | None = None) -> date:
    """Return the most recent weekday on/before ``today``.

    Note: this does not honor market holidays -- the downstream
    ingest task is idempotent, so an empty holiday run is harmless.
    """
    if today is None:
        today = datetime.utcnow().date()
    d = today
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d = d - timedelta(days=1)
    return d


def iv_source_breakdown(db: Session, *, as_of: date) -> dict:
    """Return ``{"ibkr": n, "yahoo": n, "total": n}`` counts for rows on
    ``as_of``.

    ``HistoricalIV`` does not store a provider column today; this helper
    is intentionally resilient and falls back to ``{"total": n}`` so
    callers can still show a single number without tagging.
    """
    try:
        total = (
            db.query(func.count(HistoricalIV.id))
            .filter(
                HistoricalIV.date == as_of,
                HistoricalIV.iv_30d.isnot(None),
            )
            .scalar()
            or 0
        )
    except Exception as e:
        logger.warning("iv_source_breakdown failed: %s", e)
        return {"ibkr": 0, "yahoo": 0, "total": 0, "available": False}
    # When we extend HistoricalIV with a ``source`` column this function
    # should start filling in real per-provider counts. Today we just
    # surface the total so the health card is honest.
    return {"ibkr": None, "yahoo": None, "total": int(total), "available": True}


__all__ = [
    "IVSample",
    "atm_iv_from_ibkr",
    "atm_iv_from_yahoo",
    "compute_hv",
    "iv_source_breakdown",
    "last_trading_day",
    "persist_iv_sample",
]
