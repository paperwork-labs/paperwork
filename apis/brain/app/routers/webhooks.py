"""Inbound webhooks — AxiomFolio portfolio/trade events + GitHub PR events.

Track B (Week 1) added the GitHub webhook handler at ``POST /webhooks/github``.
It replaces three GitHub Actions workflows:
- dependabot-auto-approve.yaml
- dependabot-major-triage.yaml
- auto-merge-sweep.yaml (the event-driven half; the cron half was replaced
  by ``app.schedulers.pr_sweep``).
"""

from __future__ import annotations

import hmac
import json
import logging
from typing import Any, Literal

import hashlib

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, get_db
from app.services import memory
from app.services.dependabot_classifier import classify_pr
from app.services.pr_review import review_pr
from app.tools import github as gh_tools

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

    # Track M.2: high-importance AxiomFolio events wake the trading persona.
    # The receiver used to be a silent sink; every risk-gate, approval, and
    # stop-triggered now surfaces in #trading as a narrated Slack post with
    # a link back to the underlying episode. Non-critical events (trades,
    # scans) still just land in memory.
    if event_norm in _TRADING_WAKEUP_EVENTS:
        try:
            await _wake_trading_persona(
                db,
                organization_id=org_id,
                event=body.event,
                event_norm=event_norm,
                data=body.data,
                timestamp=body.timestamp,
                summary=summary,
            )
        except Exception as e:
            # Swallow and log: webhook ingestion must always return 200 to
            # the sender (AxiomFolio) even if the narration path hiccups.
            logger.warning(
                "trading-persona wakeup failed for event=%s org=%s: %s",
                body.event,
                org_id,
                e,
            )

    return {"success": True}


# Events that should wake the `trading` persona and post to #trading.
# Deliberately a subset: ``trade.executed`` and ``position.closed`` are
# noise; the user wants narration on decisions, not on confirmations.
_TRADING_WAKEUP_EVENTS = frozenset({
    "risk.gate.activated",
    "risk.alert",
    "approval.required",
    "approval.needed",
    "stop.triggered",
})


async def _wake_trading_persona(
    db: AsyncSession,
    *,
    organization_id: str,
    event: str,
    event_norm: str,
    data: Any,
    timestamp: str | None,
    summary: str,
) -> None:
    """Track M.2 — post a narrated explanation to #trading via Brain.

    We call our own ``agent.process`` with ``persona_pin='trading'`` so
    the response lands in Brain memory (provenance), gets cost-tracked
    under the trading persona's ceiling, respects PII scrubbing, and
    picks up the trading persona's tone_prefix. Then — because the
    webhook path has no Slack channel context — we use
    ``slack_channel_id`` on the ProcessRequest to let Brain do the
    post in one shot.

    No Slack channel ID configured → noop. No Brain path at all → we
    still stored the episode above, so nothing is lost.
    """
    from app.services import agent  # lazy import: avoids router-time cycle
    from app.redis import get_redis

    channel_id = settings.SLACK_TRADING_CHANNEL_ID or settings.SLACK_ENGINEERING_CHANNEL_ID
    if not channel_id:
        logger.info(
            "trading-persona wakeup skipped (no SLACK_TRADING_CHANNEL_ID): event=%s",
            event,
        )
        return

    prompt = (
        f"AxiomFolio webhook fired: `{event}`.\n\n"
        f"One-line summary: {summary}\n\n"
        f"Raw data: {json.dumps(data, default=str)[:1500]}\n\n"
        "Explain what happened, why it matters, the stage/regime/invalidation "
        "context if relevant, and a concise next-step for the operator. "
        "Keep it tight — 3-5 sentences."
    )

    redis_client = None
    try:
        redis_client = await get_redis()
    except Exception:
        redis_client = None

    await agent.process(
        db,
        redis_client,
        message=prompt,
        organization_id=organization_id,
        org_name="paperwork-labs",
        user_id="system:axiomfolio-webhook",
        thread_id=f"trading:webhook:{event_norm}",
        persona_pin="trading",
        slack_channel_id=channel_id,
        slack_username="Trading",
        slack_icon_emoji=":chart_with_upwards_trend:",
    )


# ---- GitHub PR webhook (Track B, Week 1) ------------------------------------

_GITHUB_SAFE_EVENTS = frozenset({"pull_request", "pull_request_review", "ping"})


async def _verify_github_webhook(request: Request) -> bytes:
    """Verify GitHub's ``X-Hub-Signature-256`` and return the raw body.

    GitHub sends ``X-Hub-Signature-256: sha256=<hex>`` where hex is
    ``hmac.new(secret, body, sha256).hexdigest()`` — same construction as
    AxiomFolio, different header name.
    """
    expected_secret = (settings.GITHUB_WEBHOOK_SECRET or "").strip()
    if not expected_secret:
        if settings.ENVIRONMENT == "development":
            logger.warning(
                "GITHUB_WEBHOOK_SECRET unset; accepting GitHub webhooks without auth (dev only)"
            )
            return await request.body()
        raise HTTPException(
            status_code=503,
            detail="GitHub webhook secret not configured",
        )

    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not sig_header.startswith("sha256="):
        raise HTTPException(
            status_code=401,
            detail="Missing or malformed X-Hub-Signature-256 header",
        )

    body = await request.body()
    expected_sig = hmac.new(
        expected_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    received_sig = sig_header[7:]

    if not hmac.compare_digest(expected_sig, received_sig):
        logger.warning("GitHub webhook signature mismatch")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return body


def _extract_label_names(pr: dict[str, Any]) -> list[str]:
    return [
        (lbl.get("name") or "").strip()
        for lbl in (pr.get("labels") or [])
        if isinstance(lbl, dict) and lbl.get("name")
    ]


async def _apply_labels(pr_number: int, labels: list[str]) -> None:
    """Thin wrapper around GitHub REST. Safe no-op if list is empty."""
    if not labels:
        return
    import httpx
    from app.tools.github import _gh_headers, _repo_parts

    owner, repo = _repo_parts()
    try:
        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=_gh_headers(),
            timeout=15.0,
        ) as client:
            r = await client.post(
                f"/repos/{owner}/{repo}/issues/{pr_number}/labels",
                json={"labels": labels},
            )
            if r.status_code >= 300:
                logger.warning("apply_labels failed for #%s: %s %s", pr_number, r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("apply_labels error for #%s: %s", pr_number, e)


async def _approve_pr(pr_number: int, message: str) -> None:
    """Leave an APPROVE review on behalf of the Brain reviewer."""
    try:
        await gh_tools.review_github_pr(
            number=pr_number,
            body=message,
            event="APPROVE",
        )
    except Exception as e:
        logger.warning("approve_pr error for #%s: %s", pr_number, e)


async def _handle_pull_request_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch on the PR action. Returns a structured audit record stored
    back into Brain memory so we can trace every webhook → action.
    """
    action = str(payload.get("action") or "").strip()
    pr = payload.get("pull_request") or {}
    number = int(pr.get("number") or 0)
    if not number:
        return {"handled": False, "reason": "no pr number"}

    author = ((pr.get("user") or {}).get("login") or "").strip()
    title = str(pr.get("title") or "")
    labels = _extract_label_names(pr)

    audit: dict[str, Any] = {
        "action": action,
        "number": number,
        "author": author,
        "title": title,
        "labels": labels,
    }

    if action not in ("opened", "reopened", "synchronize", "ready_for_review"):
        audit["handled"] = False
        audit["reason"] = f"ignored action: {action}"
        return audit

    if pr.get("draft"):
        audit["handled"] = False
        audit["reason"] = "draft"
        return audit

    classification = classify_pr(
        author_login=author,
        title=title,
        labels=labels,
    )
    audit["classification"] = {
        "decision": classification.decision,
        "reason": classification.reason,
        "bump_kind": classification.bump_kind,
    }

    if classification.decision == "ignore":
        async with async_session_factory() as db:
            result = await review_pr(db, pr_number=number)
        audit["handled"] = True
        audit["route"] = "brain_review"
        audit["result"] = {
            "posted": result.get("posted"),
            "verdict": result.get("verdict"),
            "model": result.get("model"),
        }
        return audit

    if classification.decision == "safe":
        await _apply_labels(number, ["deps:safe"])
        await _approve_pr(
            number,
            f":robot_face: Brain auto-approved this Dependabot bump.\n"
            f"Classification: {classification.reason}.\n"
            f"Auto-merge sweep will squash-merge when CI is green.",
        )
        audit["handled"] = True
        audit["route"] = "dependabot_safe"
        return audit

    if classification.decision == "major":
        await _apply_labels(number, ["deps:major", "needs-human-review"])
        async with async_session_factory() as db:
            result = await review_pr(db, pr_number=number)
        audit["handled"] = True
        audit["route"] = "dependabot_major"
        audit["result"] = {
            "posted": result.get("posted"),
            "verdict": result.get("verdict"),
            "model": result.get("model"),
        }
        return audit

    await _apply_labels(number, ["needs-human-review"])
    audit["handled"] = True
    audit["route"] = "dependabot_unknown"
    audit["reason"] = classification.reason
    return audit


async def _persist_github_audit(audit: dict[str, Any], event: str, delivery: str) -> None:
    try:
        async with async_session_factory() as db:
            summary = (
                f"GitHub {event} → #{audit.get('number')}: "
                f"{audit.get('route') or audit.get('reason') or 'no-op'}"
            )[:300]
            await memory.store_episode(
                db,
                organization_id=DEFAULT_WEBHOOK_ORG_ID,
                source=f"github:webhook:{event}",
                summary=summary,
                full_context=json.dumps({"delivery": delivery, "audit": audit}, default=str),
                channel="github",
                persona="reviewer",
                product="brain",
                source_ref=str(audit.get("number") or ""),
                importance=0.35,
                metadata={
                    "delivery": delivery,
                    "event": event,
                    "route": audit.get("route"),
                },
            )
    except Exception as e:
        logger.warning("persist_github_audit failed: %s", e)


async def _process_github_webhook(event: str, payload: dict[str, Any], delivery: str) -> None:
    """Background worker — keep the HTTP response <2s as GitHub expects."""
    try:
        if event == "pull_request":
            audit = await _handle_pull_request_event(payload)
        elif event == "pull_request_review":
            audit = {
                "handled": False,
                "reason": "review event (informational)",
                "number": (payload.get("pull_request") or {}).get("number"),
                "state": (payload.get("review") or {}).get("state"),
            }
        else:
            audit = {"handled": False, "reason": f"event={event} is informational"}
        await _persist_github_audit(audit, event, delivery)
    except Exception:
        logger.exception("GitHub webhook background processing raised")


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Entry point for GitHub App / webhook deliveries.

    We verify the signature synchronously, enqueue processing in the
    background, and return ``{received: true}`` within milliseconds. GitHub
    retries on non-2xx or slow responses, so keep this tight.
    """
    body = await _verify_github_webhook(request)
    event = request.headers.get("X-GitHub-Event", "").strip()
    delivery = request.headers.get("X-GitHub-Delivery", "").strip()

    if event == "ping":
        return {"received": True, "ping": True}

    if event not in _GITHUB_SAFE_EVENTS:
        return {"received": True, "ignored": event}

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e

    background_tasks.add_task(_process_github_webhook, event, payload, delivery)
    return {"received": True, "event": event, "delivery": delivery}


# ---------------------------------------------------------------------------
# Slack slash commands (Track C)
# ---------------------------------------------------------------------------


async def _verify_slack_signature(request: Request, raw_body: bytes) -> None:
    """Verify X-Slack-Signature against SLACK_SIGNING_SECRET.

    Slack signs each request as ``v0=<hex>`` where the payload is
    ``v0:<timestamp>:<raw_body>`` and the key is the signing secret. We
    skip verification when the secret is unset (dev) but log a warning so
    it's obvious.
    """
    secret = (settings.SLACK_SIGNING_SECRET or "").strip()
    if not secret:
        if settings.ENVIRONMENT == "development":
            logger.warning("SLACK_SIGNING_SECRET not set — skipping slash-command verification")
            return
        raise HTTPException(status_code=503, detail="Slack signing secret not configured")

    ts = request.headers.get("X-Slack-Request-Timestamp", "")
    sig = request.headers.get("X-Slack-Signature", "")
    if not ts or not sig:
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")

    basestring = f"v0:{ts}:{raw_body.decode('utf-8')}".encode()
    expected = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


_KNOWN_PERSONAS = {
    "agent-ops", "brand", "cfo", "cpa", "ea", "engineering", "growth",
    "infra-ops", "legal", "partnerships", "qa", "social", "strategy",
    "tax-domain", "trading", "ux",
}


async def _run_persona_command(
    *,
    persona: str,
    message: str,
    user_id: str,
    channel_id: str,
    response_url: str,
) -> None:
    """Background worker for /persona <slug> <message>.

    We resolve Brain → persona_pin route, capture the response, and POST it
    back to Slack's ``response_url`` as an ephemeral reply. The initial 200
    ack fires instantly so we don't trip Slack's 3-second timeout.
    """
    import httpx

    from app.services import agent as brain_agent
    from app.database import async_session_factory
    from app.redis import get_redis

    redis_client = None
    try:
        redis_client = get_redis()
    except RuntimeError:
        pass

    try:
        async with async_session_factory() as db:
            result = await brain_agent.process(
                db,
                redis_client,
                organization_id=DEFAULT_WEBHOOK_ORG_ID,
                org_name="Paperwork Labs",
                user_id=user_id,
                message=message,
                channel="slack",
                channel_id=channel_id,
                request_id=f"slash:persona:{user_id}:{channel_id}",
                persona_pin=persona,
            )
            await db.commit()
    except Exception as e:
        logger.exception("persona slash command failed: %s", e)
        result = {"response": f":warning: `/persona {persona}` failed: {e}"}

    text = (result.get("response") or "").strip() or "_(empty reply)_"
    payload = {
        "response_type": "in_channel",
        "text": f"*{persona}*: {text[:3500]}",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(response_url, json=payload)
    except Exception:
        logger.warning("Failed to POST back to Slack response_url", exc_info=True)


@router.post("/slack/command")
async def slack_slash_command(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Handle Slack slash commands — currently just ``/persona``.

    Slack sends ``application/x-www-form-urlencoded`` with fields:
    ``command``, ``text``, ``user_id``, ``channel_id``, ``response_url``.
    We respond within 3 seconds with an ack and do the real work in the
    background, posting results to the ``response_url``.
    """
    raw_body = await request.body()
    await _verify_slack_signature(request, raw_body)

    form: dict[str, str] = {}
    for pair in raw_body.decode("utf-8").split("&"):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        form[k] = _url_decode(v)

    command = form.get("command", "").strip()
    text = form.get("text", "").strip()
    user_id = form.get("user_id", "")
    channel_id = form.get("channel_id", "")
    response_url = form.get("response_url", "")

    if command != "/persona":
        return {
            "response_type": "ephemeral",
            "text": f"Unknown command `{command}`. Try `/persona <slug> <message>`.",
        }

    parts = text.split(None, 1)
    if not parts:
        return {
            "response_type": "ephemeral",
            "text": (
                "Usage: `/persona <slug> <message>`. Slugs: "
                + ", ".join(sorted(_KNOWN_PERSONAS))
            ),
        }

    persona = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    if persona not in _KNOWN_PERSONAS:
        return {
            "response_type": "ephemeral",
            "text": (
                f"Unknown persona `{persona}`. Valid: "
                + ", ".join(sorted(_KNOWN_PERSONAS))
            ),
        }

    if not rest:
        return {
            "response_type": "ephemeral",
            "text": f"Give me something to ask {persona}. Example: `/persona {persona} what's our runway?`",
        }

    background_tasks.add_task(
        _run_persona_command,
        persona=persona,
        message=rest,
        user_id=user_id,
        channel_id=channel_id,
        response_url=response_url,
    )

    return {
        "response_type": "ephemeral",
        "text": f":hourglass_flowing_sand: Routing to *{persona}*…",
    }


def _url_decode(s: str) -> str:
    """Minimal application/x-www-form-urlencoded decoder (no stdlib urllib import
    at module top — keeps test imports fast)."""
    from urllib.parse import unquote_plus

    return unquote_plus(s)
