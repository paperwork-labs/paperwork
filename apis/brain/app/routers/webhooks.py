"""Inbound webhooks — AxiomFolio portfolio and trade events into Brain memory."""

from __future__ import annotations

import hmac
import json
import logging
from typing import Any, Literal

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services import memory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Event names (dot form). Aliases with underscores are normalized in _normalize_event.
# AxiomFolio sends: trade_executed, position_closed, stop_triggered, risk_gate_activated,
# scan_alert, approval_required — all normalized to dot form.
KNOWN_EVENTS = frozenset({
    "trade.executed",
    "trade.rejected",
    "position.closed",
    "stop.triggered",
    "approval.required",  # AxiomFolio sends approval_required when Tier 3 trade needs approval
    "approval.needed",    # Alias kept for backwards compatibility
    "risk.alert",
    "risk.gate.activated",  # AxiomFolio sends risk_gate_activated
    "scan.alert",           # AxiomFolio sends scan_alert
    "portfolio.update",
})

DEFAULT_WEBHOOK_ORG_ID = "paperwork-labs"


async def _verify_axiomfolio_webhook(request: Request) -> None:
    """Verify AxiomFolio webhook via HMAC-SHA256 signature.

    AxiomFolio sends: X-Webhook-Signature: sha256=<hex>
    where hex = hmac.new(secret, body, sha256).hexdigest()
    """
    expected_secret = settings.AXIOMFOLIO_WEBHOOK_SECRET
    if not expected_secret:
        if settings.ENVIRONMENT == "development":
            logger.warning(
                "Webhook secret not set; accepting AxiomFolio webhooks without auth (dev only)"
            )
            return
        raise HTTPException(
            status_code=503,
            detail="AxiomFolio webhook secret not configured",
        )

    signature_header = request.headers.get("X-Webhook-Signature", "")
    if not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=401,
            detail="Missing or malformed X-Webhook-Signature header",
        )

    body = await request.body()
    expected_sig = hmac.new(
        expected_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    received_sig = signature_header[7:]  # strip "sha256=" prefix

    if not hmac.compare_digest(expected_sig, received_sig):
        logger.warning("AxiomFolio webhook signature mismatch")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _normalize_event(event: str) -> str:
    """Map trade_executed / trade.executed to canonical dot form."""
    e = event.strip().lower()
    return e.replace("_", ".")


class RawWebhookData(BaseModel):
    """Fallback / unknown event shapes — preserve all keys."""

    model_config = ConfigDict(extra="allow")


class TradeExecutedData(BaseModel):
    """Payload data for trade.executed (and legacy trade_executed)."""

    model_config = ConfigDict(extra="ignore")

    symbol: str | None = None
    side: str | None = None
    quantity: float | None = None
    price: float | None = None
    pnl_impact: float | None = None


class TradeRejectedData(BaseModel):
    symbol: str | None = None
    reason: str | None = None
    side: str | None = None
    quantity: float | None = None


class ApprovalNeededData(BaseModel):
    """Human approval pending (e.g. Tier-3 execute_trade).

    AxiomFolio sends approval_required with order_id, symbol, side, quantity.
    """

    order_id: int | None = None
    summary: str | None = None
    symbol: str | None = None
    side: str | None = None
    quantity: float | None = None
    price: float | None = None
    tier: int | None = None
    proposal_id: str | None = None


class RiskAlertData(BaseModel):
    """Risk gate triggered or risk alert."""

    severity: str | None = None
    message: str | None = None
    gate: str | None = None
    symbol: str | None = None
    details: str | None = None


class ScanAlertData(BaseModel):
    """Scan found candidates."""

    candidates: list[dict[str, Any]] | None = None
    scan_name: str | None = None
    count: int | None = None


class StopTriggeredData(BaseModel):
    """Stop loss hit."""

    symbol: str | None = None
    position_id: int | None = None
    stop_price: float | None = None
    exit_price: float | None = None


class PositionClosedData(BaseModel):
    """Position fully closed."""

    symbol: str | None = None
    position_id: int | None = None
    pnl: float | None = None
    reason: str | None = None


class PortfolioUpdateData(BaseModel):
    """P&L / exposure snapshot."""

    pnl: float | None = None
    pnl_ytd: float | None = None
    total_value: float | None = None
    currency: str | None = "USD"
    note: str | None = None


class AxiomFolioWebhookPayload(BaseModel):
    """Envelope AxiomFolio POSTs to Brain."""

    event: str = Field(..., description="e.g. trade.executed, trade_executed")
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None
    organization_id: str | None = Field(
        default=None,
        description="Brain organization_id; defaults to paperwork-labs if omitted",
    )


def _parse_data_for_event(
    event_norm: str, data: dict[str, Any]
) -> BaseModel:
    parsers: dict[str, type[BaseModel]] = {
        "trade.executed": TradeExecutedData,
        "trade.rejected": TradeRejectedData,
        "approval.needed": ApprovalNeededData,
        "approval.required": ApprovalNeededData,  # AxiomFolio sends this
        "risk.alert": RiskAlertData,
        "risk.gate.activated": RiskAlertData,  # AxiomFolio sends this
        "scan.alert": ScanAlertData,
        "stop.triggered": StopTriggeredData,
        "position.closed": PositionClosedData,
        "portfolio.update": PortfolioUpdateData,
    }
    model_cls = parsers.get(event_norm, RawWebhookData)
    try:
        return model_cls.model_validate(data)
    except Exception as e:
        logger.warning(
            "Webhook data shape mismatch for event=%s: %s; storing raw dict",
            event_norm,
            e,
        )
        return RawWebhookData.model_validate(data)


def _episode_summary_and_context(
    raw_event: str,
    event_norm: str,
    data: dict[str, Any],
    timestamp: str | None,
) -> tuple[str, str, float]:
    parsed = _parse_data_for_event(event_norm, data)
    ts_suffix = f" ({timestamp})" if timestamp else ""

    if event_norm == "trade.executed" and isinstance(parsed, TradeExecutedData):
        parts = [
            p
            for p in [
                (parsed.side or "").upper() if parsed.side else None,
                str(parsed.quantity) if parsed.quantity is not None else None,
                parsed.symbol,
                f"@ {parsed.price}" if parsed.price is not None else None,
            ]
            if p
        ]
        core = " ".join(parts) if parts else json.dumps(data, default=str)[:200]
        summary = f"AxiomFolio: trade executed — {core}{ts_suffix}"
    elif event_norm == "trade.rejected" and isinstance(parsed, TradeRejectedData):
        sym = parsed.symbol or "unknown symbol"
        reason = parsed.reason or "no reason given"
        summary = f"AxiomFolio: trade rejected — {sym}: {reason}{ts_suffix}"
    elif event_norm in ("approval.needed", "approval.required") and isinstance(parsed, ApprovalNeededData):
        if parsed.summary:
            core = parsed.summary
        else:
            core = " ".join(
                p
                for p in [
                    (parsed.side or "").upper() if parsed.side else None,
                    str(parsed.quantity) if parsed.quantity is not None else None,
                    parsed.symbol,
                ]
                if p
            ) or "pending approval"
        summary = f"AxiomFolio: approval needed — {core}{ts_suffix}"
    elif event_norm in ("risk.alert", "risk.gate.activated") and isinstance(parsed, RiskAlertData):
        sev = f"[{parsed.severity}] " if parsed.severity else ""
        msg = parsed.message or parsed.gate or parsed.details or parsed.symbol or "risk event"
        summary = f"AxiomFolio: risk alert — {sev}{msg}{ts_suffix}"
    elif event_norm == "scan.alert" and isinstance(parsed, ScanAlertData):
        count = parsed.count or (len(parsed.candidates) if parsed.candidates else 0)
        scan_name = parsed.scan_name or "scan"
        summary = f"AxiomFolio: {scan_name} found {count} candidates{ts_suffix}"
    elif event_norm == "stop.triggered" and isinstance(parsed, StopTriggeredData):
        exit_str = str(parsed.exit_price) if parsed.exit_price is not None else "?"
        summary = f"AxiomFolio: stop triggered — {parsed.symbol or 'unknown'} @ {exit_str}{ts_suffix}"
    elif event_norm == "position.closed" and isinstance(parsed, PositionClosedData):
        pnl_str = f" P&L: {parsed.pnl}" if parsed.pnl is not None else ""
        summary = f"AxiomFolio: position closed — {parsed.symbol or 'unknown'}{pnl_str}{ts_suffix}"
    elif event_norm == "portfolio.update" and isinstance(parsed, PortfolioUpdateData):
        bits: list[str] = []
        if parsed.pnl is not None:
            bits.append(f"P&L {parsed.pnl}")
        if parsed.pnl_ytd is not None:
            bits.append(f"YTD {parsed.pnl_ytd}")
        if parsed.total_value is not None:
            bits.append(f"value {parsed.total_value} {parsed.currency or ''}".strip())
        if parsed.note:
            bits.append(parsed.note)
        core = ", ".join(bits) if bits else json.dumps(data, default=str)[:200]
        summary = f"AxiomFolio: portfolio update — {core}{ts_suffix}"
    else:
        summary = f"AxiomFolio webhook: {raw_event}{ts_suffix}"

    envelope = {
        "event": raw_event,
        "event_normalized": event_norm,
        "timestamp": timestamp,
        "data": data,
    }
    full_context = json.dumps(envelope, default=str)
    high_importance_events = ("risk.alert", "risk.gate.activated", "approval.needed", "approval.required", "stop.triggered")
    importance = 0.65 if event_norm in high_importance_events else 0.5
    return summary, full_context, importance


@router.post("/axiomfolio")
async def axiomfolio_webhook(
    body: AxiomFolioWebhookPayload,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_verify_axiomfolio_webhook),
) -> dict[str, Literal[True]]:
    event_norm = _normalize_event(body.event)
    org_id = body.organization_id or DEFAULT_WEBHOOK_ORG_ID

    if event_norm not in KNOWN_EVENTS:
        logger.info(
            "AxiomFolio webhook unknown event type=%s (normalized=%s); storing generic episode",
            body.event,
            event_norm,
        )

    summary, full_context, importance = _episode_summary_and_context(
        body.event,
        event_norm,
        body.data,
        body.timestamp,
    )

    try:
        await memory.store_episode(
            db,
            organization_id=org_id,
            source=f"axiomfolio:webhook:{event_norm}",
            summary=summary,
            full_context=full_context,
            channel="webhook",
            persona="axiomfolio",
            product="axiomfolio",
            source_ref=body.timestamp,
            importance=importance,
            metadata={
                "provider": "axiomfolio",
                "event": body.event,
                "event_normalized": event_norm,
            },
        )
    except Exception as e:
        logger.error(
            "Failed to store AxiomFolio webhook episode (event=%s, org=%s): %s",
            body.event,
            org_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to persist webhook event",
        ) from e

    return {"success": True}
