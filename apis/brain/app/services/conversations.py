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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
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


def _legacy_org_id() -> str | None:
    from app.config import settings

    v = settings.BRAIN_TOOLS_ORGANIZATION_ID.strip()
    return v or None


def _conversation_matches_organization(conv: Conversation, organization_id: str | None) -> bool:
    if organization_id is None:
        return True
    legacy = _legacy_org_id()
    stored = conv.organization_id
    if stored == organization_id:
        return True
    return stored is None and legacy is not None and organization_id == legacy


def _ensure_conversation_organization(conv: Conversation, organization_id: str | None) -> None:
    if organization_id is None:
        return
    if not _conversation_matches_organization(conv, organization_id):
        raise PermissionError("Conversation does not belong to this organization")


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


def create_conversation(
    create: ConversationCreate,
    *,
    organization_id: str | None = None,
    push_user_id: str | None = None,
) -> Conversation:
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
        organization_id=organization_id,
    )
    _save_conversation(conv)
    _maybe_push_or_email(conv, push_user_id=push_user_id or "founder")
    return conv


def _maybe_push_or_email(conv: Conversation, *, push_user_id: str = "founder") -> None:
    """Deliver founder notifications for high/critical + needs_founder_action.

    Runs **web push** (when VAPID is configured) and **Gmail SMTP** as a
    fallback when push is not configured or fails.

    - Push payload body is truncated to **120 characters** (provider size caps).
    - SMTP email uses the **full** first message body (no truncation).
    - ``EmailConfigError`` (missing Gmail env) is **re-raised** so callers
      see misconfiguration — no silent skip (no-silent-fallback.mdc).
    - Other SMTP send failures are dead-lettered (logged at error); the
      Conversation is already persisted.

    Both channels are attempted when applicable: if push succeeds, SMTP is
    skipped for that create to avoid duplicate notifications.
    """
    if conv.urgency not in _HIGH_URGENCY or not conv.needs_founder_action:
        return

    import contextlib

    import app.services.web_push as wp_svc
    from app.services.web_push import VapidConfigError

    unread = unread_count(status_filter="needs-action", organization_id=conv.organization_id)
    full_body = conv.messages[0].body_md if conv.messages else ""
    push_body = full_body[:120]
    push_payload = {
        "title": f"Brain: {conv.title}",
        "body": push_body,
        "url": f"/admin/brain/conversations/{conv.id}",
        "unreadCount": unread,
    }

    push_delivered = False
    with contextlib.suppress(VapidConfigError):
        try:
            wp_svc.fan_out_push(user_id=push_user_id, payload=push_payload)
            push_delivered = True
        except VapidConfigError:
            logger.info(
                "web_push: VAPID not configured — falling through to SMTP for conv %s",
                conv.id,
            )
        except Exception as exc:
            logger.warning(
                "web_push: fan_out error for conv %s: %s — falling through to SMTP",
                conv.id,
                exc,
            )

    if push_delivered:
        return

    # Gmail SMTP fallback
    from app.services.email_outbound import EmailConfigError, send_conversation_email

    attachments = [{"id": a.id, "url": a.url} for msg in conv.messages for a in msg.attachments]
    try:
        send_conversation_email(
            conversation_id=conv.id,
            title=conv.title,
            body_md=full_body,
            attachments=attachments or None,
        )
    except EmailConfigError:
        # Re-raise so callers know SMTP is not configured — no silent skip.
        raise
    except Exception as exc:
        # SMTP send failure: dead-letter (log error, don't block conversation create).
        logger.error(
            "email_outbound: SMTP send failed for conv %s — dead-lettered: %s",
            conv.id,
            exc,
        )


def get_conversation(conversation_id: str, *, organization_id: str | None = None) -> Conversation:
    """Load a single Conversation by ID.

    Raises KeyError if not found.
    Raises PermissionError if the conversation does not belong to *organization_id*.
    """
    conv = _load_conversation(conversation_id)
    if conv is None:
        raise KeyError(f"Conversation {conversation_id!r} not found")
    _ensure_conversation_organization(conv, organization_id)
    return conv


def list_conversations(
    status_filter: str | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    *,
    organization_id: str | None = None,
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
        if not _conversation_matches_organization(conv, organization_id):
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


def append_message(
    conversation_id: str,
    req: AppendMessageRequest,
    *,
    organization_id: str | None = None,
) -> ThreadMessage:
    """Append a ThreadMessage to an existing conversation."""
    conv = get_conversation(conversation_id, organization_id=organization_id)
    parent_id = req.parent_message_id
    if parent_id and not any(m.id == parent_id for m in conv.messages):
        raise ValueError(f"Parent message {parent_id!r} not found in conversation")
    now = datetime.now(UTC)
    msg = ThreadMessage(
        id=str(uuid4()),
        author=req.author,
        body_md=req.body_md,
        attachments=req.attachments,
        created_at=now,
        reactions={},
        parent_message_id=parent_id,
    )
    conv.messages.append(msg)
    conv.updated_at = now
    _save_conversation(conv)
    return msg


def update_conversation_status(
    conversation_id: str,
    status: StatusLevel,
    *,
    organization_id: str | None = None,
) -> Conversation:
    """Update the status of a conversation."""
    conv = get_conversation(conversation_id, organization_id=organization_id)
    conv.status = status
    conv.updated_at = datetime.now(UTC)
    if status != "snoozed":
        conv.snooze_until = None
    _save_conversation(conv)
    return conv


def snooze(
    conversation_id: str, until: datetime, *, organization_id: str | None = None
) -> Conversation:
    """Snooze a conversation until the given datetime."""
    conv = get_conversation(conversation_id, organization_id=organization_id)
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
    *,
    organization_id: str | None = None,
) -> ThreadMessage:
    """Add (or remove if already present) an emoji reaction to a message."""
    conv = get_conversation(conversation_id, organization_id=organization_id)
    for msg in conv.messages:
        if msg.id == message_id:
            reactors = msg.reactions.setdefault(emoji, [])
            if participant_id in reactors:
                reactors.remove(participant_id)
            else:
                reactors.append(participant_id)
            if not reactors:
                del msg.reactions[emoji]
            conv.updated_at = datetime.now(UTC)
            _save_conversation(conv)
            return msg
    raise KeyError(f"Message {message_id!r} not found in conversation {conversation_id!r}")


def search_conversations(
    query: str,
    limit: int = 20,
    *,
    organization_id: str | None = None,
) -> list[Conversation]:
    """Full-text search via SQLite FTS5 sidecar index."""
    ids = _fts_search(query, limit=limit)
    results: list[Conversation] = []
    for cid in ids:
        conv = _load_conversation(cid)
        if conv is not None and _conversation_matches_organization(conv, organization_id):
            results.append(conv)
    return results


def unread_count(status_filter: str = "needs-action", *, organization_id: str | None = None) -> int:
    """Return the count of conversations matching *status_filter* (for badge/PWA)."""
    page = list_conversations(
        status_filter=status_filter, limit=10_000, organization_id=organization_id
    )
    return page.total


def needs_action_badge_metrics(
    status_filter: str = "needs-action",
    *,
    organization_id: str | None = None,
) -> dict[str, int | bool]:
    """Count + whether any matching row is urgency=critical (sidebar badge styling)."""
    page = list_conversations(
        status_filter=status_filter, limit=10_000, organization_id=organization_id
    )
    return {
        "count": page.total,
        "has_critical": any(c.urgency == "critical" for c in page.items),
    }


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

SourceKind = Literal["yaml", "brain_json", "studio_json", "none"]


@dataclass(frozen=True)
class FounderActionsBackfillResult:
    """Outcome of ``backfill_founder_actions_detailed`` for admin + Studio callers."""

    created: int
    source_kind: SourceKind
    parse_error: str | None = None


def backfill_from_founder_actions_yaml(path: Path | None = None) -> int:
    """Compatibility wrapper — returns only the created count."""
    return backfill_founder_actions_detailed(path=path).created


def backfill_founder_actions_detailed(path: Path | None = None) -> FounderActionsBackfillResult:
    """Import founder action tiers → Conversations (idempotent).

    Resolution order:
    1. Explicit ``path`` when provided (``.yaml`` via PyYAML, ``.json`` via stdlib json)
    2. ``apis/brain/data/founder_actions.yaml``
    3. ``apis/brain/data/founder_actions.json`` (canonical JSON sibling to YAML)
    4. ``apps/studio/src/data/founder-actions.json`` (Studio sync output)

    Idempotency: there is no ``source_ref`` field on ``Conversation`` today; we use
    ``parent_action_id = slugify(title)`` as the stable dedup key (same title → same row).

    Each new row uses ``needs_founder_action=True`` so status is ``needs-action`` and
    founder notifications behave consistently.
    """
    data: dict[str, Any] | None = None
    source_kind: SourceKind = "none"
    parse_error: str | None = None
    resolved_path: Path | None = None

    def _try_load_json(p: Path, kind: SourceKind) -> None:
        nonlocal data, source_kind, parse_error, resolved_path
        if data is not None:
            return
        if not p.exists():
            return
        try:
            raw_json = p.read_text(encoding="utf-8")
            data = json.loads(raw_json)
            source_kind = kind
            resolved_path = p
            parse_error = None
            logger.info("backfill: loaded JSON from %s", p)
        except (OSError, json.JSONDecodeError) as exc:
            parse_error = f"failed to read JSON {p}: {exc}"
            logger.error("backfill: %s", parse_error)

    if path is not None and path.exists():
        resolved_path = path
        try:
            raw = path.read_text(encoding="utf-8")
            suf = path.suffix.lower()
            if suf in {".yaml", ".yml"}:
                data = yaml.safe_load(raw)
                source_kind = "yaml"
            elif suf == ".json":
                data = json.loads(raw)
                name = path.name.lower()
                source_kind = "studio_json" if "founder-actions" in name else "brain_json"
            else:
                data = yaml.safe_load(raw)
                source_kind = "yaml"
            parse_error = None
        except (OSError, yaml.YAMLError, json.JSONDecodeError) as exc:
            parse_error = f"failed to read {path}: {exc}"
            logger.error("backfill: %s", parse_error)
            return FounderActionsBackfillResult(
                created=0,
                source_kind="none",
                parse_error=parse_error,
            )

    if data is None:
        default_yaml = _data_dir() / "founder_actions.yaml"
        if default_yaml.exists():
            try:
                raw = default_yaml.read_text(encoding="utf-8")
                data = yaml.safe_load(raw)
                source_kind = "yaml"
                resolved_path = default_yaml
                parse_error = None
                logger.info("backfill: using YAML at %s", default_yaml)
            except (OSError, yaml.YAMLError) as exc:
                logger.warning("backfill: could not read default YAML %s: %s", default_yaml, exc)

    if data is None:
        _try_load_json(_data_dir() / "founder_actions.json", "brain_json")

    if data is None:
        repo_root_env = os.environ.get("REPO_ROOT", "").strip()
        monorepo_root = Path(repo_root_env) if repo_root_env else _data_dir().parents[2]
        studio_json = monorepo_root / "apps" / "studio" / "src" / "data" / "founder-actions.json"
        _try_load_json(studio_json, "studio_json")

    if parse_error and data is None:
        return FounderActionsBackfillResult(created=0, source_kind="none", parse_error=parse_error)

    if data is None:
        logger.warning("backfill: no founder_actions source found — skipping")
        return FounderActionsBackfillResult(created=0, source_kind="none", parse_error=None)

    tiers: list[dict[str, Any]] = data.get("tiers", [])
    if not tiers:
        msg = "founder_actions payload has no tiers — nothing to import"
        logger.warning("backfill: %s", msg)
        return FounderActionsBackfillResult(created=0, source_kind=source_kind, parse_error=msg)

    existing_ids: set[str] = set()
    for cid in _list_all_ids():
        conv = _load_conversation(cid)
        if conv and conv.parent_action_id:
            existing_ids.add(conv.parent_action_id)

    created = 0
    for tier in tiers:
        tier_id: str = tier.get("id", "")
        tier_urgency: UrgencyLevel = "critical" if tier_id == "critical" else "normal"
        items: list[dict[str, Any]] = tier.get("items", [])
        for item in items:
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            # Stable dedup key — mirrors a future ``source_ref`` for founder-action imports.
            parent_action_id = _slugify(title)
            if parent_action_id in existing_ids:
                logger.debug("backfill: skipping duplicate %r", parent_action_id)
                continue

            parts: list[str] = []
            if item.get("why"):
                parts.append(f"**Why:** {item['why']}")
            if item.get("where"):
                parts.append(f"**Where:** {item['where']}")
            steps = item.get("steps", [])
            if steps:
                parts.append("**Steps:**\n" + "\n".join(str(s) for s in steps))
            if item.get("verification"):
                parts.append(f"**Verification:** {item['verification']}")
            if item.get("eta"):
                parts.append(f"**ETA:** {item['eta']}")
            body_md = "\n\n".join(parts)

            raw_urgency = item.get("urgency")
            urgency: UrgencyLevel = tier_urgency
            if raw_urgency in ("info", "normal", "high", "critical"):
                urgency = raw_urgency

            tags: list[str] = [tier_id, "founder-action"]
            src = item.get("source")
            if isinstance(src, str) and src.strip():
                slug = _slugify(src)[:40]
                if slug:
                    tags.append(f"founder-src-{slug}")

            create = ConversationCreate(
                title=title,
                body_md=body_md,
                tags=tags,
                urgency=urgency,
                parent_action_id=parent_action_id,
                needs_founder_action=True,
            )
            conv = create_conversation(create)
            existing_ids.add(parent_action_id)
            created += 1
            logger.info("backfill: created conversation %r (%s)", conv.id, title)

    logger.info(
        "backfill: created %d conversations (source=%s path=%s)",
        created,
        source_kind,
        resolved_path,
    )
    return FounderActionsBackfillResult(created=created, source_kind=source_kind, parse_error=None)


def _slugify(text: str) -> str:
    import re

    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")[:120] or "action"
