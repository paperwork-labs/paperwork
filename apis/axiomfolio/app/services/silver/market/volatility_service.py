"""Volatility dashboard service.

Provides VIX/VVIX/VIX3M regime indicators with caching.

medallion: silver
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.config import settings

logger = logging.getLogger(__name__)


class VolatilityService:
    """Compute and cache VIX/VVIX/VIX3M volatility regime data."""

    CACHE_KEY = "volatility_dashboard"
    CACHE_TTL = 300

    def __init__(self, redis_client=None, fmp_api_key: str | None = None) -> None:
        self._redis = redis_client
        self._fmp_key = fmp_api_key

    def _get_cached(self) -> Dict[str, Any] | None:
        if not self._redis:
            return None
        try:
            raw = self._redis.get(self.CACHE_KEY)
            if raw:
                return json.loads(raw)
        except Exception:
            logger.debug("Failed to read volatility cache")
        return None

    def _set_cache(self, data: Dict[str, Any]) -> None:
        if not self._redis:
            return
        try:
            self._redis.setex(self.CACHE_KEY, self.CACHE_TTL, json.dumps(data))
        except Exception:
            logger.debug("Failed to write volatility cache")

    def _check_fmp_budget(self) -> bool:
        """Return True if FMP daily budget has capacity. Fail-closed on Redis error."""
        if not self._redis:
            return False
        try:
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            current = int(self._redis.hget(f"provider:calls:{date_key}", "fmp") or 0)
            budget = settings.provider_policy.fmp_daily_budget
            if current >= budget:
                logger.warning("VolatilityService: FMP over daily budget (%d/%d)", current, budget)
                return False
            return True
        except Exception as exc:
            logger.warning("VolatilityService: budget check failed (Redis error), treating as over-budget: %s", exc)
            return False

    def _record_fmp_call(self, n: int = 1) -> None:
        """Increment the daily FMP call counter in Redis."""
        if not self._redis:
            return
        try:
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            hash_key = f"provider:calls:{date_key}"
            self._redis.hincrby(hash_key, "fmp", n)
            self._redis.expire(hash_key, 86400 * 30)
        except Exception:
            logger.debug("VolatilityService: failed to record FMP call")

    async def get_dashboard(self) -> Dict[str, Any]:
        cached = self._get_cached()
        if cached:
            return cached

        result: Dict[str, Any] = {
            "vix": None, "vvix": None, "vix3m": None,
            "term_structure_ratio": None, "vol_of_vol_ratio": None,
            "regime": "unknown", "signal": "",
        }

        if not self._fmp_key:
            return result

        if not self._check_fmp_budget():
            return result

        import aiohttp
        from app.services.silver.math.rate_limiter import provider_rate_limiter

        symbols = {"vix": "^VIX", "vvix": "^VVIX", "vix3m": "^VIX3M"}
        quotes: Dict[str, float] = {}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            for key, sym in symbols.items():
                try:
                    await provider_rate_limiter.acquire("fmp")
                    url = f"https://financialmodelingprep.com/api/v3/quote/{sym}?apikey={self._fmp_key}"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and isinstance(data, list) and len(data) > 0:
                                quotes[key] = float(data[0].get("price", 0))
                    self._record_fmp_call()
                except Exception as exc:
                    logger.warning("Failed to fetch volatility quote for %s (%s): %s", key, sym, exc)

        vix = quotes.get("vix")
        vvix = quotes.get("vvix")
        vix3m = quotes.get("vix3m")

        result["vix"] = vix
        result["vvix"] = vvix
        result["vix3m"] = vix3m

        if vix and vix > 0:
            if vix3m:
                result["term_structure_ratio"] = round(vix3m / vix, 3)
            if vvix:
                result["vol_of_vol_ratio"] = round(vvix / vix, 2)

        if vix is not None:
            if vix < 15:
                result["regime"] = "calm"
            elif vix < 20:
                result["regime"] = "elevated"
            elif vix < 30:
                result["regime"] = "fear"
            else:
                result["regime"] = "extreme"

        ts = result.get("term_structure_ratio")
        vov = result.get("vol_of_vol_ratio")
        if vov is not None and ts is not None:
            if vov < 3.5 and ts >= 1.0:
                result["signal"] = "Protection is cheap - good time to hedge"
            elif vov > 6.0:
                result["signal"] = "Market stressed - hedges expensive, consider reducing"
            elif vix is not None and vix < 15 and ts >= 1.0:
                result["signal"] = "Calm markets - no urgency"
            else:
                result["signal"] = ""

        self._set_cache(result)
        return result
