"""HTTP client for Coinbase v2 data API (wallet accounts + transactions).

medallion: bronze
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from backend.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coinbase.com"


class CoinbaseAPIError(Exception):
    """Coinbase API failure with retry hint."""

    def __init__(
        self,
        message: str,
        *,
        permanent: bool,
        status: Optional[int] = None,
        path: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.permanent = permanent
        self.status = status
        self.path = path


def _classify_permanent(status: int) -> bool:
    if status == 429:
        return False
    return 400 <= status < 500


def _data_rows(body: Dict[str, Any], *, context: str) -> List[Dict[str, Any]]:
    block = body.get("data")
    if block is None:
        return []
    if isinstance(block, list):
        return [x for x in block if isinstance(x, dict)]
    if isinstance(block, dict):
        return [block]
    raise CoinbaseAPIError(
        f"Coinbase {context} envelope has unexpected data type "
        f"{type(block).__name__}",
        permanent=True,
    )


def _next_page_path(pagination: Any) -> Optional[str]:
    if not isinstance(pagination, dict):
        return None
    raw = pagination.get("next_uri")
    if not raw or not isinstance(raw, str):
        return None
    nxt = raw.strip()
    if not nxt:
        return None
    if nxt.startswith("http://") or nxt.startswith("https://"):
        parsed = urlparse(nxt)
        base = urlparse(BASE_URL)
        p_host = (parsed.hostname or "").lower()
        b_host = (base.hostname or "").lower()
        if p_host != b_host:
            raise CoinbaseAPIError(
                f"unexpected pagination host: {parsed.hostname!r}",
                permanent=True,
            )
        path = parsed.path or ""
        if not path.startswith("/"):
            path = f"/{path}"
        if parsed.query:
            return f"{path}?{parsed.query}"
        return path
    if nxt.startswith("/"):
        return nxt
    return f"/{nxt}"


class CoinbaseBronzeClient:
    """Bearer-authenticated client for ``/v2`` wallet endpoints."""

    def __init__(
        self,
        *,
        access_token: str,
        base_url: str = BASE_URL,
        session: Optional[requests.Session] = None,
        timeout_s: Optional[float] = None,
    ) -> None:
        if not access_token:
            raise CoinbaseAPIError(
                "Coinbase client requires a non-empty access_token",
                permanent=True,
            )
        self._token = access_token
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._timeout_s = (
            timeout_s
            if timeout_s is not None
            else getattr(settings, "COINBASE_OAUTH_REQUEST_TIMEOUT_S", 15.0)
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        for attempt in range(2):
            try:
                resp = self._session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    timeout=self._timeout_s,
                )
            except requests.RequestException as exc:
                logger.warning("coinbase client: network failure on %s: %s", path, exc)
                raise CoinbaseAPIError(
                    f"network failure calling Coinbase {path}: {exc}",
                    permanent=False,
                    path=path,
                ) from exc

            status = resp.status_code
            if status == 429 and attempt == 0:
                time.sleep(1.5)
                continue
            if status >= 400:
                logger.warning(
                    "coinbase client: HTTP %s on %s body=%s",
                    status,
                    path,
                    (resp.text or "")[:200],
                )
                raise CoinbaseAPIError(
                    f"Coinbase {path} returned HTTP {status}: "
                    f"{(resp.text or '')[:200]}",
                    permanent=_classify_permanent(status),
                    status=status,
                    path=path,
                )

            try:
                body = resp.json() if resp.content else {}
            except ValueError as exc:
                raise CoinbaseAPIError(
                    f"Coinbase {path} returned non-JSON: " f"{(resp.text or '')[:200]}",
                    permanent=True,
                    status=status,
                    path=path,
                ) from exc

            if not isinstance(body, dict):
                raise CoinbaseAPIError(
                    f"Coinbase {path} unexpected root {type(body).__name__}",
                    permanent=True,
                    status=status,
                    path=path,
                )
            return body

        raise CoinbaseAPIError(
            f"Coinbase {path} rate-limited after retry",
            permanent=False,
            status=429,
            path=path,
        )

    def get_user(self) -> Dict[str, Any]:
        body = self._request_json("GET", "/v2/user")
        data = body.get("data")
        if not isinstance(data, dict):
            raise CoinbaseAPIError(
                "/v2/user missing data object",
                permanent=True,
                path="/v2/user",
            )
        return data

    def list_all_accounts(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        path: Optional[str] = "/v2/accounts?limit=100"
        while path:
            body = self._request_json("GET", path)
            out.extend(_data_rows(body, context="accounts"))
            path = _next_page_path(body.get("pagination"))
        return out

    def list_transactions_for_account(self, account_id: str) -> List[Dict[str, Any]]:
        if not account_id:
            raise CoinbaseAPIError(
                "list_transactions_for_account requires account_id",
                permanent=True,
            )
        out: List[Dict[str, Any]] = []
        path: Optional[str] = f"/v2/accounts/{account_id}/transactions?limit=100"
        while path:
            body = self._request_json("GET", path)
            out.extend(_data_rows(body, context="transactions"))
            path = _next_page_path(body.get("pagination"))
        return out


__all__ = ["CoinbaseAPIError", "CoinbaseBronzeClient", "BASE_URL"]
