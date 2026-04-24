"""Postmark inbound webhook for the picks (newsletter) pipeline."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.picks import EmailInbox, IngestionStatus
from app.services.gold.picks.postmark_signature import validate_postmark_signature
from app.tasks.picks.parse_inbound import parse_inbound_email

logger = logging.getLogger(__name__)

router = APIRouter()

_PAYLOAD_REDACT_KEYS = frozenset({"Attachments", "RawEmail"})


def _redact_for_storage(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Drop bulky / sensitive Postmark fields before persisting JSON."""
    return {k: v for k, v in payload.items() if k not in _PAYLOAD_REDACT_KEYS}


def _extract_sender_email(from_field: str) -> str:
    _, addr = parseaddr(from_field)
    return addr.strip().lower() if addr else ""


def _parse_received_at(date_str: Optional[str]) -> datetime:
    if not date_str or not str(date_str).strip():
        return datetime.now(timezone.utc)
    try:
        dt = parsedate_to_datetime(str(date_str).strip())
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        logger.warning("picks inbound: could not parse Date=%r; using UTC now", date_str)
        return datetime.now(timezone.utc)


def _to_addresses(payload: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    full = payload.get("ToFull")
    if isinstance(full, list):
        for item in full:
            if isinstance(item, dict) and item.get("Email"):
                out.append(str(item["Email"]).strip().lower())
    if not out and payload.get("To"):
        _, addr = parseaddr(str(payload["To"]))
        if addr:
            out.append(addr.strip().lower())
    return out


@router.post("/inbound")
async def postmark_picks_inbound(
    request: Request,
    db: Session = Depends(get_db),
    x_postmark_signature: Optional[str] = Header(default=None, alias="X-Postmark-Signature"),
):
    raw_body = await request.body()

    if settings.PICKS_INBOUND_REQUIRE_SIGNATURE:
        secret = (settings.POSTMARK_INBOUND_SECRET or "").strip()
        if not secret:
            logger.warning("picks inbound: signature required but POSTMARK_INBOUND_SECRET unset")
            return JSONResponse(
                status_code=403,
                content={"detail": "Webhook signing secret not configured."},
            )
        if not validate_postmark_signature(raw_body, x_postmark_signature, secret):
            logger.warning("picks inbound: invalid or missing Postmark signature")
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid webhook signature."},
            )

    try:
        payload: Dict[str, Any] = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("picks inbound: bad JSON: %s", exc)
        return JSONResponse(
            status_code=400,
            content={"detail": "Malformed JSON body."},
        )

    message_id = str(payload.get("MessageID") or "").strip()
    if not message_id:
        return JSONResponse(
            status_code=400,
            content={"detail": "MessageID is required."},
        )

    existing = db.query(EmailInbox).filter(EmailInbox.message_id == message_id).first()
    if existing is not None:
        return {"status": "duplicate", "inbox_id": existing.id}

    sender_raw = str(payload.get("From") or "")
    sender_email = _extract_sender_email(sender_raw)
    allow = [a for a in settings.PICKS_INBOUND_ALLOWLIST if a]
    if not allow:
        logger.warning(
            "picks inbound: PICKS_INBOUND_ALLOWLIST empty; ignoring message_id=%s",
            message_id,
        )
        return {"status": "ignored", "reason": "allowlist_empty"}

    if sender_email not in allow:
        logger.info(
            "picks inbound: sender not allowlisted sender=%s message_id=%s",
            sender_email or "?",
            message_id,
        )
        return {"status": "ignored", "reason": "sender_not_allowed"}

    to_header = str(payload.get("To") or "")
    to_emails = _to_addresses(payload)
    recipients: Dict[str, Any] = {
        "to_header": to_header,
        "to_addresses": to_emails,
    }

    raw_date = payload.get("Date")
    received_at = _parse_received_at(str(raw_date) if raw_date is not None else None)

    attachments = payload.get("Attachments")
    att_list = attachments if isinstance(attachments, list) else []
    pdf_count = 0
    for item in att_list:
        if not isinstance(item, dict):
            continue
        ct = str(item.get("ContentType") or "").lower()
        name = str(item.get("Name") or "").lower()
        if "pdf" in ct or name.endswith(".pdf"):
            pdf_count += 1

    storage_payload = _redact_for_storage(payload)
    row = EmailInbox(
        message_id=message_id,
        source_label="postmark_inbound",
        sender=sender_email or (sender_raw[:255] if sender_raw else "unknown"),
        recipients=recipients,
        subject=payload.get("Subject"),
        body_text=payload.get("TextBody"),
        body_html=payload.get("HtmlBody"),
        received_at=received_at,
        has_pdf=pdf_count > 0,
        attachment_count=len(att_list),
        attachments_meta=None,
        raw_payload=storage_payload,
        ingestion_status=IngestionStatus.RECEIVED.value,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        dup = (
            db.query(EmailInbox)
            .filter(EmailInbox.message_id == message_id)
            .one_or_none()
        )
        if dup is None:
            logger.warning(
                "picks inbound: IntegrityError on insert but no row for message_id=%s",
                message_id,
            )
            raise
        return {"status": "duplicate", "inbox_id": dup.id}

    inbox_id = row.id
    db.commit()
    parse_inbound_email.delay(inbox_id)
    return {"status": "queued", "inbox_id": inbox_id}
