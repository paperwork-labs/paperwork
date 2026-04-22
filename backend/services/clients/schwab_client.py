"""
Schwab Trader API Client
Production-ready scaffold for Schwab Trader API v1 (https://api.schwabapi.com/trader/v1).
Uses OAuth tokens from the aggregator callback flow. Returns empty results when not configured.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from backend.config import settings
from backend.services.aggregator.schwab_connector import SchwabConnector

logger = logging.getLogger(__name__)

BASE_URL = "https://api.schwabapi.com/trader/v1"
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


def _option_expiry_iso_from_occ_symbol(occ: str) -> str:
    """Last-resort: Schwab-style OCC like ``SOUN  260717C00009000`` — YYMMDD at indices 6–11.

    Returns ISO date ``YYYY-MM-DD`` or "" if the symbol does not look like a standard OCC.
    """
    s = (occ or "").strip()
    if len(s) < 12:
        return ""
    yymmdd = s[6:12]
    if not yymmdd.isdigit() or len(yymmdd) != 6:
        return ""
    yy = int(yymmdd[0:2])
    mm = int(yymmdd[2:4])
    dd = int(yymmdd[4:6])
    year = 2000 + yy if yy < 90 else 1900 + yy
    try:
        return date(year, mm, dd).isoformat()
    except ValueError:
        return ""


def _is_schwab_oauth_configured() -> bool:
    """Return True if Schwab OAuth app credentials are set (client_id, redirect_uri)."""
    cid = getattr(settings, "SCHWAB_CLIENT_ID", None)
    redirect = getattr(settings, "SCHWAB_REDIRECT_URI", None)
    return bool(cid and redirect and str(cid).strip() and str(redirect).strip())


class SchwabClient:
    """
    Schwab Trader API client (read-only scaffold).

    Uses OAuth access_token/refresh_token from the aggregator callback flow.
    When credentials are not provided or OAuth is not configured, returns empty lists
    and logs clear messages about what's needed.

    Method signatures mirror the TastyTrade client pattern.
    """

    def __init__(self) -> None:
        self.connected = False
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._account_hash_map: Dict[str, str] = {}  # account_number -> hashValue
        self._on_token_refresh: Optional[Any] = None  # callback(access_token, refresh_token)

    def set_token_refresh_callback(self, callback: Any) -> None:
        """Set a callback invoked after a successful token refresh.

        The callback signature is ``callback(access_token: str, refresh_token: str)``.
        Used by the sync service to persist refreshed tokens back to the DB.
        """
        self._on_token_refresh = callback

    async def connect(self) -> bool:
        """
        Connect with no credentials. Used when caller has not yet passed tokens.
        Returns False and logs what's needed.
        """
        if not _is_schwab_oauth_configured():
            logger.info(
                "Schwab API: OAuth not configured. Set SCHWAB_CLIENT_ID and "
                "SCHWAB_REDIRECT_URI, then link an account via the Connections page OAuth flow."
            )
            self.connected = False
            return False
        logger.info(
            "Schwab API: connect() called without credentials. Use "
            "connect_with_credentials(access_token, refresh_token) after loading from "
            "AccountCredentials for the linked account."
        )
        self.connected = False
        return False

    async def connect_with_credentials(
        self,
        access_token: str,
        refresh_token: str,
        **_kwargs: Any,
    ) -> bool:
        """
        Connect using OAuth tokens from AccountCredentials (after OAuth callback).
        Mirrors TastyTrade connect_with_credentials pattern.
        """
        if not access_token or not refresh_token:
            logger.warning(
                "Schwab API: connect_with_credentials called with empty "
                "access_token or refresh_token. Returning disconnected."
            )
            self.connected = False
            return False
        if not _is_schwab_oauth_configured():
            logger.warning(
                "Schwab API: OAuth app not configured (SCHWAB_CLIENT_ID, "
                "SCHWAB_REDIRECT_URI). Tokens cannot be refreshed."
            )
            self.connected = False
            return False

        self._access_token = str(access_token).strip()
        self._refresh_token = str(refresh_token).strip()
        self.connected = True
        logger.info("Schwab API: connected with OAuth tokens")
        return True

    async def _ensure_token(self) -> bool:
        """Refresh token if we get 401. Returns False if refresh fails.

        After a successful refresh the ``_on_token_refresh`` callback is invoked
        so the caller (sync service) can persist the new tokens to the DB.
        """
        if not self._refresh_token or not self.connected:
            return False
        try:
            connector = SchwabConnector()
            tokens = await connector.refresh_tokens(self._refresh_token)
            new_access = tokens.get("access_token")
            new_refresh = tokens.get("refresh_token", self._refresh_token)
            if not new_access:
                logger.error("Schwab API: token refresh returned empty access_token")
                return False
            self._access_token = new_access
            self._refresh_token = new_refresh
            logger.info("Schwab API: token refresh succeeded")
            if self._on_token_refresh:
                try:
                    self._on_token_refresh(new_access, new_refresh)
                except Exception as cb_exc:
                    logger.error("Schwab API: token refresh callback failed: %s", cb_exc)
            return True
        except Exception as e:
            logger.error("Schwab API: token refresh failed: %s", e)
        return False

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Perform authenticated request. On 401, refresh and retry once.
        Returns parsed JSON (dict or list) or None on failure.
        """
        if not self.connected or not self._access_token:
            return None

        url = f"{BASE_URL}{path}"

        async def _do_request(token: str) -> tuple[int, Any]:
            headers = {"Authorization": f"Bearer {token}"}
            async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT) as session:
                async with session.request(method, url, headers=headers, params=params) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = None
                    return resp.status, data

        status, data = await _do_request(self._access_token)
        if status == 401:
            logger.info("Schwab API %s %s: got 401, attempting token refresh", method, path)
            refresh_ok = await self._ensure_token()
            if refresh_ok and self._access_token:
                status, data = await _do_request(self._access_token)
        if status != 200:
            logger.warning("Schwab API %s %s: status=%s body=%s", method, path, status, str(data)[:300])
            return None
        return data

    def _get_account_hash(self, account_number: str, account_list: List[Dict]) -> Optional[str]:
        """
        Resolve account_number to hashValue from GET accounts/accountNumbers response.
        Matches by exact accountNumber or by suffix (last 4 digits) if API returns masked.
        """
        anum = str(account_number).strip()
        for acc in account_list:
            api_num = str(acc.get("accountNumber") or "").strip()
            hv = acc.get("hashValue") or acc.get("hash")
            if not hv:
                continue
            if api_num == anum:
                return str(hv)
            if len(anum) >= 4 and len(api_num) >= 4 and anum[-4:] == api_num[-4:]:
                return str(hv)
        return None

    async def get_accounts(self) -> List[Dict[str, Any]]:
        """
        GET /accounts/accountNumbers - list of {accountNumber, hashValue}.
        Returns empty list when not configured.
        """
        if not self.connected or not self._access_token:
            logger.debug("Schwab API: get_accounts skipped (not connected)")
            return []

        data = await self._request("GET", "/accounts/accountNumbers")
        if not data:
            return []

        # Response can be array or { "accountNumbers": [...] }
        items = data if isinstance(data, list) else (data.get("accountNumbers") or [])
        if not isinstance(items, list):
            return []

        results = []
        for item in items:
            if isinstance(item, dict):
                results.append({
                    "account_number": item.get("accountNumber", ""),
                    "hash_value": item.get("hashValue") or item.get("hash", ""),
                })
        return results

    async def _resolve_account_hash(self, account_number: str) -> Optional[str]:
        """Resolve account_number to hashValue, caching in _account_hash_map."""
        if account_number in self._account_hash_map:
            return self._account_hash_map[account_number]
        accounts = await self.get_accounts()
        if not accounts:
            logger.warning("Schwab API: no accounts returned, cannot resolve hash for %s", account_number)
            return None
        # Build map from account_number to hash
        for a in accounts:
            anum = a.get("account_number", "")
            hv = a.get("hash_value", "")
            if anum and hv:
                self._account_hash_map[anum] = hv
        hv = self._get_account_hash(
            account_number,
            [{"accountNumber": a.get("account_number"), "hashValue": a.get("hash_value")} for a in accounts],
        )
        if hv:
            self._account_hash_map[account_number] = hv
        else:
            available = [a.get("account_number") for a in accounts]
            logger.error(
                "Schwab API: could not resolve hash for account '%s'. "
                "Available accounts from API: %s. All data fetches for this account will return empty.",
                account_number,
                available,
            )
        return hv

    async def _fetch_positions_raw(self, account_hash: str) -> List[Dict[str, Any]]:
        """Fetch the raw positions array from GET /accounts/{hash}?fields=positions."""
        data = await self._request("GET", f"/accounts/{account_hash}", params={"fields": "positions"})
        if not data or not isinstance(data, dict):
            return []
        securities = data.get("securitiesAccount", data)
        if not isinstance(securities, dict):
            return []
        positions_raw = securities.get("positions", [])
        if not isinstance(positions_raw, list):
            return []
        return positions_raw

    async def get_positions(self, account_number: str) -> List[Dict[str, Any]]:
        """
        GET /accounts/{accountHash}?fields=positions — equity positions.
        Returns list of position dicts with symbol, quantity, average_cost, total_cost_basis.
        """
        if not self.connected or not self._access_token:
            logger.debug("Schwab API: get_positions skipped (not connected)")
            return []

        account_hash = await self._resolve_account_hash(account_number)
        if not account_hash:
            return []

        positions_raw = await self._fetch_positions_raw(account_hash)
        results = []
        for p in positions_raw:
            if not isinstance(p, dict):
                continue
            inst = p.get("instrument") or {}
            asset_type = (inst.get("assetType") or inst.get("type") or "").upper()
            if asset_type in ("OPTION", "EQUITY_OPTION"):
                continue
            symbol = (inst.get("symbol") or p.get("symbol") or "").upper()
            if not symbol:
                continue
            qty = float(p.get("longQuantity") or p.get("quantity") or 0) - float(p.get("shortQuantity") or 0)
            avg_cost = None
            cost_basis = None
            for field in ("taxLotAverageLongPrice", "averageLongPrice", "averagePrice", "averageCost"):
                val = p.get(field)
                if val is not None and float(val) > 0:
                    avg_cost = float(val)
                    break
            if avg_cost is None and p.get("currentDayCost"):
                avg_cost = float(p["currentDayCost"])
            if p.get("cost"):
                cost_basis = float(p["cost"])
            results.append({
                "symbol": symbol,
                "quantity": qty,
                "average_cost": avg_cost,
                "total_cost_basis": cost_basis,
                "market_value": float(p.get("marketValue", 0) or 0),
                "day_pnl": float(p.get("currentDayProfitLoss", 0) or 0),
                "day_pnl_pct": float(p.get("currentDayProfitLossPercentage", 0) or 0),
                "maintenance_requirement": float(p.get("maintenanceRequirement", 0) or 0),
                "long_open_pnl": float(p.get("longOpenProfitLoss", 0) or 0),
            })
        logger.info("Schwab API: get_positions returned %d equity positions", len(results))
        return results

    async def get_transactions(
        self, account_number: str, days: int = 365
    ) -> List[Dict[str, Any]]:
        """
        GET /accounts/{accountHash}/transactions with start_date/end_date.
        Schwab supports up to 540 days of history; we clamp to 540. Callers
        may pass 0 (or a non-positive value) to mean 365 days of history.
        Returns empty list when not configured.
        """
        if not self.connected or not self._access_token:
            logger.debug("Schwab API: get_transactions skipped (not connected)")
            return []

        account_hash = await self._resolve_account_hash(account_number)
        if not account_hash:
            return []

        eff = 365 if days is None or int(days) <= 0 else int(days)
        effective_days = min(eff, 540)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=effective_days)
        params = {
            "startDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endDate": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }

        data = await self._request("GET", f"/accounts/{account_hash}/transactions", params=params)
        if not data:
            return []

        transactions_raw = (
            data.get("transactions") if isinstance(data, dict) else (data if isinstance(data, list) else [])
        )
        if not isinstance(transactions_raw, list):
            return []

        results = []
        for t in transactions_raw:
            if not isinstance(t, dict):
                continue
            net_amt = float(t.get("netAmount", 0) or 0)
            transfer_items = t.get("transferItems") or []
            inst = {}
            qty = 0.0
            price = 0.0
            transfer_cost_basis = None
            item: Dict[str, Any] = {}
            if transfer_items and isinstance(transfer_items, list):
                item = transfer_items[0] if transfer_items else {}
                inst = item.get("instrument") or {}
                qty = float(item.get("amount", 0) or 0)
                price = float(item.get("price", 0) or 0)
                transfer_cost_basis = float(item.get("cost", 0) or 0) if item.get("cost") else None
            if not inst:
                inst = t.get("instrument") or {}
            symbol = (inst.get("symbol") or t.get("symbol") or "").upper()
            pe_raw = item.get("positionEffect") or item.get("position_effect") or ""
            position_effect = str(pe_raw).upper()
            inst_asset = (inst.get("assetType") or inst.get("type") or "").upper()
            results.append({
                "id": str(t.get("activityId") or t.get("transactionId") or t.get("id") or ""),
                "account_number": account_number,
                "symbol": symbol,
                "action": t.get("type", t.get("transactionType", "")),
                "activity_type": t.get("activityType", ""),
                "sub_account": t.get("subAccount", ""),
                "quantity": qty or float(t.get("quantity", 0) or 0),
                "price": price or float(t.get("price", 0) or 0),
                "amount": net_amt,
                "commission": float(t.get("commission", 0) or 0),
                "transfer_cost_basis": transfer_cost_basis,
                "position_id": t.get("positionId"),
                "order_id": t.get("orderId"),
                "date": t.get("tradeDate") or t.get("settlementDate") or t.get("transactionDate") or t.get("date"),
                "description": t.get("description") or "",
                "instrument_asset_type": inst_asset,
                "position_effect": position_effect,
            })
        return results

    async def get_account_balances(self, account_number: str) -> Dict[str, Any]:
        """
        GET /accounts/{accountHash} (balances). Returns dict with cash and net liquidating value.
        Returns empty dict when not configured.
        """
        if not self.connected or not self._access_token:
            logger.debug("Schwab API: get_account_balances skipped (not connected)")
            return {}

        account_hash = await self._resolve_account_hash(account_number)
        if not account_hash:
            return {}

        data = await self._request("GET", f"/accounts/{account_hash}")
        if not data or not isinstance(data, dict):
            return {}

        securities = data.get("securitiesAccount", data)
        bal = securities.get("currentBalances") or data.get("currentBalances") or {}
        if not isinstance(bal, dict):
            return {}

        def _f(key: str, *alt_keys: str) -> float:
            for k in (key, *alt_keys):
                v = bal.get(k)
                if v is not None:
                    return float(v)
            return 0.0

        result = {
            "cash_balance": _f("cashBalance"),
            "net_liquidating_value": _f("liquidationValue", "netLiquidatingValue"),
            "equity_buying_power": _f("buyingPower"),
            "available_funds": _f("availableFunds"),
            "day_trading_buying_power": _f("dayTradingBuyingPower"),
            "equity": _f("equity"),
            "equity_percentage": _f("equityPercentage"),
            "long_margin_value": _f("longMarginValue"),
            "maintenance_call": _f("maintenanceCall"),
            "maintenance_requirement": _f("maintenanceRequirement"),
            "margin_balance": _f("marginBalance"),
            "reg_t_call": _f("regTCall"),
            "short_margin_value": _f("shortMarginValue"),
            "sma": _f("sma"),
            "account_type": (securities.get("type") or "").upper(),
        }
        logger.info("Schwab API: get_account_balances NLV=%.2f equity=%.2f margin_req=%.2f",
                     result["net_liquidating_value"], result["equity"], result["maintenance_requirement"])
        return result

    async def get_options_positions(self, account_number: str) -> List[Dict[str, Any]]:
        """Extract option positions from GET /accounts/{hash}?fields=positions."""
        if not self.connected or not self._access_token:
            return []

        account_hash = await self._resolve_account_hash(account_number)
        if not account_hash:
            return []

        positions_raw = await self._fetch_positions_raw(account_hash)
        results = []
        for p in positions_raw:
            if not isinstance(p, dict):
                continue
            inst = p.get("instrument") or {}
            asset_type = (inst.get("assetType") or inst.get("type") or "").upper()
            if asset_type not in ("OPTION", "EQUITY_OPTION"):
                continue
            symbol = (inst.get("underlyingSymbol") or inst.get("symbol") or "").upper()
            option_symbol = (inst.get("symbol") or "").upper()
            qty = float(p.get("longQuantity") or 0) - float(p.get("shortQuantity") or 0)
            expiration = (
                inst.get("optionExpirationDate")
                or inst.get("expirationDate")
                or inst.get("expiry")
                or ""
            )
            if not expiration:
                expiration = _option_expiry_iso_from_occ_symbol(option_symbol) or ""
            results.append({
                "symbol": symbol,
                "option_symbol": option_symbol,
                "quantity": qty,
                "strike": float(inst.get("strikePrice") or 0),
                "expiration": expiration,
                "put_call": (inst.get("putCall") or inst.get("optionType") or "").upper(),
                "average_cost": float(p.get("averageCost", 0) or 0),
                "market_value": float(p.get("marketValue", 0) or 0),
                "net_change": p.get("netChange") if p.get("netChange") is not None else p.get("currentDayProfitLoss"),
                "average_price": p.get("averagePrice") if p.get("averagePrice") is not None else inst.get("averagePrice"),
            })
        logger.info("Schwab API: get_options_positions returned %d option positions", len(results))
        return results

    async def place_order(
        self, account_number: str, order: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Place order - not implemented (read-only client)."""
        logger.warning("Schwab API: place_order not implemented (read-only)")
        return {"status": "not_implemented"}
