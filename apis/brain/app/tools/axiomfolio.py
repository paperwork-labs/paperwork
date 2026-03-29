"""AxiomFolio proxy tools — Tier 0 reads, Tier 2 position edits, Tier 3 order execution.

See docs/AXIOMFOLIO_INTEGRATION.md for endpoint contract."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings
from app.services.pii import scrub_pii

logger = logging.getLogger(__name__)


def _axf_client() -> httpx.AsyncClient:
    headers: dict[str, str] = {}
    if settings.AXIOMFOLIO_API_KEY:
        headers["X-API-Key"] = settings.AXIOMFOLIO_API_KEY
    return httpx.AsyncClient(
        base_url=settings.AXIOMFOLIO_API_URL.rstrip("/"),
        headers=headers,
        timeout=15.0,
    )


def _scrub_json_blob(data: Any) -> str:
    return scrub_pii(json.dumps(data, indent=2, default=str))


def _envelope_error(body: dict[str, Any], status: int) -> str | None:
    if body.get("success") is True:
        return None
    err = body.get("error")
    if err is None and status >= 400:
        return f"Request failed (HTTP {status})."
    if err is not None:
        return f"Error: {err}"
    return None


def _http_error_message(exc: httpx.HTTPStatusError) -> str:
    try:
        body = exc.response.json()
        msg = _envelope_error(body, exc.response.status_code)
        if msg:
            return msg
    except Exception:
        logger.debug("axiomfolio non-json error body", exc_info=True)
    return f"HTTP {exc.response.status_code}: {exc.response.text[:500]}"


def _format_scan_summary(data: Any) -> str:
    if data is None:
        return "Scan completed; no data returned."
    if isinstance(data, list):
        n = len(data)
        preview = _scrub_json_blob(data[:10])
        more = f"\n… and {n - 10} more." if n > 10 else ""
        return f"Candidates ({n}):\n{preview}{more}"
    if isinstance(data, dict):
        if "candidates" in data and isinstance(data["candidates"], list):
            return _format_scan_summary(data["candidates"])
        return f"Scan result:\n{_scrub_json_blob(data)}"
    return scrub_pii(str(data))


def _format_portfolio_summary(data: Any) -> str:
    if data is None:
        return "No portfolio data."
    if not isinstance(data, dict):
        return _scrub_json_blob(data)

    lines: list[str] = ["Portfolio (account identifiers scrubbed)"]

    for key in ("equity", "net_liquidation", "total_value", "cash"):
        if key in data and data[key] is not None:
            lines.append(f"  • {key.replace('_', ' ').title()}: {data[key]}")

    for key in ("day_pnl", "total_pnl", "unrealized_pnl", "realized_pnl"):
        if key in data and data[key] is not None:
            lines.append(f"  • {key.replace('_', ' ').title()}: {data[key]}")

    positions = data.get("positions") or data.get("holdings") or []
    if isinstance(positions, list) and positions:
        lines.append(f"  • Positions: {len(positions)}")
        for i, pos in enumerate(positions[:8]):
            if isinstance(pos, dict):
                sym = pos.get("symbol") or pos.get("ticker") or "?"
                qty = pos.get("quantity") or pos.get("qty") or pos.get("shares")
                pnl = pos.get("unrealized_pnl") or pos.get("pnl")
                chunk = f"    — {sym}"
                if qty is not None:
                    chunk += f" qty={qty}"
                if pnl is not None:
                    chunk += f" unrealized_pnl={pnl}"
                lines.append(chunk)
            else:
                lines.append(f"    — {pos}")
        if len(positions) > 8:
            lines.append(f"    … +{len(positions) - 8} more positions")

    exposure = data.get("exposure") or data.get("gross_exposure")
    if exposure is not None:
        lines.append(f"  • Exposure: {exposure}")

    detail = _scrub_json_blob(data)
    lines.append("")
    lines.append("Full payload (scrubbed):")
    lines.append(detail)
    return "\n".join(lines)


def _format_risk_summary(data: Any) -> str:
    if data is None:
        return "No risk data."
    if not isinstance(data, dict):
        return _scrub_json_blob(data)

    lines: list[str] = ["Risk status (scrubbed)"]
    for key in (
        "portfolio_heat",
        "var",
        "max_drawdown",
        "leverage",
        "margin_usage",
        "buying_power",
    ):
        if key in data and data[key] is not None:
            lines.append(f"  • {key.replace('_', ' ').title()}: {data[key]}")

    gates = data.get("gates") or data.get("risk_gates")
    if isinstance(gates, list) and gates:
        lines.append("  • Gates:")
        for g in gates[:12]:
            lines.append(f"    — {g}")
        if len(gates) > 12:
            lines.append(f"    … +{len(gates) - 12} more")

    lines.append("")
    lines.append(_scrub_json_blob(data))
    return "\n".join(lines)


def _format_analysis_summary(symbol: str, data: Any) -> str:
    header = f"Stage analysis: {symbol.upper()}"
    if data is None:
        return f"{header}\nNo analysis payload returned."
    if isinstance(data, dict):
        parts = [header, _scrub_json_blob(data)]
        return "\n".join(parts)
    return f"{header}\n{scrub_pii(str(data))}"


def _format_watchlist_summary(data: Any) -> str:
    if data is None:
        return "Watchlist is empty or unavailable."
    if isinstance(data, list):
        syms = []
        for item in data:
            if isinstance(item, dict):
                syms.append(str(item.get("symbol") or item.get("ticker") or item))
            else:
                syms.append(str(item))
        return "Watchlist: " + ", ".join(syms) if syms else _scrub_json_blob(data)
    if isinstance(data, dict):
        items = data.get("symbols") or data.get("items") or data.get("watchlist")
        if isinstance(items, list):
            return _format_watchlist_summary(items)
        return _scrub_json_blob(data)
    return scrub_pii(str(data))


async def scan_market() -> str:
    """GET /api/v1/scans/run — Tier 0. Run scans, return candidates."""
    try:
        async with _axf_client() as client:
            res = await client.get("/api/v1/scans/run")
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("scan_market HTTP error: %s", e)
        return _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("scan_market request failed: %s", e)
        return f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("scan_market failed: %s", e)
        return f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return err
    return _format_scan_summary(body.get("data"))


async def get_portfolio() -> str:
    """GET /api/v1/portfolio — Tier 0. Positions, P&L, exposure (PII scrubbed)."""
    try:
        async with _axf_client() as client:
            res = await client.get("/api/v1/portfolio")
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("get_portfolio HTTP error: %s", e)
        return _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("get_portfolio request failed: %s", e)
        return f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("get_portfolio failed: %s", e)
        return f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return err
    return _format_portfolio_summary(body.get("data"))


async def stage_analysis(symbol: str) -> str:
    """GET /api/v1/analysis/{symbol} — Tier 0. Technical / stage analysis."""
    sym = symbol.strip().upper()
    if not sym:
        return "Error: symbol is required."

    try:
        async with _axf_client() as client:
            res = await client.get(f"/api/v1/analysis/{sym}")
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("stage_analysis HTTP error: %s", e)
        return _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("stage_analysis request failed: %s", e)
        return f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("stage_analysis failed: %s", e)
        return f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return err
    return _format_analysis_summary(sym, body.get("data"))


async def get_risk_status() -> str:
    """GET /api/v1/portfolio/risk — Tier 0. Risk metrics and gates (scrubbed)."""
    try:
        async with _axf_client() as client:
            res = await client.get("/api/v1/portfolio/risk")
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("get_risk_status HTTP error: %s", e)
        return _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("get_risk_status request failed: %s", e)
        return f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("get_risk_status failed: %s", e)
        return f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return err
    return _format_risk_summary(body.get("data"))


async def get_watchlist() -> str:
    """GET /api/v1/watchlist — Tier 0. Tracked symbols and alerts."""
    try:
        async with _axf_client() as client:
            res = await client.get("/api/v1/watchlist")
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("get_watchlist HTTP error: %s", e)
        return _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("get_watchlist request failed: %s", e)
        return f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("get_watchlist failed: %s", e)
        return f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return err
    return scrub_pii(_format_watchlist_summary(body.get("data")))


async def execute_trade(
    symbol: str,
    side: str,
    quantity: int,
    order_type: str = "limit",
    price: float | None = None,
) -> str:
    """POST /api/v1/orders — Tier 3. Submits a real order when AxiomFolio is live."""
    sym = symbol.strip().upper()
    if not sym:
        return "Error: symbol is required."
    if quantity <= 0:
        return "Error: quantity must be positive."

    side_norm = side.strip().lower()
    if side_norm not in ("buy", "sell", "short", "cover"):
        return "Error: side should be buy, sell, short, or cover."

    payload: dict[str, Any] = {
        "symbol": sym,
        "side": side_norm,
        "quantity": quantity,
        "order_type": order_type.strip().lower(),
    }
    if price is not None:
        payload["price"] = price

    warning = (
        "⚠️ Tier 3 — AxiomFolio may execute a real trade against your broker "
        "when this environment is connected to live trading. "
        "Human approval is required in production per integration policy.\n\n"
    )

    try:
        async with _axf_client() as client:
            res = await client.post("/api/v1/orders", json=payload)
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("execute_trade HTTP error: %s", e)
        return warning + _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("execute_trade request failed: %s", e)
        return warning + f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("execute_trade failed: %s", e)
        return warning + f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return warning + err
    summary = _scrub_json_blob(body.get("data"))
    return warning + f"Order accepted / queued:\n{summary}"


async def modify_position(
    position_id: str,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> str:
    """PUT /api/v1/positions/{id} — Tier 2. Update stops and targets."""
    pid = position_id.strip()
    if not pid:
        return "Error: position_id is required."
    if stop_loss is None and take_profit is None:
        return "Error: provide stop_loss and/or take_profit to update."

    payload: dict[str, Any] = {}
    if stop_loss is not None:
        payload["stop_loss"] = stop_loss
    if take_profit is not None:
        payload["take_profit"] = take_profit

    # Avoid path injection: alphanumeric, hyphen, underscore only (e.g. UUIDs)
    safe_id = "".join(c for c in pid if c.isalnum() or c in "-_")
    if safe_id != pid:
        return "Error: position_id contains invalid characters."

    try:
        async with _axf_client() as client:
            res = await client.put(f"/api/v1/positions/{safe_id}", json=payload)
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("modify_position HTTP error: %s", e)
        return _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("modify_position request failed: %s", e)
        return f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("modify_position failed: %s", e)
        return f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return err
    return f"Position updated:\n{_scrub_json_blob(body.get('data'))}"
