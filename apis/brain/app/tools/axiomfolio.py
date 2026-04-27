"""AxiomFolio proxy tools — Tier 0 reads, Tier 2 previews, Tier 3 order execution.

This client targets AxiomFolio's Brain integration API at /api/v1/tools/*,
authenticated via the X-Brain-Api-Key header.

For end-to-end integration details, refer to AxiomFolio's current Brain
integration documentation (docs/PAPERWORK_HANDOFF.md in the AxiomFolio repo).
Note: the legacy docs/AXIOMFOLIO_INTEGRATION.md in this repository describes
an older X-API-Key, non-/tools/ contract and is not authoritative for this module."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings
from app.services.pii import scrub_pii

logger = logging.getLogger(__name__)


def _axf_client() -> httpx.AsyncClient:
    """Create AxiomFolio client with X-Brain-Api-Key auth header."""
    headers: dict[str, str] = {}
    if settings.AXIOMFOLIO_API_KEY:
        headers["X-Brain-Api-Key"] = settings.AXIOMFOLIO_API_KEY
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
        for pos in positions[:8]:
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


def _format_regime_summary(data: Any) -> str:
    if data is None:
        return "No regime data."
    if isinstance(data, dict):
        regime = data.get("regime") or data.get("current_regime") or "Unknown"
        lines = [f"Market Regime: {regime}"]
        for key in ("description", "recommendation", "risk_level"):
            if data.get(key):
                lines.append(f"  • {key.replace('_', ' ').title()}: {data[key]}")
        return "\n".join(lines)
    return scrub_pii(str(data))


async def scan_market() -> str:
    """GET /api/v1/tools/scan — Tier 0. Run scans, return candidates."""
    try:
        async with _axf_client() as client:
            res = await client.get("/api/v1/tools/scan")
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
    """GET /api/v1/tools/portfolio — Tier 0. Positions, P&L, exposure (PII scrubbed)."""
    try:
        async with _axf_client() as client:
            res = await client.get("/api/v1/tools/portfolio")
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
    """GET /api/v1/tools/stage/{symbol} — Tier 0. Technical / stage analysis."""
    sym = symbol.strip().upper()
    if not sym:
        return "Error: symbol is required."

    try:
        async with _axf_client() as client:
            res = await client.get(f"/api/v1/tools/stage/{sym}")
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
    """GET /api/v1/tools/risk — Tier 0. Circuit breaker status and risk metrics."""
    try:
        async with _axf_client() as client:
            res = await client.get("/api/v1/tools/risk")
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


async def get_market_regime() -> str:
    """GET /api/v1/tools/regime — Tier 0. Current market regime (R1-R5)."""
    try:
        async with _axf_client() as client:
            res = await client.get("/api/v1/tools/regime")
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("get_market_regime HTTP error: %s", e)
        return _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("get_market_regime request failed: %s", e)
        return f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("get_market_regime failed: %s", e)
        return f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return err
    return _format_regime_summary(body.get("data"))


async def preview_trade(
    symbol: str,
    side: str,
    quantity: int,
    order_type: str = "limit",
    price: float | None = None,
) -> str:
    """POST /api/v1/tools/preview-trade — Tier 2. Create PREVIEW order for approval.

    Returns order_id for use in approve_trade/reject_trade/execute_trade.
    """
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

    try:
        async with _axf_client() as client:
            res = await client.post("/api/v1/tools/preview-trade", json=payload)
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("preview_trade HTTP error: %s", e)
        return _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("preview_trade request failed: %s", e)
        return f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("preview_trade failed: %s", e)
        return f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return err

    data = body.get("data", {})
    order_id = data.get("order_id") or data.get("id")
    status = data.get("status", "PREVIEW")
    summary = _scrub_json_blob(data)

    result = f"Trade preview created:\n{summary}\n\n"
    if order_id:
        result += f"Order ID: {order_id}\n"
    result += f"Status: {status}\n"

    if status == "PENDING_APPROVAL":
        result += "\n⚠️ This trade requires approval. Use approve_trade(order_id) or reject_trade(order_id)."  # noqa: E501
    else:
        result += "\nUse execute_trade(order_id) to submit this order."

    return result


async def approve_trade(order_id: int) -> str:
    """POST /api/v1/tools/approve-trade — Tier 3. Approve a pending order.

    Call after preview_trade when status is PENDING_APPROVAL.
    """
    if order_id <= 0:
        return "Error: order_id must be a positive integer."

    payload = {
        "order_id": order_id,
    }

    try:
        async with _axf_client() as client:
            res = await client.post("/api/v1/tools/approve-trade", json=payload)
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("approve_trade HTTP error: %s", e)
        return _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("approve_trade request failed: %s", e)
        return f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("approve_trade failed: %s", e)
        return f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return err

    data = body.get("data", {})
    return f"✅ Order {order_id} approved.\n{_scrub_json_blob(data)}\n\nUse execute_trade({order_id}) to submit."  # noqa: E501


async def reject_trade(order_id: int, reason: str = "") -> str:
    """POST /api/v1/tools/reject-trade — Tier 3. Reject a pending order.

    Call after preview_trade to cancel without executing.
    """
    if order_id <= 0:
        return "Error: order_id must be a positive integer."

    payload: dict[str, Any] = {
        "order_id": order_id,
    }
    if reason:
        payload["reason"] = reason

    try:
        async with _axf_client() as client:
            res = await client.post("/api/v1/tools/reject-trade", json=payload)
            res.raise_for_status()
            body = res.json()
    except httpx.HTTPStatusError as e:
        logger.warning("reject_trade HTTP error: %s", e)
        return _http_error_message(e)
    except httpx.RequestError as e:
        logger.warning("reject_trade request failed: %s", e)
        return f"Could not reach AxiomFolio: {e}"
    except Exception as e:
        logger.warning("reject_trade failed: %s", e)
        return f"Unexpected error: {e}"

    err = _envelope_error(body, 200)
    if err:
        return err

    return f"❌ Order {order_id} rejected." + (f" Reason: {reason}" if reason else "")


async def execute_trade(order_id: int) -> str:
    """POST /api/v1/tools/execute-trade — Tier 3. Execute an approved order.

    Call after preview_trade (and approve_trade if required).
    This submits a REAL trade to the broker.
    """
    if order_id <= 0:
        return "Error: order_id must be a positive integer."

    warning = (
        "⚠️ Tier 3 — This will execute a REAL trade against the broker "
        "when AxiomFolio is connected to live trading.\n\n"
    )

    payload = {"order_id": order_id}

    try:
        async with _axf_client() as client:
            res = await client.post("/api/v1/tools/execute-trade", json=payload)
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

    data = body.get("data", {})
    status = data.get("status", "SUBMITTED")
    summary = _scrub_json_blob(data)
    return f"{warning}Order {order_id} submitted ({status}):\n{summary}"


async def get_watchlist() -> str:
    """AxiomFolio watchlist is not in the Brain tools API. Use scan_market instead."""
    return "Watchlist endpoint not available in current API. Use scan_market() to find candidates."


async def modify_position(
    _position_id: str,
    _stop_loss: float | None = None,
    _take_profit: float | None = None,
) -> str:
    """Position modification not available in current Brain tools API.

    Use preview_trade to create a closing order instead.
    """
    return (
        "Position modification not available in current API. "
        "To adjust stops or close a position, use preview_trade() to create a closing order."
    )
