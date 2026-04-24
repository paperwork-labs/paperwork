from __future__ import annotations

"""medallion: silver"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import fmpsdk

from backend.config import settings
from backend.services.market.rate_limiter import provider_rate_limiter

if TYPE_CHECKING:
    from backend.services.market.market_infra import MarketInfra

logger = logging.getLogger(__name__)

_TICKER_RE = re.compile(r"^[A-Z]{1,5}(?:-[A-Z]{1,2})?$")
_WIKI_UA = "AxiomFolio/1.0 (https://github.com/sankalp404/axiomfolio)"


class IndexUniverseService:
    """Index constituents, tradeable symbols, and iShares parsing."""

    _IWM_HOLDINGS_URL = (
        "https://www.ishares.com/us/products/239710/"
        "ishares-russell-2000-etf/1467271812596.ajax"
        "?fileType=csv&fileName=IWM_holdings&dataType=fund"
    )

    INDEX_ENDPOINTS = {
        "SP500": {"fmp": "sp500_constituent", "finnhub": "^GSPC"},
        "NASDAQ100": {"fmp": "nasdaq_constituent", "finnhub": "^NDX"},
        "DOW30": {"fmp": "dowjones_constituent", "finnhub": "^DJI"},
        "RUSSELL2000": {"fmp": "russell2000_constituent", "finnhub": "^RUT"},
    }

    def __init__(self, infra: "MarketInfra") -> None:
        self._infra = infra

    @staticmethod
    def _parse_ishares_csv(text: str) -> List[str]:
        """Parse iShares ETF holdings CSV and extract ticker symbols.

        iShares CSVs have metadata header rows before the actual data table.
        The data section starts after a row containing 'Ticker' as a column header.
        """
        import csv
        import io

        lines = text.strip().splitlines()
        header_idx: Optional[int] = None
        ticker_col: Optional[int] = None
        for i, line in enumerate(lines):
            lower = line.lower()
            if "ticker" in lower:
                reader = csv.reader(io.StringIO(line))
                cols = next(reader, [])
                for j, col in enumerate(cols):
                    if col.strip().lower() == "ticker":
                        header_idx = i
                        ticker_col = j
                        break
                if header_idx is not None:
                    break

        if header_idx is None or ticker_col is None:
            return []

        symbols: List[str] = []
        for line in lines[header_idx + 1:]:
            if not line.strip():
                continue
            reader = csv.reader(io.StringIO(line))
            cols = next(reader, [])
            if ticker_col >= len(cols):
                continue
            raw = cols[ticker_col].strip().upper()
            if not raw or raw in ("-", "CASH", "N/A", "NA", "--"):
                continue
            symbol = raw.replace(".", "-")
            if not re.match(r"^[A-Z]{1,5}(?:-[A-Z]{1,2})?$", symbol):
                continue
            symbols.append(symbol)
        return symbols

    @staticmethod
    async def _get_last_good_constituents(r, idx: str) -> List[str]:
        """Return last-known-good constituent list from Redis, or empty list."""
        try:
            raw = await r.get(f"index_constituents:{idx}:last_good")
            if raw:
                data = json.loads(raw)
                return data.get("symbols", [])
        except Exception:
            logger.debug("Failed to read last-known-good constituents for %s", idx)
        return []

    async def _fetch_iwm_holdings(self) -> List[str]:
        """Fetch Russell 2000 constituents from iShares IWM ETF holdings CSV."""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(
                    self._IWM_HOLDINGS_URL,
                    timeout=aiohttp.ClientTimeout(total=60),
                    headers={"User-Agent": "Mozilla/5.0 AxiomFolio/1.0"},
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "iShares IWM fetch returned HTTP %d", resp.status
                        )
                        return []
                    text = await resp.text()
            return self._parse_ishares_csv(text)
        except Exception as exc:
            logger.warning("iShares IWM holdings fetch failed: %s", exc)
            return []

    async def get_index_constituents(self, index_name: str) -> List[str]:
        """Return constituents for supported indices (SP500, NASDAQ100, DOW30, RUSSELL2000).

        Strategy: Redis cache -> FMP -> Finnhub -> Wikipedia/iShares fallback.
        Normalized to UPPER and '.'->'-'.
        """
        cache_key = f"index_constituents:{index_name}"
        r = await self._infra._get_redis()
        cached = await r.get(cache_key)
        if cached:
            try:
                obj = json.loads(cached)
                if isinstance(obj, dict) and obj.get("symbols"):
                    return list(obj.get("symbols"))
            except Exception as e:
                logger.warning("cached_constituents_parse failed for %s: %s", index_name, e)
        idx = index_name.upper()
        ep = self.INDEX_ENDPOINTS.get(idx, {}).get("fmp")
        symbols: List[str] = []
        if settings.FMP_API_KEY and ep:
            fmp_budget_ok = False
            try:
                _r_sync = self._infra._sync_redis
                _date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                _current = int(_r_sync.hget(f"provider:calls:{_date_key}", "fmp") or 0)
                _budget = settings.provider_policy.fmp_daily_budget
                if _current < _budget:
                    fmp_budget_ok = True
                else:
                    logger.warning("get_index_constituents: FMP over daily budget (%d/%d), skipping", _current, _budget)
            except Exception as _budget_exc:
                logger.warning(
                    "Redis unavailable for FMP budget check, allowing FMP for index constituents: %s",
                    _budget_exc,
                )
                fmp_budget_ok = True

            if fmp_budget_ok:
                try:
                    await provider_rate_limiter.acquire("fmp")
                    fn = getattr(fmpsdk, ep, None)
                    if callable(fn):
                        data = await asyncio.to_thread(fn, apikey=settings.FMP_API_KEY)
                    else:
                        import requests as _req
                        resp = await asyncio.to_thread(
                            _req.get,
                            f"https://financialmodelingprep.com/api/v3/{ep}?apikey={settings.FMP_API_KEY}",
                            timeout=30,
                        )
                        data = resp.json() if resp.status_code == 200 else []
                except Exception as exc:
                    logger.warning("Index %s: FMP constituent fetch failed: %s", idx, exc)
                    data = []
                if isinstance(data, list):
                    symbols = [str(d.get("symbol", "")).strip().upper().replace('.', '-') for d in data if d.get("symbol")]
                elif data:
                    logger.warning("Index %s: FMP returned non-list response: %s", idx, str(data)[:200])
        provider_used = "fmp" if symbols else None
        if symbols:
            logger.info("Index %s: fetched %d constituents from FMP", idx, len(symbols))
            await self._infra._record_provider_call("fmp")

        # Wikipedia fallback
        if not symbols:
            import pandas as _pd
            _wiki_kwargs = {"storage_options": {"User-Agent": _WIKI_UA}}
            try:
                if idx == "SP500":
                    tables = await asyncio.to_thread(
                        _pd.read_html, "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", **_wiki_kwargs,
                    )
                    if tables:
                        df = tables[0]
                        if "Symbol" in df.columns:
                            symbols = [str(s).upper().replace('.', '-') for s in df["Symbol"].dropna().tolist()]
                elif idx == "NASDAQ100":
                    tables = await asyncio.to_thread(
                        _pd.read_html, "https://en.wikipedia.org/wiki/Nasdaq-100", **_wiki_kwargs,
                    )
                    for t in tables:
                        for col in ["Ticker", "Symbol", "Company", "Stock Symbol"]:
                            if col in t.columns:
                                symbols = [str(s).upper().replace('.', '-') for s in t[col].dropna().tolist()]
                                break
                        if symbols:
                            break
                elif idx == "DOW30":
                    tables = await asyncio.to_thread(
                        _pd.read_html, "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average", **_wiki_kwargs,
                    )
                    for t in tables:
                        if "Symbol" in t.columns and len(t) <= 40:
                            symbols = [str(s).upper().replace('.', '-') for s in t["Symbol"].dropna().tolist()]
                            break
                elif idx == "RUSSELL2000":
                    symbols = await self._fetch_iwm_holdings()
                    if symbols:
                        provider_used = "ishares_iwm"
                        logger.info(
                            "Index RUSSELL2000: fetched %d constituents from iShares IWM ETF",
                            len(symbols),
                        )
            except Exception as exc:
                logger.warning("Index %s: Wikipedia fallback failed: %s", idx, exc)
                symbols = []
        fallback_used = provider_used not in ("fmp",) if symbols else True
        provider_used = provider_used or ("wikipedia" if symbols else "none")
        if provider_used == "wikipedia":
            logger.info("Index %s: fetched %d constituents from Wikipedia fallback", idx, len(symbols))
        elif provider_used == "none":
            logger.error("Index %s: ALL constituent providers failed (FMP, Finnhub, Wikipedia)", idx)
        normalized = []
        for s in symbols:
            if not s:
                continue
            t = s.upper().replace(".", "-")
            if _TICKER_RE.match(t):
                normalized.append(t)
        out = sorted(set(normalized))
        if not out:
            logger.warning("Index %s: 0 constituents after normalization — skipping cache", idx)
            last_good = await self._get_last_good_constituents(r, idx)
            if last_good:
                logger.warning("Index %s: returning %d last-known-good constituents", idx, len(last_good))
            return last_good or out
        try:
            await r.setex(cache_key, 24 * 3600, json.dumps({"symbols": out}))
            await r.set(f"index_constituents:{idx}:last_good", json.dumps({"symbols": out}))
            meta_key = f"{cache_key}:meta"
            await r.setex(
                meta_key,
                24 * 3600,
                json.dumps({"provider_used": provider_used, "fallback_used": bool(fallback_used), "count": len(out)}),
            )
        except Exception as e:
            logger.warning("redis_constituents_cache failed for %s: %s", idx, e)
        return out

    async def get_all_tradeable_symbols(self, indices: Optional[List[str]] = None) -> Dict[str, List[str]]:
        idxs = ["SP500", "NASDAQ100", "DOW30", "RUSSELL2000"] if not indices else [i.upper() for i in indices]
        result: Dict[str, List[str]] = {}
        for idx in idxs:
            try:
                result[idx] = await self.get_index_constituents(idx)
            except Exception as e:
                logger.warning("get_all_tradeable_symbols failed for index %s: %s", idx, e)
                result[idx] = []
        return result
