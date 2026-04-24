"""
Public chart share API — signed tokens, OG PNG, and anonymous OHLCV for `/share/c/:token`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

import jwt
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.config import settings
from app.services.market.market_data_service import provider_router
from app.services.share.chart_og_image import render_chart_og_png
from app.services.share.chart_share_token import create_chart_share_token, decode_chart_share_token

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_PERIODS: Set[str] = {
    "1mo",
    "3mo",
    "6mo",
    "1y",
    "2y",
    "3y",
    "5y",
    "ytd",
    "max",
}
_VALID_INDICATOR_KEYS: Set[str] = {
    "trendLines",
    "gaps",
    "tdSequential",
    "emas",
    "stage",
    "supportResistance",
}


def _history_data_source(raw: Optional[str]) -> str:
    if raw == "redis_cache":
        return "redis_cache"
    if raw == "db":
        return "db_fallback"
    if raw == "fmp":
        return "provider_fmp"
    if raw == "yfinance":
        return "provider_yfinance"
    if raw == "twelvedata":
        return "provider_twelvedata"
    if raw:
        return f"provider_{raw}"
    return "unknown"


def _public_frontend_base() -> str:
    raw = (settings.FRONTEND_ORIGIN or "").strip()
    if raw:
        return raw.rstrip("/")
    cors = (settings.CORS_ORIGINS or "").strip()
    if cors:
        first = cors.split(",")[0].strip()
        if first:
            return first.rstrip("/")
    return "http://127.0.0.1:5173"


def _dataframe_to_bars(df: Optional[pd.DataFrame]) -> List[dict[str, Any]]:
    if df is None or df.empty:
        return []
    try:
        df_out = df.iloc[::-1].copy()
    except Exception:
        df_out = df
    cols = {c.lower(): c for c in df_out.columns}

    def pick(col_name: str) -> str:
        for key in cols:
            if key.startswith(col_name):
                return cols[key]
        return col_name

    o, h, l_, c, v = pick("open"), pick("high"), pick("low"), pick("close"), pick("volume")
    out: List[dict[str, Any]] = []
    for ts, row in df_out.iterrows():
        out.append(
            {
                "time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "open": float(row.get(o, None) or row.get("open_price", 0) or 0),
                "high": float(row.get(h, None) or row.get("high_price", 0) or 0),
                "low": float(row.get(l_, None) or row.get("low_price", 0) or 0),
                "close": float(row.get(c, None) or row.get("close_price", 0) or 0),
                "volume": float(row.get(v, 0) or 0),
            }
        )
    return out


def _last_n_closes_for_sparkline(df: Optional[pd.DataFrame], n: int = 30) -> List[float]:
    if df is None or df.empty:
        return []
    try:
        df_asc = df.sort_index(ascending=True)
    except Exception:
        return []
    cols = {c.lower(): c for c in df_asc.columns}

    def close_col() -> str:
        for key in cols:
            if key.startswith("close"):
                return cols[key]
        return "close"

    cname = close_col()
    if cname not in df_asc.columns:
        return []
    ser = df_asc[cname].tail(n)
    return [float(x) for x in ser if pd.notna(x)]


def _last_close(df: Optional[pd.DataFrame]) -> Optional[float]:
    if df is None or df.empty:
        return None
    cols = {c.lower(): c for c in df.columns}

    def close_col() -> str:
        for key in cols:
            if key.startswith("close"):
                return cols[key]
        return "close"

    cname = close_col()
    if cname not in df.columns:
        return None
    try:
        v = float(df[cname].iloc[0])
    except Exception as e:
        logger.warning("share og: last close parse failed: %s", e)
        return None
    if v != v:  # NaN
        return None
    return v


class ChartShareCreateRequest(BaseModel):
    symbol: str
    period: str = "1y"
    indicators: List[str] = Field(default_factory=list, max_length=32)

    @field_validator("symbol")
    @classmethod
    def _sym(cls, v: str) -> str:
        s = v.strip().upper()
        if not s or len(s) > 32:
            raise ValueError("Invalid symbol")
        return s

    @field_validator("period")
    @classmethod
    def _period(cls, v: str) -> str:
        p = v.strip()
        if p not in _VALID_PERIODS:
            raise ValueError("Invalid period for chart share")
        return p

    @field_validator("indicators")
    @classmethod
    def _inds(cls, v: List[str]) -> List[str]:
        out: List[str] = []
        for x in v:
            s = str(x).strip()
            if s in _VALID_INDICATOR_KEYS and s not in out:
                out.append(s)
        return out


class ChartShareCreateResponse(BaseModel):
    token: str
    url: str


@router.post("/chart", response_model=ChartShareCreateResponse)
async def create_chart_share(
    body: ChartShareCreateRequest,
    current_user: User = Depends(get_current_user),
) -> ChartShareCreateResponse:
    """Authenticated: mint a 30-day signed link for the public chart view."""
    token = create_chart_share_token(
        user_id=int(current_user.id),
        symbol=body.symbol,
        period=body.period,
        indicators=body.indicators,
    )
    base = _public_frontend_base()
    url = f"{base}/share/c/{token}"
    return ChartShareCreateResponse(token=token, url=url)


@router.get("/chart/{token}/bars")
async def get_chart_share_bars(
    token: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Public: verify token and return daily OHLCV in the same shape as
    ``GET /api/v1/market-data/prices/{symbol}/history`` for chart rendering.
    """
    try:
        claims = decode_chart_share_token(token)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=401, detail="This share link has expired"
        ) from e
    except (jwt.InvalidTokenError, ValueError) as e:
        raise HTTPException(
            status_code=401, detail="Invalid or corrupted share link"
        ) from e

    sym = str(claims["symbol"])
    period = str(claims.get("period", "1y"))
    ind = claims.get("indicators") or []
    if not isinstance(ind, list):
        ind = []

    try:
        res = await provider_router.get_historical_data(
            symbol=sym,
            period=period,
            interval="1d",
            max_bars=None,
            return_provider=True,
            db=db,
        )
        if isinstance(res, tuple) and len(res) == 2:
            df, raw_src = res[0], res[1]
        else:
            df, raw_src = res, None  # type: ignore[assignment]
    except Exception as e:
        logger.exception("chart share bars: provider failed for %s: %s", sym, e)
        raise HTTPException(
            status_code=503, detail="Market data is temporarily unavailable"
        ) from e

    if df is None or df.empty:
        raise HTTPException(
            status_code=404, detail="No price history is available for this symbol yet"
        )

    bars = _dataframe_to_bars(df)
    if not bars:
        raise HTTPException(
            status_code=404, detail="No price history is available for this symbol yet"
        )

    return {
        "symbol": sym,
        "period": period,
        "interval": "1d",
        "data_source": _history_data_source(
            str(raw_src) if raw_src is not None else None
        ),
        "bars": bars,
        "indicators": [str(x) for x in ind],
    }


@router.get("/chart/{token}/og.png")
async def get_chart_share_og(
    token: str,
    db: Session = Depends(get_db),
) -> Response:
    """Open Graph 1200x630 image for link previews (public, token-gated)."""
    try:
        claims = decode_chart_share_token(token)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="This share link has expired") from e
    except (jwt.InvalidTokenError, ValueError) as e:
        raise HTTPException(
            status_code=401, detail="Invalid or corrupted share link"
        ) from e

    sym = str(claims["symbol"])
    period = str(claims.get("period", "1y"))

    try:
        res = await provider_router.get_historical_data(
            symbol=sym,
            period=period,
            interval="1d",
            max_bars=None,
            return_provider=True,
            db=db,
        )
        if isinstance(res, tuple) and len(res) == 2:
            df, _ = res[0], res[1]
        else:
            df = res  # type: ignore[assignment]
    except Exception as e:
        logger.exception("chart share og: provider failed for %s: %s", sym, e)
        raise HTTPException(
            status_code=503, detail="Market data is temporarily unavailable"
        ) from e

    spark = _last_n_closes_for_sparkline(df, 30) if df is not None and not df.empty else []
    last_price = _last_close(df) if df is not None and not df.empty else None
    if not spark and (df is None or df.empty):
        logger.warning("chart share og: empty history for %s — placeholder image", sym)
    try:
        png = render_chart_og_png(
            symbol=sym,
            last_price=last_price,
            sparkline=spark,
        )
    except Exception as e:
        logger.exception("chart share og: render failed for %s: %s", sym, e)
        raise HTTPException(
            status_code=500, detail="Failed to render preview image"
        ) from e

    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )
