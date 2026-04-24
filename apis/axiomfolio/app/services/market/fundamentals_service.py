"""medallion: silver"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import fmpsdk
import yfinance as yf

from app.config import settings
from app.services.market.constants import FUNDAMENTAL_FIELDS, ETF_SECTOR_INDUSTRY

logger = logging.getLogger(__name__)


def needs_fundamentals(snapshot: Dict[str, Any]) -> bool:
    """Return True when *snapshot* is missing core fundamental fields or data is stale (>7 days)."""
    if any(snapshot.get(f) is None for f in FUNDAMENTAL_FIELDS):
        return True
    ts = snapshot.get("analysis_timestamp")
    if ts is not None:
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except Exception as e:
                logger.warning(
                    "needs_fundamentals: could not parse analysis_timestamp string: %s",
                    e,
                )
                return False
        try:
            ts_utc = (
                ts.replace(tzinfo=timezone.utc)
                if ts.tzinfo is None
                else ts.astimezone(timezone.utc)
            )
            age = datetime.now(timezone.utc) - ts_utc
            if age > timedelta(days=7):
                return True
        except Exception as e:
            logger.warning("timestamp_age_check failed: %s", e)
    return False


class FundamentalsService:
    """Multi-provider fundamentals fetch.

    Accepts ``MarketInfra`` for Redis/API clients and ``ProviderRouter``
    for retry infrastructure.
    """

    def __init__(self, infra, provider_router) -> None:
        self._infra = infra
        self._provider = provider_router

    def get_fundamentals_info(self, symbol: str) -> Dict[str, Any]:
        """Return fundamentals for *symbol* using multi-provider cascade.

        Provider order: FMP -> Finnhub -> yfinance -> Alpha Vantage.
        Each subsequent provider only fills fields still missing.
        """
        from app.services.market.rate_limiter import provider_rate_limiter

        info: Dict[str, Any] = {}

        def _decimal_to_pct(value: Any) -> Optional[float]:
            try:
                return float(value) * 100.0 if value is not None else None
            except Exception as e:
                logger.warning(
                    "get_fundamentals_info: could not convert value to percent (%r): %s",
                    value,
                    e,
                )
                return None

        def set_if_missing(key: str, value: Any) -> None:
            if info.get(key) is None and value is not None:
                info[key] = value

        def call_fmp_first_available(
            candidate_names: list[str], *, apikey: str, symbol: str
        ) -> Any:
            last_exc: Exception | None = None
            for fn_name in candidate_names:
                fn = getattr(fmpsdk, fn_name, None)
                if not callable(fn):
                    continue
                try:
                    provider_rate_limiter.acquire_sync("fmp")
                    result = self._provider._call_blocking_with_retries_sync(
                        fn, apikey=apikey, symbol=symbol
                    )
                    self._infra._record_provider_call_sync("fmp")
                    return result
                except Exception as exc:
                    last_exc = exc
                    continue
            if last_exc is not None:
                raise last_exc
            return None

        # --- Provider 1: FMP ---
        fmp_budget_ok = False
        try:
            _r = self._infra._sync_redis
            _dk = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            _cur = int(_r.hget(f"provider:calls:{_dk}", "fmp") or 0)
            if _cur < settings.provider_policy.fmp_daily_budget:
                fmp_budget_ok = True
            else:
                logger.warning("fundamentals: FMP over daily budget (%d/%d) for %s", _cur, settings.provider_policy.fmp_daily_budget, symbol)
        except Exception as _be:
            logger.warning("fundamentals: budget check failed for %s, skipping FMP: %s", symbol, _be)

        try:
            if settings.FMP_API_KEY and fmp_budget_ok:
                provider_rate_limiter.acquire_sync("fmp")
                prof = self._provider._call_blocking_with_retries_sync(
                    fmpsdk.company_profile, apikey=settings.FMP_API_KEY, symbol=symbol,
                )
                self._infra._record_provider_call_sync("fmp")
                if prof and len(prof) > 0 and isinstance(prof[0], dict):
                    d = prof[0]
                    info = {
                        "name": d.get("companyName") or d.get("company_name") or d.get("symbol"),
                        "sector": d.get("sector"),
                        "industry": d.get("industry"),
                        "sub_industry": d.get("subIndustry") or d.get("sub_industry"),
                        "market_cap": d.get("mktCap"),
                    }
                    if d.get("beta") is not None:
                        info["beta"] = d.get("beta")
                try:
                    provider_rate_limiter.acquire_sync("fmp")
                    metrics = self._provider._call_blocking_with_retries_sync(
                        fmpsdk.key_metrics_ttm, apikey=settings.FMP_API_KEY, symbol=symbol,
                    )
                    self._infra._record_provider_call_sync("fmp")
                    if metrics and isinstance(metrics[0], dict):
                        m = metrics[0]
                        set_if_missing("pe_ttm", m.get("peRatioTTM") or m.get("peRatio"))
                        set_if_missing("peg_ttm", m.get("pegRatioTTM") or m.get("pegRatio"))
                        set_if_missing("dividend_yield", _decimal_to_pct(m.get("dividendYieldTTM") or m.get("dividendYield")))
                        set_if_missing("roe", _decimal_to_pct(m.get("roeTTM") or m.get("roe")))
                        set_if_missing("beta", m.get("beta"))
                        set_if_missing("eps_ttm", m.get("netIncomePerShareTTM") or m.get("epsTTM"))
                        set_if_missing("revenue_ttm", m.get("revenuePerShareTTM"))
                except Exception as exc:
                    logger.warning("FMP key metrics failed for %s: %s", symbol, exc)
                try:
                    ratios = call_fmp_first_available(
                        ["financial_ratios_ttm", "ratios_ttm", "financial_ratios"],
                        apikey=settings.FMP_API_KEY, symbol=symbol,
                    )
                    if ratios and isinstance(ratios[0], dict):
                        r = ratios[0]
                        set_if_missing("pe_ttm", r.get("priceEarningsRatioTTM") or r.get("priceEarningsRatio"))
                        set_if_missing("peg_ttm", r.get("pegRatioTTM") or r.get("pegRatio"))
                        set_if_missing("roe", _decimal_to_pct(r.get("returnOnEquityTTM") or r.get("returnOnEquity")))
                        set_if_missing("dividend_yield", _decimal_to_pct(r.get("dividendYieldTTM") or r.get("dividendYield")))
                except Exception as exc:
                    logger.warning("FMP ratios failed for %s: %s", symbol, exc)
                try:
                    provider_rate_limiter.acquire_sync("fmp")
                    growth = self._provider._call_blocking_with_retries_sync(
                        fmpsdk.financial_growth, apikey=settings.FMP_API_KEY, symbol=symbol,
                    )
                    self._infra._record_provider_call_sync("fmp")
                    if growth and isinstance(growth[0], dict):
                        g = growth[0]
                        set_if_missing("eps_growth_yoy", _decimal_to_pct(g.get("epsGrowth") or g.get("epsgrowth")))
                        set_if_missing("eps_growth_qoq", _decimal_to_pct(g.get("epsGrowthQuarterly") or g.get("epsGrowthQoQ")))
                        set_if_missing("revenue_growth_yoy", _decimal_to_pct(g.get("revenueGrowth") or g.get("revenuegrowth")))
                        set_if_missing("revenue_growth_qoq", _decimal_to_pct(g.get("revenueGrowthQuarterly") or g.get("revenueGrowthQoQ")))
                except Exception as exc:
                    logger.warning("FMP financial growth failed for %s: %s", symbol, exc)
        except Exception as exc:
            logger.warning("FMP fundamentals failed for %s: %s", symbol, exc)

        # --- Provider 2: Finnhub ---
        finnhub_client = self._infra.finnhub_client
        if finnhub_client and needs_fundamentals(info):
            try:
                provider_rate_limiter.acquire_sync("finnhub")
                prof2 = finnhub_client.company_profile2(symbol=symbol)
                if isinstance(prof2, dict) and prof2.get("name"):
                    set_if_missing("name", prof2.get("name"))
                    set_if_missing("sector", prof2.get("finnhubIndustry"))
                    set_if_missing("industry", prof2.get("finnhubIndustry"))
                    set_if_missing("market_cap", prof2.get("marketCapitalization"))
            except Exception as exc:
                logger.debug("Finnhub profile failed for %s: %s", symbol, exc)
            try:
                provider_rate_limiter.acquire_sync("finnhub")
                basics = finnhub_client.company_basic_financials(symbol=symbol, metric="all")
                if isinstance(basics, dict):
                    m = basics.get("metric", {})
                    set_if_missing("pe_ttm", m.get("peTTM"))
                    set_if_missing("beta", m.get("beta"))
                    set_if_missing("roe", _decimal_to_pct(m.get("roeTTM")))
                    set_if_missing("dividend_yield", _decimal_to_pct(m.get("dividendYieldIndicatedAnnual")))
                    set_if_missing("eps_ttm", m.get("epsTTM"))
                    set_if_missing("revenue_ttm", m.get("revenueTTM"))
                    set_if_missing("peg_ttm", m.get("pegAnnual"))
                    set_if_missing("high_52w_price", m.get("52WeekHigh"))
                    set_if_missing("low_52w_price", m.get("52WeekLow"))
            except Exception as exc:
                logger.debug("Finnhub basic financials failed for %s: %s", symbol, exc)

        # --- Provider 3: yfinance ---
        needs_core = any(info.get(k) is None for k in FUNDAMENTAL_FIELDS[:5])
        needs_full = needs_fundamentals(info)
        if needs_full or needs_core:
            try:
                provider_rate_limiter.acquire_sync("yfinance")
                y = self._provider._call_blocking_with_retries_sync(lambda: yf.Ticker(symbol).info)
                if y:
                    if not info:
                        info = {
                            "name": y.get("shortName") or y.get("longName") or y.get("symbol"),
                            "sector": y.get("sector"),
                            "industry": y.get("industry"),
                            "sub_industry": y.get("subIndustry") or y.get("industry") or None,
                            "market_cap": y.get("marketCap"),
                        }
                    set_if_missing("name", y.get("shortName") or y.get("longName"))
                    set_if_missing("sector", y.get("sector"))
                    set_if_missing("industry", y.get("industry"))
                    set_if_missing("sub_industry", y.get("subIndustry") or y.get("industry"))
                    set_if_missing("market_cap", y.get("marketCap"))
                    set_if_missing("beta", y.get("beta"))
                    set_if_missing("pe_ttm", y.get("trailingPE") or y.get("forwardPE"))
                    set_if_missing("peg_ttm", y.get("pegRatio"))
                    set_if_missing("roe", _decimal_to_pct(y.get("returnOnEquity")))
                    set_if_missing("dividend_yield", _decimal_to_pct(y.get("dividendYield")))
                    set_if_missing("eps_growth_yoy", _decimal_to_pct(y.get("earningsGrowth")))
                    set_if_missing("eps_growth_qoq", _decimal_to_pct(y.get("earningsQuarterlyGrowth")))
                    set_if_missing("revenue_growth_yoy", _decimal_to_pct(y.get("revenueGrowth")))
                    set_if_missing("revenue_growth_qoq", _decimal_to_pct(y.get("revenueQuarterlyGrowth")))
                    set_if_missing("eps_ttm", y.get("trailingEps"))
                    set_if_missing("revenue_ttm", y.get("totalRevenue"))
                    set_if_missing("analyst_rating", y.get("recommendationKey"))
                    earnings = y.get("earningsDate")
                    if isinstance(earnings, (list, tuple)) and earnings:
                        set_if_missing("next_earnings", earnings[0])
                    set_if_missing("last_earnings", y.get("lastEarningsDate"))
            except Exception as e:
                logger.warning("fundamentals fetch failed for %s: %s", symbol, e)
                if not info:
                    info = {}

        # --- Provider 4: Alpha Vantage (last resort) ---
        if settings.ALPHA_VANTAGE_API_KEY and needs_fundamentals(info):
            try:
                import requests as _requests
                provider_rate_limiter.acquire_sync("alphavantage")
                url = (
                    f"https://www.alphavantage.co/query?function=OVERVIEW"
                    f"&symbol={symbol}&apikey={settings.ALPHA_VANTAGE_API_KEY}"
                )
                resp = _requests.get(url, timeout=10)
                if resp.ok:
                    av = resp.json()
                    if av.get("Symbol"):
                        set_if_missing("name", av.get("Name"))
                        set_if_missing("sector", av.get("Sector"))
                        set_if_missing("industry", av.get("Industry"))
                        try:
                            set_if_missing("market_cap", float(av["MarketCapitalization"]))
                        except (ValueError, KeyError, TypeError):
                            pass
                        try:
                            set_if_missing("pe_ttm", float(av["TrailingPE"]))
                        except (ValueError, KeyError, TypeError):
                            pass
                        try:
                            set_if_missing("peg_ttm", float(av["PEGRatio"]))
                        except (ValueError, KeyError, TypeError):
                            pass
                        try:
                            set_if_missing("eps_ttm", float(av["EPS"]))
                        except (ValueError, KeyError, TypeError):
                            pass
                        try:
                            set_if_missing("revenue_ttm", float(av["RevenueTTM"]))
                        except (ValueError, KeyError, TypeError):
                            pass
                        try:
                            set_if_missing("beta", float(av["Beta"]))
                        except (ValueError, KeyError, TypeError):
                            pass
                        try:
                            set_if_missing("roe", _decimal_to_pct(float(av["ReturnOnEquityTTM"])))
                        except (ValueError, KeyError, TypeError):
                            pass
                        try:
                            set_if_missing("dividend_yield", _decimal_to_pct(float(av["DividendYield"])))
                        except (ValueError, KeyError, TypeError):
                            pass
                        try:
                            set_if_missing("eps_growth_yoy", _decimal_to_pct(float(av["QuarterlyEarningsGrowthYOY"])))
                        except (ValueError, KeyError, TypeError):
                            pass
                        try:
                            set_if_missing("revenue_growth_yoy", _decimal_to_pct(float(av["QuarterlyRevenueGrowthYOY"])))
                        except (ValueError, KeyError, TypeError):
                            pass
                        set_if_missing("analyst_rating", av.get("AnalystRating") or av.get("AnalystTargetPrice"))
            except Exception as exc:
                logger.debug("Alpha Vantage overview failed for %s: %s", symbol, exc)

        # --- ETF sector/industry override ---
        upper_sym = symbol.upper()
        if upper_sym in ETF_SECTOR_INDUSTRY:
            etf_sector, etf_industry = ETF_SECTOR_INDUSTRY[upper_sym]
            info["sector"] = etf_sector
            info["industry"] = etf_industry
            if not info.get("sub_industry"):
                info["sub_industry"] = etf_industry

        return info
