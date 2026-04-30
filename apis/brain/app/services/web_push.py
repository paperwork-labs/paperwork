"""Web Push (VAPID) service — WS-69 PR I.

Manages per-user PushSubscription records in a JSON file and sends push
notifications via pywebpush.

Persistence: ``apis/brain/data/web_push_subscriptions.json``
  [ { user_id, endpoint, keys: { p256dh, auth }, created_at, last_seen }, ... ]

VAPID env vars (required — no silent fallback):
  VAPID_PUBLIC_KEY   — URL-safe base64-encoded ECDH public key
  VAPID_PRIVATE_KEY  — URL-safe base64-encoded ECDH private key
  VAPID_SUBJECT      — mailto: or https: URI for the VAPID claim

medallion: ops
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data file helpers
# ---------------------------------------------------------------------------


def _data_dir() -> Path:
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data"
    return Path(__file__).resolve().parents[2] / "data"


def _subscriptions_path() -> Path:
    return _data_dir() / "web_push_subscriptions.json"


def _load_subscriptions() -> list[dict[str, Any]]:
    path = _subscriptions_path()
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("web_push: failed to load subscriptions: %s", exc)
        return []


def _save_subscriptions(subs: list[dict[str, Any]]) -> None:
    path = _subscriptions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            # File-lock during write to prevent concurrent corruption
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                json.dump(subs, fh, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


# ---------------------------------------------------------------------------
# VAPID configuration
# ---------------------------------------------------------------------------


class VapidConfigError(RuntimeError):
    """Raised when required VAPID env vars are missing (no silent fallback)."""


def _get_vapid_config() -> tuple[str, str, str]:
    """Return (public_key, private_key, subject) or raise VapidConfigError."""
    pub = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    priv = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    subject = os.environ.get("VAPID_SUBJECT", "").strip()
    missing = [
        name
        for name, val in [
            ("VAPID_PUBLIC_KEY", pub),
            ("VAPID_PRIVATE_KEY", priv),
            ("VAPID_SUBJECT", subject),
        ]
        if not val
    ]
    if missing:
        raise VapidConfigError(
            f"VAPID configuration incomplete — missing env vars: {', '.join(missing)}. "
            "Run apis/brain/scripts/generate_vapid_keys.py to generate keys."
        )
    return pub, priv, subject


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_vapid_public_key() -> str:
    """Return the VAPID public key (for client-side subscribe call).

    Raises VapidConfigError if VAPID_PUBLIC_KEY is not set.
    """
    pub, _, _ = _get_vapid_config()
    return pub


def subscribe(user_id: str, endpoint: str, p256dh: str, auth: str) -> None:
    """Persist a PushSubscription for *user_id*.

    Upserts by endpoint — if the same endpoint is re-registered, last_seen is
    updated and duplicate entries are not created.
    """
    subs = _load_subscriptions()
    now = datetime.now(UTC).isoformat()
    for sub in subs:
        if sub.get("endpoint") == endpoint:
            sub["user_id"] = user_id
            sub["keys"] = {"p256dh": p256dh, "auth": auth}
            sub["last_seen"] = now
            _save_subscriptions(subs)
            logger.info("web_push: updated existing subscription endpoint=%s", endpoint[:40])
            return
    subs.append(
        {
            "user_id": user_id,
            "endpoint": endpoint,
            "keys": {"p256dh": p256dh, "auth": auth},
            "created_at": now,
            "last_seen": now,
        }
    )
    _save_subscriptions(subs)
    logger.info("web_push: new subscription user_id=%s endpoint=%s", user_id, endpoint[:40])


def unsubscribe(endpoint: str) -> None:
    """Remove the subscription with *endpoint* (idempotent)."""
    subs = _load_subscriptions()
    before = len(subs)
    subs = [s for s in subs if s.get("endpoint") != endpoint]
    if len(subs) < before:
        _save_subscriptions(subs)
        logger.info("web_push: removed subscription endpoint=%s", endpoint[:40])


def list_subscriptions(user_id: str) -> list[dict[str, Any]]:
    """Return all active subscriptions for *user_id*."""
    return [s for s in _load_subscriptions() if s.get("user_id") == user_id]


def send_push(subscription: dict[str, Any], payload: dict[str, Any]) -> None:
    """Send a push notification to a single *subscription*.

    On ``410 Gone`` the subscription is automatically pruned.
    Raises VapidConfigError if VAPID keys are not configured.
    All other network/push errors are logged; caller decides whether to dead-letter.
    """
    from pywebpush import WebPusher, WebPushException

    _pub_key, priv_key, subject = _get_vapid_config()

    endpoint = subscription.get("endpoint", "")
    keys = subscription.get("keys", {})

    subscription_info = {
        "endpoint": endpoint,
        "keys": {
            "p256dh": keys.get("p256dh", ""),
            "auth": keys.get("auth", ""),
        },
    }

    try:
        pusher = WebPusher(subscription_info)
        response = pusher.send(
            data=json.dumps(payload).encode("utf-8"),
            vapid_private_key=priv_key,
            vapid_claims={"sub": subject},
            content_type="application/json",
            headers={"ttl": "86400"},
        )
        if response.status_code == 410:
            logger.warning("web_push: 410 Gone — pruning endpoint=%s", endpoint[:40])
            unsubscribe(endpoint)
        elif response.status_code not in {200, 201, 202}:
            logger.warning(
                "web_push: unexpected status %s for endpoint=%s",
                response.status_code,
                endpoint[:40],
            )
    except WebPushException as exc:
        if exc.response is not None and exc.response.status_code == 410:
            logger.warning("web_push: 410 Gone (exc) — pruning endpoint=%s", endpoint[:40])
            unsubscribe(endpoint)
        else:
            logger.error("web_push: push failed endpoint=%s: %s", endpoint[:40], exc)
        raise


def fan_out_push(user_id: str, payload: dict[str, Any]) -> None:
    """Send *payload* to all subscriptions for *user_id*.

    Individual failures are caught and logged; they never block the caller.
    Returns immediately after dispatching (dead-letter pattern — SMTP fallback in PR J).
    """
    subs = list_subscriptions(user_id)
    if not subs:
        logger.debug("web_push: no subscriptions for user_id=%s", user_id)
        return
    errors: list[str] = []
    for sub in subs:
        try:
            send_push(sub, payload)
        except Exception as exc:
            errors.append(f"endpoint={sub.get('endpoint', '')[:40]}: {exc}")
    if errors:
        logger.warning(
            "web_push: fan_out partial failure — %d/%d failed: %s",
            len(errors),
            len(subs),
            "; ".join(errors),
        )
