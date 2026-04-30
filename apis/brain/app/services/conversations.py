"""Unified Conversations service — Brain-canonical store (WS-69 PR E).

Persistence: JSON files at apis/brain/data/conversations/<id>.json with a
sidecar SQLite FTS5 index at apis/brain/data/conversations.fts.db for
full-text search over title + message bodies.

Backfill: ``backfill_from_founder_actions_yaml`` reads the legacy
apis/brain/data/founder_actions.yaml (if present) and creates corresponding
Conversations with ``parent_action_id`` set so they link back.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from pydantic import ValidationError

from app.schemas.conversation import (
    AppendMessageRequest,
    Conversation,
    ConversationCreate,
    ConversationParticipant,
    ConversationsListPage,
    StatusLevel,
    ThreadMessage,
    UrgencyLevel,
)

_EXPENSE_TAG_ALLOWLIST = frozenset(
    {"expense-approval", "expense-monthly-close", "expense-rule-change"}
)


def _validate_conversation_tags(tags: list[str]) -> None:
    for t in tags:
        if t.startswith("expense-") and t not in _EXPENSE_TAG_ALLOWLIST:
            raise ValueError(f"Unknown expense-related tag: {t!r}")


logger = logging.getLogger(__name__)

_fts_lock = threading.Lock()

_HIGH_URGENCY: set[str] = {"high", "critical"}

# ---------------------------------------------------------------------------
# Data-directory helpers
# ---------------------------------------------------------------------------


def _data_dir() -> Path:
    """Returns apis/brain/data — three levels above this services/ file."""
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data"
    return Path(__file__).resolve().parents[2] / "data"


def _conversations_dir() -> Path:
    d = _data_dir() / "conversations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _conversation_path(conversation_id: str) -> Path:
    return _conversations_dir() / f"{conversation_id}.json"


def _fts_db_path() -> Path:
    return _data_dir() / "conversations.fts.db"


# ---------------------------------------------------------------------------
# FTS helpers (SQLite FTS5 sidecar)
# ---------------------------------------------------------------------------


def _get_fts_conn() -> sqlite3.Connection:
    db_path = str(_fts_db_path())
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS conv_fts
        USING fts5(
            conversation_id UNINDEXED,
            title,
            body,
            tokenize = 'porter ascii'
        )
    """)
    conn.commit()
    return conn


def _fts_upsert(conversation_id: str, title: str, body: str) -> None:
    with _fts_lock:
        conn = _get_fts_conn()
        try:
            conn.execute(
                "DELETE FROM conv_fts WHERE conversation_id = ?",
                (conversation_id,),
            )
            conn.execute(
                "INSERT INTO conv_fts (conversation_id, title, body) VALUES (?, ?, ?)",
                (conversation_id, title, body),
            )
            conn.commit()
        finally:
            conn.close()


def _fts_delete(conversation_id: str) -> None:
    with _fts_lock:
        conn = _get_fts_conn()
        try:
            conn.execute(
                "DELETE FROM conv_fts WHERE conversation_id = ?",
                (conversation_id,),
            )
            conn.commit()
        finally:
            conn.close()


def _fts_search(query: str, limit: int = 20) -> list[str]:
    """Returns list of conversation_ids matching *query* via FTS5."""
    with _fts_lock:
        conn = _get_fts_conn()
        try:
            rows = conn.execute(
                """
                SELECT conversation_id
                FROM conv_fts
                WHERE conv_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# JSON persistence helpers
# ---------------------------------------------------------------------------


def _load_conversation(conversation_id: str) -> Conversation | None:
    path = _conversation_path(conversation_id)
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return Conversation.model_validate(data)
    except (json.JSONDecodeError, ValidationError, OSError) as exc:
        logger.error("conversations: failed to load %s: %s", conversation_id, exc)
        return None


def _save_conversation(conv: Conversation) -> None:
    path = _conversation_path(conv.id)
    tmp_dir = _conversations_dir()
    fd, tmp_path = tempfile.mkstemp(dir=tmp_dir, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(conv.model_dump(mode="json"), fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        import contextlib

        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise

    # Keep FTS index in sync
    body_parts = [m.body_md for m in conv.messages]
    _fts_upsert(conv.id, conv.title, " ".join(body_parts))


def _list_all_ids() -> list[str]:
    d = _conversations_dir()
    return [p.stem for p in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)]


# ---------------------------------------------------------------------------
# Default urgency → status mapping
# ---------------------------------------------------------------------------


def _default_status(urgency: UrgencyLevel) -> StatusLevel:
    if urgency in _HIGH_URGENCY:
        return "needs-action"
    return "open"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_conversation(create: ConversationCreate) -> Conversation:
    """Create a new Conversation and persist it to disk."""
    _validate_conversation_tags(create.tags)
    now = datetime.now(UTC)
    status: StatusLevel = (
        "needs-action" if create.needs_founder_action else _default_status(create.urgency)
    )
    conv = Conversation(
        id=str(uuid4()),
        title=create.title,
        tags=create.tags,
        urgency=create.urgency,
        persona=create.persona,
        participants=create.participants,
        messages=(
            [
                ThreadMessage(
                    id=str(uuid4()),
                    author=ConversationParticipant(
                        id="founder", kind="founder", display_name="Founder"
                    ),
                    body_md=create.body_md,
                    attachments=create.attachments,
                    created_at=now,
                    reactions={},
                )
            ]
            if create.body_md
            else []
        ),
        created_at=now,
        updated_at=now,
        status=status,
        snooze_until=None,
        parent_action_id=create.parent_action_id,
        links=create.links,
        needs_founder_action=create.needs_founder_action,
    )
    _save_conversation(conv)
    _maybe_push_notify(conv)
    return conv


def _maybe_push_notify(conv: Conversation) -> None:
    """Fan out a web push notification for high/critical conversations.

    Dead-letters on failure — never blocks the create path.
    SMTP fallback ships in PR J.
    """
    if conv.urgency not in _HIGH_URGENCY or not conv.needs_founder_action:
        return

    import contextlib

    import app.services.web_push as wp_svc
    from app.services.web_push import VapidConfigError

    unread = unread_count(status_filter="needs-action")
    body_text = conv.messages[0].body_md[:120] if conv.messages else ""
    payload = {
        "title": f"Brain: {conv.title}",
        "body": body_text,
        "url": f"/admin/brain/conversations/{conv.id}",
        "unreadCount": unread,
    }
    with contextlib.suppress(VapidConfigError):
        # VapidConfigError is logged by web_push service; suppress here so
        # the conversation is still created cleanly when VAPID is unconfigured.
        try:
            wp_svc.fan_out_push(user_id="founder", payload=payload)
        except VapidConfigError:
            logger.info("web_push: VAPID not configured — skipping push for conv %s", conv.id)
        except Exception as exc:
            logger.warning("web_push: fan_out error for conv %s: %s", conv.id, exc)


def get_conversation(conversation_id: str) -> Conversation:
    """Load a single Conversation by ID.

    Raises KeyError if not found.
    """
    conv = _load_conversation(conversation_id)
    if conv is None:
        raise KeyError(f"Conversation {conversation_id!r} not found")
    return conv


def list_conversations(
    status_filter: str | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> ConversationsListPage:
    """Return a cursor-paginated page of conversations.

    *status_filter* maps to ``status`` values: ``needs-action``, ``open``,
    ``snoozed``, ``resolved``, ``archived``.  ``all`` or None returns
    everything.

    *search* performs FTS5 full-text search (AND-mode) prior to status
    filter so both constraints are applied.

    *cursor* is the last conversation ID seen; pagination continues from
    the item immediately after it.
    """
    if search:
        candidate_ids: list[str] = _fts_search(search, limit=500)
        all_ids = [cid for cid in candidate_ids if (_conversation_path(cid)).exists()]
    else:
        all_ids = _list_all_ids()

    # Apply status filter
    filter_status: str | None = (
        None if (status_filter is None or status_filter == "all") else status_filter
    )

    convs: list[Conversation] = []
    for cid in all_ids:
        conv = _load_conversation(cid)
        if conv is None:
            continue
        if filter_status and conv.status != filter_status:
            continue
        convs.append(conv)

    # Sort newest first by updated_at
    convs.sort(key=lambda c: c.updated_at, reverse=True)

    total = len(convs)

    # Cursor pagination: skip to just after `cursor`
    start_idx = 0
    if cursor:
        for i, c in enumerate(convs):
            if c.id == cursor:
                start_idx = i + 1
                break

    page = convs[start_idx : start_idx + limit]
    next_cursor = page[-1].id if len(page) == limit and start_idx + limit < total else None

    return ConversationsListPage(items=page, next_cursor=next_cursor, total=total)


def append_message(conversation_id: str, req: AppendMessageRequest) -> ThreadMessage:
    """Append a ThreadMessage to an existing conversation."""
    conv = get_conversation(conversation_id)
    now = datetime.now(UTC)
    msg = ThreadMessage(
        id=str(uuid4()),
        author=req.author,
        body_md=req.body_md,
        attachments=req.attachments,
        created_at=now,
        reactions={},
    )
    conv.messages.append(msg)
    conv.updated_at = now
    _save_conversation(conv)
    return msg


def update_conversation_status(conversation_id: str, status: StatusLevel) -> Conversation:
    """Update the status of a conversation."""
    conv = get_conversation(conversation_id)
    conv.status = status
    conv.updated_at = datetime.now(UTC)
    if status != "snoozed":
        conv.snooze_until = None
    _save_conversation(conv)
    return conv


def snooze(conversation_id: str, until: datetime) -> Conversation:
    """Snooze a conversation until the given datetime."""
    conv = get_conversation(conversation_id)
    conv.status = "snoozed"
    conv.snooze_until = until
    conv.updated_at = datetime.now(UTC)
    _save_conversation(conv)
    return conv


def react(
    conversation_id: str,
    message_id: str,
    emoji: str,
    participant_id: str,
) -> ThreadMessage:
    """Add (or remove if already present) an emoji reaction to a message."""
    conv = get_conversation(conversation_id)
    for msg in conv.messages:
        if msg.id == message_id:
            reactors = msg.reactions.setdefault(emoji, [])
            if participant_id in reactors:
                reactors.remove(participant_id)
            else:
                reactors.append(participant_id)
            conv.updated_at = datetime.now(UTC)
            _save_conversation(conv)
            return msg
    raise KeyError(f"Message {message_id!r} not found in conversation {conversation_id!r}")


def search_conversations(query: str, limit: int = 20) -> list[Conversation]:
    """Full-text search via SQLite FTS5 sidecar index."""
    ids = _fts_search(query, limit=limit)
    results: list[Conversation] = []
    for cid in ids:
        conv = _load_conversation(cid)
        if conv is not None:
            results.append(conv)
    return results


def unread_count(status_filter: str = "needs-action") -> int:
    """Return the count of conversations matching *status_filter* (for badge/PWA)."""
    page = list_conversations(status_filter=status_filter, limit=10_000)
    return page.total


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------


def backfill_from_founder_actions_yaml(path: Path | None = None) -> int:
    """One-shot migration: read legacy founder_actions data → create Conversations.

    Supports two source formats:
    - YAML at ``path`` (or ``apis/brain/data/founder_actions.yaml`` if not found)
    - JSON at ``apps/studio/src/data/founder-actions.json`` (Studio-built cache)

    Each action item becomes one Conversation with:
    - status = "needs-action"
    - urgency derived from tier ("critical" tier → "critical", else "normal")
    - parent_action_id = item title (slugified) for traceability

    Returns the number of new conversations created (skips duplicates).
    """
    # Resolve data source
    data: dict[str, Any] | None = None

    if path is None:
        path = _data_dir() / "founder_actions.yaml"

    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
        except (OSError, yaml.YAMLError) as exc:
            logger.error("backfill: failed to read YAML %s: %s", path, exc)

    if data is None:
        # Fall back to the Studio-built JSON cache.
        # Monorepo root is 3 levels up from the data dir (data -> brain -> apis -> repo root),
        # or from REPO_ROOT env var if available.
        repo_root_env = os.environ.get("REPO_ROOT", "").strip()
        monorepo_root = Path(repo_root_env) if repo_root_env else _data_dir().parents[2]
        json_fallback = monorepo_root / "apps" / "studio" / "src" / "data" / "founder-actions.json"
        if json_fallback.exists():
            try:
                raw_json = json_fallback.read_text(encoding="utf-8")
                data = json.loads(raw_json)
                logger.info("backfill: using JSON fallback at %s", json_fallback)
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("backfill: failed to read JSON fallback %s: %s", json_fallback, exc)

    if data is None:
        logger.warning("backfill: no founder_actions source found — skipping")
        return 0

    tiers: list[dict[str, Any]] = data.get("tiers", [])
    if not tiers:
        logger.warning("backfill: founder_actions.yaml has no tiers — nothing to import")
        return 0

    # Index existing parent_action_ids to stay idempotent
    existing_ids: set[str] = set()
    for cid in _list_all_ids():
        conv = _load_conversation(cid)
        if conv and conv.parent_action_id:
            existing_ids.add(conv.parent_action_id)

    created = 0
    for tier in tiers:
        tier_id: str = tier.get("id", "")
        urgency: UrgencyLevel = "critical" if tier_id == "critical" else "normal"
        items: list[dict[str, Any]] = tier.get("items", [])
        for item in items:
            title: str = item.get("title", "").strip()
            if not title:
                continue
            parent_action_id = _slugify(title)
            if parent_action_id in existing_ids:
                logger.debug("backfill: skipping duplicate %r", parent_action_id)
                continue

            # Build body from available fields
            parts: list[str] = []
            if item.get("why"):
                parts.append(f"**Why:** {item['why']}")
            if item.get("where"):
                parts.append(f"**Where:** {item['where']}")
            steps = item.get("steps", [])
            if steps:
                parts.append("**Steps:**\n" + "\n".join(steps))
            if item.get("verification"):
                parts.append(f"**Verification:** {item['verification']}")
            if item.get("eta"):
                parts.append(f"**ETA:** {item['eta']}")
            body_md = "\n\n".join(parts)

            create = ConversationCreate(
                title=title,
                body_md=body_md,
                tags=[tier_id, "founder-action"],
                urgency=urgency,
                parent_action_id=parent_action_id,
            )
            conv = create_conversation(create)
            # Override status to needs-action for all backfill items
            update_conversation_status(conv.id, "needs-action")
            existing_ids.add(parent_action_id)
            created += 1
            logger.info("backfill: created conversation %r (%s)", conv.id, title)

    logger.info("backfill: created %d conversations from %s", created, path)
    return created


def _slugify(text: str) -> str:
    import re

    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")[:120] or "action"
