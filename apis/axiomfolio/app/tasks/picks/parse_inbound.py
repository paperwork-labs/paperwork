"""Inbound newsletter email parsing (Celery entry point).

Currently a stub: marks rows as ready for the LLM parser (implemented
in a follow-up). The webhook persists ``EmailInbox`` and dispatches
this task.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.picks import EmailInbox, IngestionStatus
from app.observability import traced
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.picks.parse_inbound_email",
    soft_time_limit=25,
    time_limit=30,
    queue="celery",
)
@traced(
    "parse_inbound_email",
    attrs={"component": "picks", "subsystem": "parser_task"},
)
def parse_inbound_email(email_inbox_id: int) -> Dict[str, Any]:
    """Load ``EmailInbox`` by id, mark parse pending, log stub; real parser later."""
    db: Session = SessionLocal()
    try:
        row = db.get(EmailInbox, email_inbox_id)
        if row is None:
            logger.warning("parse_inbound_email: EmailInbox id=%s not found", email_inbox_id)
            return {"inbox_id": email_inbox_id, "status": "missing"}

        logger.info(
            "parse_inbound_email: TODO parse with LLM (inbox_id=%s message_id=%s)",
            row.id,
            row.message_id,
        )
        row.ingestion_status = IngestionStatus.PARSE_PENDING.value
        db.add(row)
        db.commit()
        return {"inbox_id": row.id, "status": "stub"}
    except Exception:
        logger.exception("parse_inbound_email failed for inbox_id=%s", email_inbox_id)
        db.rollback()
        raise
    finally:
        db.close()
