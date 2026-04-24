"""
Read-only options chain from Yahoo Finance via the yfinance library
(same stack as YFinanceProvider; no new external dependency).

medallion: silver
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


def _d(val: Any) -> Decimal | None:
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    try:
        return Decimal(str(val))
    except Exception:
        return None


def _i(val: Any) -> int | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(f)
    except Exception:
        return None


def _parse_iv(v: Any) -> Decimal | None:
    d = _d(v)
    if d is None or d < 0:
        return None
    if d > Decimal("1"):
        d = d / Decimal(100)
    if d > Decimal("1"):
        return None
    return d


def fetch_yfinance_options_chain(
    symbol: str,
    *,
    max_dte_days: int = 120,
    expiries: Sequence[date] | None = None,
) -> list[dict[str, Any]]:
    """Return flat option contract dicts (CALL/PUT) for the symbol from Yahoo.

    Each row: expiry (date), option_type, strike, bid, ask, open_interest,
    volume, implied_vol (0-1), optional greeks, symbol (underlying).
    """
    try:
        import yfinance as yf
    except ImportError as e:
        logger.warning("yfinance not installed: %s", e)
        return []

    sym = (symbol or "").upper().strip()
    if not sym:
        return []

    t = yf.Ticker(sym)
    try:
        opt_dates = list(t.options)
    except Exception as e:
        logger.warning("yfinance options list failed for %s: %s", sym, e)
        return []

    if not opt_dates:
        return []

    today = date.today()
    out: list[dict[str, Any]] = []

    want = None
    if expiries is not None:
        want = {d if isinstance(d, date) else date.fromisoformat(str(d)) for d in expiries}

    for exp_s in opt_dates:
        try:
            exp_d = datetime.strptime(str(exp_s), "%Y-%m-%d").date()
        except Exception:
            continue

        dte = (exp_d - today).days
        if dte > max_dte_days or dte < 0:
            if want is None or exp_d not in want:
                continue
        if want is not None and exp_d not in want:
            continue

        try:
            ch = t.option_chain(str(exp_s))
        except Exception as e:
            logger.warning("yfinance option_chain %s %s: %s", sym, exp_s, e)
            continue

        for label, otype in (("CALL", "CALL"), ("PUT", "PUT")):
            frame = ch.calls if label == "CALL" else ch.puts
            if frame is None or frame.empty:
                continue
            for _, row in frame.iterrows():
                strike = _d(row.get("strike"))
                if strike is None:
                    continue
                out.append(
                    {
                        "symbol": sym,
                        "expiry": exp_d,
                        "option_type": otype,
                        "strike": strike,
                        "bid": _d(row.get("bid")),
                        "ask": _d(row.get("ask")),
                        "open_interest": _i(row.get("openInterest") or row.get("open interest")),
                        "volume": _i(row.get("volume")),
                        "implied_vol": _parse_iv(
                            row.get("impliedVolatility") or row.get("impliedVol")
                        ),
                        "delta": _d(row.get("delta")),
                        "gamma": _d(row.get("gamma")),
                        "theta": _d(row.get("theta")),
                        "vega": _d(row.get("vega")),
                    }
                )
    if not out:
        logger.info("yfinance: empty options chain for %s", sym)
    return out
