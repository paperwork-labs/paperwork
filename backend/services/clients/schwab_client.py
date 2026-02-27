"""
Schwab Trader API Client
Production-ready scaffold for Schwab Trader API v1 (https://api.schwabapi.com/trader/v1).
Uses OAuth tokens from the aggregator callback flow. Returns empty results when not configured.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

from backend.config import settings
from backend.services.aggregator.schwab_connector import SchwabConnector

logger = logging.getLogger(__name__)

BASE_URL = "https://api.schwabapi.com/trader/v1"
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


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
        """Refresh token if we get 401. Returns False if refresh fails."""
        if not self._refresh_token or not self.connected:
            return False
        try:
            connector = SchwabConnector()
            tokens = await connector.refresh_tokens(self._refresh_token)
            self._access_token = tokens.get("access_token")
            self._refresh_token = tokens.get("refresh_token", self._refresh_token)
            if self._access_token:
                return True
        except Exception as e:
            logger.error("Schwab API: token refresh failed: %s", e)
        return False

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Perform authenticated request. On 401, refresh and retry once.
        Returns parsed JSON or None on failure.
        """
        if not self.connected or not self._access_token:
            return None

        url = f"{BASE_URL}{path}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        async def _do_request(token: str) -> tuple[int, Optional[dict]]:
            h = {"Authorization": f"Bearer {token}"}
            async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT) as session:
                async with session.get(url, headers=h, params=params) as resp:
                    try:
                        data = await resp.json() if resp.content_length else None
                    except Exception:
                        data = None
                    return resp.status, data

        status, data = await _do_request(self._access_token)
        if status == 401:
            if await self._ensure_token() and self._access_token:
                status, data = await _do_request(self._access_token)
        if status != 200:
            logger.warning("Schwab API %s %s: status=%s", method, path, status)
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
        return hv

    async def get_positions(self, account_number: str) -> List[Dict[str, Any]]:
        """
        GET /accounts/{accountHash}/positions.
        Returns list of position dicts with symbol, quantity, average_cost, total_cost_basis.
        Returns empty list when not configured.
        """
        if not self.connected or not self._access_token:
            logger.debug("Schwab API: get_positions skipped (not connected)")
            return []

        account_hash = await self._resolve_account_hash(account_number)
        if not account_hash:
            return []

        data = await self._request("GET", f"/accounts/{account_hash}/positions")
        if not data:
            return []

        positions_raw = data.get("positions") if isinstance(data, dict) else (data if isinstance(data, list) else [])
        if not isinstance(positions_raw, list):
            return []

        results = []
        for p in positions_raw:
            if not isinstance(p, dict):
                continue
            inst = p.get("instrument") or {}
            symbol = (inst.get("symbol") or p.get("symbol") or "").upper()
            if not symbol:
                continue
            qty = float(p.get("longQuantity") or p.get("quantity") or 0) - float(p.get("shortQuantity") or 0)
            avg_cost = None
            cost_basis = None
            if "averageCost" in p:
                avg_cost = float(p["averageCost"])
            if "currentDayCost" in p:
                avg_cost = float(p["currentDayCost"]) if avg_cost is None else avg_cost
            if "cost" in p:
                cost_basis = float(p["cost"])
            if "marketValue" in p and qty != 0 and avg_cost is None:
                avg_cost = float(p["marketValue"]) / abs(qty)
            results.append({
                "symbol": symbol,
                "quantity": qty,
                "average_cost": avg_cost,
                "total_cost_basis": cost_basis,
            })
        return results

    async def get_transactions(
        self, account_number: str, days: int = 365
    ) -> List[Dict[str, Any]]:
        """
        GET /accounts/{accountHash}/transactions with start_date/end_date.
        Schwab limits to 60 days; we use min(days, 60) for the request.
        Returns empty list when not configured.
        """
        if not self.connected or not self._access_token:
            logger.debug("Schwab API: get_transactions skipped (not connected)")
            return []

        account_hash = await self._resolve_account_hash(account_number)
        if not account_hash:
            return []

        # Schwab API typically limits transactions to 60 days
        effective_days = min(days, 60)
        end = datetime.utcnow()
        start = end - timedelta(days=effective_days)
        params = {
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
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
            commission = 0.0
            if transfer_items and isinstance(transfer_items, list):
                item = transfer_items[0] if transfer_items else {}
                inst = item.get("instrument") or {}
                qty = float(item.get("amount", 0) or 0)
                price = float(item.get("price", 0) or 0)
                commission = float(item.get("cost", 0) or 0)
            if not inst:
                inst = t.get("instrument") or {}
            symbol = (inst.get("symbol") or t.get("symbol") or "").upper()
            results.append({
                "id": str(t.get("activityId") or t.get("transactionId") or t.get("id") or ""),
                "account_number": account_number,
                "symbol": symbol,
                "action": t.get("type", t.get("transactionType", "")),
                "quantity": qty or float(t.get("quantity", 0) or 0),
                "price": price or float(t.get("price", 0) or 0),
                "amount": net_amt,
                "commission": commission or float(t.get("commission", 0) or 0),
                "date": t.get("tradeDate") or t.get("settlementDate") or t.get("transactionDate") or t.get("date"),
                "description": t.get("description") or "",
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

        # Balances may be nested
        bal = data.get("securitiesAccount", {}).get("currentBalances") or data.get("currentBalances") or {}
        if not isinstance(bal, dict):
            return {}

        return {
            "cash_balance": float(bal.get("cashBalance", 0) or 0),
            "net_liquidating_value": float(bal.get("liquidationValue", bal.get("netLiquidatingValue", 0)) or 0),
            "equity_buying_power": float(bal.get("buyingPower", 0) or 0),
        }

    async def get_options_positions(self, account_number: str) -> List[Dict[str, Any]]:
        """Extract option positions from the full positions response."""
        if not self.connected or not self._access_token:
            return []

        account_hash = await self._resolve_account_hash(account_number)
        if not account_hash:
            return []

        data = await self._request("GET", f"/accounts/{account_hash}/positions")
        if not data:
            return []

        positions_raw = data.get("positions") if isinstance(data, dict) else (data if isinstance(data, list) else [])
        if not isinstance(positions_raw, list):
            return []

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
            results.append({
                "symbol": symbol,
                "option_symbol": option_symbol,
                "quantity": qty,
                "strike": float(inst.get("strikePrice") or 0),
                "expiration": inst.get("expirationDate") or inst.get("expiry") or "",
                "put_call": (inst.get("putCall") or inst.get("optionType") or "").upper(),
                "average_cost": float(p.get("averageCost", 0) or 0),
                "market_value": float(p.get("marketValue", 0) or 0),
            })
        return results

    async def place_order(
        self, account_number: str, order: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Place order - not implemented (read-only client)."""
        logger.warning("Schwab API: place_order not implemented (read-only)")
        return {"status": "not_implemented"}
