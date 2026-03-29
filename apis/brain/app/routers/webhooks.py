"""Inbound webhooks — AxiomFolio portfolio and trade events into Brain memory."""

from __future__ import annotations

import hmac
import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services import memory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Event names (dot form). Aliases with underscores are normalized in _normalize_event.
KNOWN_EVENTS = frozenset({
    "trade.executed",
    "trade.rejected",
    "approval.needed",
    "risk.alert",
    "portfolio.update",
})

DEFAULT_WEBHOOK_ORG_ID = "paperwork-labs"


def _verify_axiomfolio_webhook(
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
) -> None:
    expected = settings.AXIOMFOLIO_WEBHOOK_SECRET or settings.AXIOMFOLIO_API_KEY
    if not expected:
        if settings.ENVIRONMENT == "development":
            logger.warning(
                "Webhook secret not set; accepting AxiomFolio webhooks without auth (dev only)"
            )
            return
        raise HTTPException(
            status_code=503,
            detail="AxiomFolio webhook secret not configured",
        )
    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Webhook-Secret")


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
    """Human approval pending (e.g. Tier-3 execute_trade)."""

    summary: str | None = None
    symbol: str | None = None
    side: str | None = None
    quantity: float | None = None
    tier: int | None = None
    proposal_id: str | None = None


class RiskAlertData(BaseModel):
    severity: str | None = None
    message: str | None = None
    gate: str | None = None
    symbol: str | None = None


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
        "risk.alert": RiskAlertData,
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
    elif event_norm == "approval.needed" and isinstance(parsed, ApprovalNeededData):
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
    elif event_norm == "risk.alert" and isinstance(parsed, RiskAlertData):
        sev = f"[{parsed.severity}] " if parsed.severity else ""
        msg = parsed.message or parsed.gate or parsed.symbol or "risk event"
        summary = f"AxiomFolio: risk alert — {sev}{msg}{ts_suffix}"
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
    importance = 0.65 if event_norm in ("risk.alert", "approval.needed") else 0.5
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
