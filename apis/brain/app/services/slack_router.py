"""Slack notification router — channels, dedup, rate-limit, quiet hours.

All Brain Slack posts go through ``route()`` before calling
``slack_outbound.post_message``. The router enforces:

1. **Channel routing** — maps event_type → target channel from slack_routing.yaml.
2. **Thread dedup** — same (channel, key, severity) within dedup_window_minutes
   gets action="thread_reply" so it collapses into one thread.
3. **Rate limit** — if Brain-wide posts in the sliding hour hit rate_limit_per_hour,
   action="defer_to_digest" so excess goes to email digest instead.
4. **Quiet hours** — outside 09:00-22:00 UTC and on weekends, only
   severity >= quiet_severity_threshold posts immediately; rest defer.

State is kept in-memory (per-process) and also persisted to
``apis/brain/data/slack_dedup_state.json`` so restarts don't lose context.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..schemas.slack_routing import (
    RoutingAction,
    RoutingDecision,
    SlackRoutingConfig,
    severity_gte,
)
from .slack_outbound import post_message as _slack_post_message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_CONFIG_REL = Path("apis/brain/data/slack_routing.yaml")
_DEDUP_STATE_REL = Path("apis/brain/data/slack_dedup_state.json")
_MORNING_QUEUE_REL = Path("apis/brain/data/slack_morning_queue.json")

# ---------------------------------------------------------------------------
# Thread-safe in-memory state
# ---------------------------------------------------------------------------

_lock = threading.Lock()

# dedup registry: key → {"ts": str, "thread_ts": str, "posted_at": ISO-str}
_dedup: dict[str, dict[str, str]] = {}

# sliding rate-limit window: deque of ISO-string timestamps of recent posts
_rate_window: deque[str] = deque()

# morning queue: list of pending payloads
_morning_queue: list[dict[str, Any]] = []

_state_loaded = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    env = os.environ.get("REPO_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / _CONFIG_REL).exists():
            return parent
    return Path("/app")


def _load_config(root: Path | None = None) -> SlackRoutingConfig:
    base = root or _repo_root()
    config_path = base / _CONFIG_REL
    if not config_path.exists():
        logger.warning("slack_router: config not found at %s — using defaults", config_path)
        return SlackRoutingConfig.model_validate({"schema": "slack_routing/v1"})
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return SlackRoutingConfig.model_validate(raw)
    except (yaml.YAMLError, ValidationError, OSError) as exc:
        logger.warning("slack_router: config load failed (%s) — using defaults", exc)
        return SlackRoutingConfig.model_validate({"schema": "slack_routing/v1"})


def _dedup_key(channel: str, key: str, severity: str) -> str:
    return f"{channel}::{key}::{severity}"


def _load_state(root: Path) -> None:
    """Load persisted dedup + morning-queue state into memory (once per process)."""
    global _state_loaded
    if _state_loaded:
        return
    _state_loaded = True

    state_path = root / _DEDUP_STATE_REL
    if state_path.exists():
        try:
            data: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8"))
            _dedup.update(data.get("dedup", {}))
            for ts in data.get("rate_window", []):
                _rate_window.append(ts)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("slack_router: failed to load dedup state: %s", exc)

    queue_path = root / _MORNING_QUEUE_REL
    if queue_path.exists():
        try:
            items: list[dict[str, Any]] = json.loads(queue_path.read_text(encoding="utf-8"))
            _morning_queue.extend(items if isinstance(items, list) else [])
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("slack_router: failed to load morning queue: %s", exc)


def _persist_state(root: Path) -> None:
    """Write in-memory state to disk atomically."""
    state_path = root / _DEDUP_STATE_REL
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"dedup": dict(_dedup), "rate_window": list(_rate_window)}, indent=2),
        encoding="utf-8",
    )
    tmp.replace(state_path)

    queue_path = root / _MORNING_QUEUE_REL
    tmp2 = queue_path.with_suffix(".tmp")
    tmp2.write_text(json.dumps(list(_morning_queue), indent=2), encoding="utf-8")
    tmp2.replace(queue_path)


def _is_quiet_now(cfg: SlackRoutingConfig, now: datetime | None = None) -> bool:
    """Return True if current UTC time falls within quiet hours or is a quiet weekend."""
    import zoneinfo

    tz = zoneinfo.ZoneInfo(cfg.quiet_hours.timezone)
    utc_now = (now or datetime.now(UTC)).astimezone(tz)

    if cfg.quiet_hours.weekends_quiet and utc_now.weekday() >= 5:
        return True

    start_h, start_m = map(int, cfg.quiet_hours.start.split(":"))
    end_h, end_m = map(int, cfg.quiet_hours.end.split(":"))
    current_minutes = utc_now.hour * 60 + utc_now.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    if start_minutes < end_minutes:
        # same-day quiet window (e.g. 00:00-06:00)
        return start_minutes <= current_minutes < end_minutes
    else:
        # overnight quiet window (e.g. 22:00-09:00)
        return current_minutes >= start_minutes or current_minutes < end_minutes


def _purge_old_rate_entries(window_minutes: int, now: datetime) -> None:
    cutoff = now - timedelta(minutes=window_minutes)
    while _rate_window and datetime.fromisoformat(_rate_window[0]) < cutoff:
        _rate_window.popleft()


def _purge_old_dedup(window_minutes: int, now: datetime) -> None:
    cutoff = now - timedelta(minutes=window_minutes)
    expired = [
        k
        for k, v in _dedup.items()
        if datetime.fromisoformat(v.get("posted_at", "1970-01-01T00:00:00+00:00")) < cutoff
    ]
    for k in expired:
        del _dedup[k]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def route(
    *,
    event_type: str,
    severity: str = "low",
    key: str = "",
    payload: dict[str, Any] | None = None,
    now: datetime | None = None,
    root: Path | None = None,
) -> RoutingDecision:
    """Determine where and how a Slack notification should be delivered.

    Parameters
    ----------
    event_type:
        Event class (e.g. ``"pr_merged"``, ``"anomaly_high"``).
    severity:
        One of ``"low"``, ``"medium"``, ``"high"``.
    key:
        Dedup discriminator within the event type (e.g. PR number, alert name).
        Empty string means every call is unique.
    payload:
        Arbitrary data stored in the morning queue when deferred.
    now:
        Override current time (for testing).
    root:
        Monorepo root override (for testing).
    """
    base = root or _repo_root()
    cfg = _load_config(base)
    utc_now = (now or datetime.now(UTC)).astimezone(UTC)

    with _lock:
        _load_state(base)

        channel = cfg.channel_for(event_type)
        dk = _dedup_key(channel, key or event_type, severity)

        # --- dedup check ---
        _purge_old_dedup(cfg.dedup_window_minutes, utc_now)
        if key and dk in _dedup:
            existing = _dedup[dk]
            return RoutingDecision(
                action=RoutingAction.thread_reply,
                channel=channel,
                thread_ts=existing.get("thread_ts"),
                reason=f"dedup: same key seen at {existing.get('posted_at')}",
                dedup_key=dk,
            )

        # --- rate limit check ---
        _purge_old_rate_entries(60, utc_now)
        if len(_rate_window) >= cfg.rate_limit_per_hour:
            _maybe_enqueue_morning(
                cfg, channel, event_type, severity, key, payload or {}, utc_now, dk
            )
            _persist_state(base)
            return RoutingDecision(
                action=RoutingAction.defer_to_digest,
                channel=channel,
                reason=f"rate limit: {len(_rate_window)}/{cfg.rate_limit_per_hour} posts/h",
                dedup_key=dk,
            )

        # --- quiet hours check ---
        if _is_quiet_now(cfg, utc_now) and not severity_gte(severity, cfg.quiet_severity_threshold):
            _maybe_enqueue_morning(
                cfg, channel, event_type, severity, key, payload or {}, utc_now, dk
            )
            _persist_state(base)
            return RoutingDecision(
                action=RoutingAction.defer_to_morning,
                channel=channel,
                reason=(
                    f"quiet hours: severity={severity} < threshold={cfg.quiet_severity_threshold}"
                ),
                dedup_key=dk,
            )

        # --- record the post ---
        now_iso = utc_now.isoformat()
        _rate_window.append(now_iso)
        if key:
            _dedup[dk] = {"posted_at": now_iso, "thread_ts": ""}
        _persist_state(base)

        return RoutingDecision(
            action=RoutingAction.new_post,
            channel=channel,
            reason="ok",
            dedup_key=dk,
        )


def record_thread_ts(dk: str, thread_ts: str, root: Path | None = None) -> None:
    """After a new_post succeeds, store its thread_ts so replies can collapse into it."""
    base = root or _repo_root()
    with _lock:
        if dk in _dedup:
            _dedup[dk]["thread_ts"] = thread_ts
        _persist_state(base)


def _maybe_enqueue_morning(
    _cfg: SlackRoutingConfig,
    channel: str,
    event_type: str,
    severity: str,
    key: str,
    payload: dict[str, Any],
    utc_now: datetime,
    dk: str,
) -> None:
    """Add item to morning queue if not already present for this dedup key."""
    for item in _morning_queue:
        if item.get("dedup_key") == dk:
            return
    _morning_queue.append(
        {
            "channel": channel,
            "event_type": event_type,
            "severity": severity,
            "key": key,
            "payload": payload,
            "queued_at": utc_now.isoformat(),
            "dedup_key": dk,
        }
    )


async def flush_morning_digest(root: Path | None = None) -> dict[str, Any]:
    """Send queued off-hours / rate-limited posts as one digest.

    Called by the 09:00 UTC ``slack_morning_digest`` cron.
    Returns a summary dict ``{sent, skipped}``.
    """
    base = root or _repo_root()
    # Config loaded to ensure default_channel is available; not used directly here.
    _load_config(base)

    with _lock:
        _load_state(base)
        items = list(_morning_queue)
        _morning_queue.clear()
        _persist_state(base)

    if not items:
        return {"sent": 0, "skipped": 0}

    # Group by channel for a compact digest post.
    from collections import defaultdict

    by_channel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_channel[item["channel"]].append(item)

    sent = 0
    skipped = 0
    for channel, channel_items in by_channel.items():
        lines = [f"*Deferred notifications digest* — {len(channel_items)} item(s)\n"]
        for item in channel_items:
            msg = item.get("payload", {}).get("text") or f"[{item['event_type']}] key={item['key']}"
            lines.append(f"• `{item['event_type']}` sev={item['severity']}: {msg}")
        text = "\n".join(lines)
        result = await _slack_post_message(channel=channel, text=text)
        if result.get("ok"):
            sent += len(channel_items)
            # Record this digest post in rate window
            with _lock:
                _rate_window.append(datetime.now(UTC).isoformat())
                _persist_state(base)
        else:
            logger.warning(
                "slack_router: digest post to %s failed: %s", channel, result.get("error")
            )
            skipped += len(channel_items)

    logger.info("slack_router: morning digest flushed — sent=%d skipped=%d", sent, skipped)
    return {"sent": sent, "skipped": skipped}


async def routed_post(
    *,
    event_type: str,
    severity: str = "low",
    key: str = "",
    text: str,
    blocks: list[dict[str, Any]] | None = None,
    username: str | None = None,
    icon_emoji: str | None = None,
    now: datetime | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Convenience wrapper: route then post (or defer) in one call.

    Returns the routing decision merged with the Slack API result (or a
    synthetic result when deferred).
    """
    decision = route(
        event_type=event_type,
        severity=severity,
        key=key,
        payload={"text": text},
        now=now,
        root=root,
    )

    if decision.action in (RoutingAction.defer_to_digest, RoutingAction.defer_to_morning):
        return {
            "ok": True,
            "action": decision.action.value,
            "channel": decision.channel,
            "reason": decision.reason,
        }

    result = await _slack_post_message(
        channel=decision.channel,
        text=text,
        blocks=blocks,
        thread_ts=decision.thread_ts if decision.action == RoutingAction.thread_reply else None,
        username=username,
        icon_emoji=icon_emoji,
    )

    if decision.action == RoutingAction.new_post and result.get("ok") and decision.dedup_key:
        record_thread_ts(decision.dedup_key, result.get("ts", ""), root=root)

    return {**result, "action": decision.action.value, "channel": decision.channel}


def get_dedup_state(root: Path | None = None) -> dict[str, Any]:
    """Return a snapshot of the current dedup + rate-window state (for admin endpoint)."""
    base = root or _repo_root()
    with _lock:
        _load_state(base)
        return {
            "dedup_entries": len(_dedup),
            "dedup": dict(_dedup),
            "rate_window_posts": len(_rate_window),
            "rate_window": list(_rate_window),
            "morning_queue_depth": len(_morning_queue),
        }
