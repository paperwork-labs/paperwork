"""Periodic refresh of broker OAuth access tokens.

Scheduled every 30 minutes (see ``app/tasks/job_catalog.py`` ›
``oauth-token-refresh``). Selects ACTIVE connections whose
``token_expires_at`` falls inside the refresh window (default matches
``REFRESH_WINDOW``) and asks the broker's
adapter to renew. Outcomes:

* Success      -> rotate ciphertexts, bump ``rotation_count``, ``ACTIVE``.
* Permanent    -> mark ``REFRESH_FAILED``, log WARN; **do not** retry. The
                  user must re-authorize via the OAuth UI.
* Transient    -> log WARN, leave row ACTIVE so next tick retries; counter
                  ``errors`` is incremented but the task does not re-raise
                  (Celery retries on this task add little value because we'll
                  pick the row up again on the next 30-minute tick).

Per the no-silent-fallback rule each iteration emits structured counters and
asserts ``written + skipped + errors == total``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from celery import shared_task

from app.database import SessionLocal
from app.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from app.services.oauth import OAuthError, get_adapter
from app.services.oauth.encryption import (
    EncryptionDecryptError,
    decrypt,
    decrypt_optional,
    encrypt,
)

logger = logging.getLogger(__name__)


REFRESH_WINDOW = timedelta(minutes=60)


def _refresh_one(db, conn: BrokerOAuthConnection) -> str:
    """Refresh a single connection. Returns ``"written"|"skipped"|"errors"``."""

    if conn.status not in (
        OAuthConnectionStatus.ACTIVE.value,
        OAuthConnectionStatus.EXPIRED.value,
    ):
        return "skipped"
    if not conn.access_token_encrypted:
        return "skipped"

    try:
        adapter = get_adapter(conn.broker)
    except OAuthError as exc:
        logger.warning(
            "oauth.refresh unsupported broker user=%s connection=%s broker=%s err=%s",
            conn.user_id,
            conn.id,
            conn.broker,
            exc,
        )
        conn.status = OAuthConnectionStatus.ERROR.value
        conn.last_error = f"unsupported broker: {exc}"
        return "errors"

    try:
        access = decrypt(conn.access_token_encrypted)
        refresh = decrypt_optional(conn.refresh_token_encrypted)
    except EncryptionDecryptError as exc:
        logger.warning(
            "oauth.refresh decrypt failed user=%s connection=%s broker=%s err=%s",
            conn.user_id,
            conn.id,
            conn.broker,
            exc,
        )
        conn.status = OAuthConnectionStatus.REFRESH_FAILED.value
        conn.last_error = "stored token could not be decrypted; reauthorize"
        return "errors"

    try:
        tokens = adapter.refresh(access_token=access, refresh_token=refresh)
    except OAuthError as exc:
        if exc.permanent:
            logger.warning(
                "oauth.refresh permanent failure user=%s connection=%s broker=%s status=%s err=%s",
                conn.user_id,
                conn.id,
                conn.broker,
                exc.provider_status,
                exc,
            )
            conn.status = OAuthConnectionStatus.REFRESH_FAILED.value
            conn.last_error = f"refresh failed (permanent): {exc}"
            return "errors"
        logger.warning(
            "oauth.refresh transient failure user=%s connection=%s broker=%s status=%s err=%s",
            conn.user_id,
            conn.id,
            conn.broker,
            exc.provider_status,
            exc,
        )
        conn.last_error = f"refresh failed (transient): {exc}"
        return "errors"
    except Exception as exc:  # adapter bug; surface as ERROR
        logger.exception(
            "oauth.refresh unexpected exception user=%s connection=%s broker=%s",
            conn.user_id,
            conn.id,
            conn.broker,
        )
        conn.status = OAuthConnectionStatus.ERROR.value
        conn.last_error = f"unexpected refresh error: {exc}"
        return "errors"

    conn.access_token_encrypted = encrypt(tokens.access_token)
    if tokens.refresh_token is not None:
        conn.refresh_token_encrypted = encrypt(tokens.refresh_token)
    conn.token_expires_at = tokens.expires_at
    if tokens.scope is not None:
        conn.scope = tokens.scope
    conn.status = OAuthConnectionStatus.ACTIVE.value
    conn.last_refreshed_at = datetime.now(UTC)
    conn.last_error = None
    conn.rotation_count = (conn.rotation_count or 0) + 1
    return "written"


@shared_task(
    name="app.tasks.portfolio.oauth_token_refresh.refresh_expiring_tokens",
    soft_time_limit=240,
    time_limit=300,
)
def refresh_expiring_tokens(
    window_minutes: int = int(REFRESH_WINDOW.total_seconds() // 60),
) -> dict[str, int]:
    """Refresh ACTIVE/EXPIRED connections whose tokens expire within ``window``."""

    window = timedelta(minutes=max(1, int(window_minutes)))
    cutoff = datetime.now(UTC) + window

    counters = {"written": 0, "skipped": 0, "errors": 0, "total": 0}
    db = SessionLocal()
    try:
        rows = (
            db.query(BrokerOAuthConnection)
            .filter(
                BrokerOAuthConnection.status.in_(
                    [
                        OAuthConnectionStatus.ACTIVE.value,
                        OAuthConnectionStatus.EXPIRED.value,
                    ]
                ),
                BrokerOAuthConnection.token_expires_at != None,  # noqa: E711
                BrokerOAuthConnection.token_expires_at <= cutoff,
            )
            .all()
        )
        counters["total"] = len(rows)

        for row in rows:
            outcome = _refresh_one(db, row)
            counters[outcome] = counters.get(outcome, 0) + 1
            try:
                db.commit()
            except Exception:
                logger.exception(
                    "oauth.refresh commit failed user=%s connection=%s broker=%s",
                    row.user_id,
                    row.id,
                    row.broker,
                )
                db.rollback()
                # Reclassify as error if the per-row outcome was success.
                if outcome == "written":
                    counters["written"] -= 1
                    counters["errors"] = counters.get("errors", 0) + 1

        assert (
            counters["written"] + counters["skipped"] + counters["errors"] == counters["total"]
        ), f"counter drift: {counters}"

        logger.info(
            "oauth.refresh tick complete total=%d written=%d skipped=%d errors=%d",
            counters["total"],
            counters["written"],
            counters["skipped"],
            counters["errors"],
        )
        return counters
    finally:
        db.close()


__all__ = ["REFRESH_WINDOW", "_refresh_one", "refresh_expiring_tokens"]
