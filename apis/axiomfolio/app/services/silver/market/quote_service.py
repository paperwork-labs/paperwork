"""medallion: silver"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

import fmpsdk
import yfinance as yf

from app.config import settings
from app.database import SessionLocal
from app.models.market_data import PriceData
from app.services.silver.market.provider_router import APIProvider
from app.services.silver.math.rate_limiter import provider_rate_limiter

if TYPE_CHECKING:
    from app.services.silver.market.market_infra import MarketInfra
    from app.services.silver.market.provider_router import ProviderRouter
    from app.services.silver.market.fundamentals_service import FundamentalsService

logger = logging.getLogger(__name__)


class QuoteService:
    """Current price resolution and fundamentals delegation."""

    def __init__(self, infra: "MarketInfra", provider_router: "ProviderRouter", fundamentals: "FundamentalsService") -> None:
        self._infra = infra
        self._provider = provider_router
        self._fundamentals = fundamentals

    async def _get_current_price_detail(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Resolve live quote with source and freshness (60s Redis cache, then providers, then DB)."""
        sym_key = symbol.strip().upper()
        cache_key = f"price:{sym_key}"
        cached = None
        r: Optional[Any] = None
        try:
            r = await self._infra._get_redis()
            cached = await r.get(cache_key)
        except Exception as e:
            logger.warning(
                "Redis unavailable for price cache read for %s, falling through to providers: %s",
                sym_key,
                e,
            )
        if cached:
            try:
                price = float(cached)
                as_of = datetime.now(timezone.utc)
                ttl_remain = -1
                if r is not None:
                    try:
                        ttl_remain = int(await r.ttl(cache_key))
                    except Exception as ttl_exc:
                        logger.debug("price cache ttl read failed for %s: %s", sym_key, ttl_exc)
                if ttl_remain >= 0:
                    age_seconds = max(0, 60 - ttl_remain)
                else:
                    age_seconds = 0
                return {
                    "price": price,
                    "source": "redis_cache",
                    "as_of": as_of,
                    "age_seconds": age_seconds,
                }
            except Exception as e:
                logger.warning("cached_price_parse failed for %s: %s", sym_key, e)
        for provider in self._provider._provider_priority("real_time_quote"):
            if not self._provider._is_provider_available(provider):
                continue
            try:
                price = None
                if provider == APIProvider.FMP:
                    try:
                        r_budget = await self._infra._get_redis()
                        _date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        _current = int(
                            await r_budget.hget(f"provider:calls:{_date_key}", "fmp") or 0
                        )
                        _limit = settings.provider_policy.fmp_daily_budget
                        if _current >= _limit:
                            logger.warning(
                                "Provider fmp over daily budget (%d/%d), skipping quote for %s",
                                _current,
                                _limit,
                                sym_key,
                            )
                            continue
                    except Exception as _budget_exc:
                        logger.warning(
                            "Redis unavailable for budget check, allowing FMP quote for %s: %s",
                            sym_key,
                            _budget_exc,
                        )
                    await provider_rate_limiter.acquire("fmp")
                    q = await self._provider._call_blocking_with_retries(
                        fmpsdk.quote, apikey=settings.FMP_API_KEY, symbol=sym_key
                    )
                    price = q and len(q) > 0 and q[0].get("price")
                elif provider == APIProvider.YFINANCE:
                    hist = await self._provider._call_blocking_with_retries(
                        lambda: yf.Ticker(sym_key).history(period="1d", interval="1m")
                    )
                    price = float(hist["Close"].iloc[-1]) if not hist.empty else None
                if price is not None:
                    self._provider._cb_record_success(provider)
                    if provider == APIProvider.FMP:
                        await self._infra._record_provider_call("fmp")
                    try:
                        r_w = await self._infra._get_redis()
                        await r_w.setex(cache_key, 60, str(price))
                    except Exception as e:
                        logger.warning(
                            "Redis unavailable for price cache write for %s: %s", sym_key, e
                        )
                    as_of = datetime.now(timezone.utc)
                    if provider == APIProvider.FMP:
                        src = "provider_fmp"
                    elif provider == APIProvider.YFINANCE:
                        src = "provider_yfinance"
                    else:
                        src = f"provider_{provider.value}"
                    return {
                        "price": float(price),
                        "source": src,
                        "as_of": as_of,
                        "age_seconds": 0,
                    }
            except Exception as exc:
                logger.warning(
                    "get_current_price provider %s failed for %s: %s",
                    provider.value,
                    sym_key,
                    exc,
                )
                self._provider._cb_record_failure(provider)
                continue
        db = SessionLocal()
        try:
            row = (
                db.query(PriceData)
                .filter(PriceData.symbol == sym_key, PriceData.interval == "1d")
                .order_by(PriceData.date.desc())
                .first()
            )
            if row is not None and row.close_price is not None:
                bar_ts = row.date
                if bar_ts is None:
                    return None
                if bar_ts.tzinfo is None:
                    as_of = bar_ts.replace(tzinfo=timezone.utc)
                else:
                    as_of = bar_ts.astimezone(timezone.utc)
                now = datetime.now(timezone.utc)
                age_seconds = max(0, int((now - as_of).total_seconds()))
                return {
                    "price": float(row.close_price),
                    "source": "db_fallback",
                    "as_of": as_of,
                    "age_seconds": age_seconds,
                }
        except Exception as db_exc:
            logger.warning("get_current_price db_fallback failed for %s: %s", sym_key, db_exc)
        finally:
            db.close()
        return None

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol with provider policy and 60s Redis cache."""
        detail = await self._get_current_price_detail(symbol)
        return float(detail["price"]) if detail else None

    async def get_current_price_with_freshness(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Same as live quote path as `get_current_price`, with API-oriented freshness fields."""
        detail = await self._get_current_price_detail(symbol)
        if not detail:
            return None
        as_of = detail["as_of"]
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        as_of_utc = as_of.astimezone(timezone.utc)
        as_of_str = as_of_utc.isoformat().replace("+00:00", "Z")
        return {
            "price": detail["price"],
            "source": detail["source"],
            "as_of": as_of_str,
            "age_seconds": int(detail["age_seconds"]),
        }

    def get_fundamentals_info(self, symbol: str) -> Dict[str, Any]:
        """Delegate to FundamentalsService (multi-provider cascade)."""
        return self._fundamentals.get_fundamentals_info(symbol)
