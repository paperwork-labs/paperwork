"""Unified Conversations service — Postgres-canonical store (T1.0d Wave 0).

Persistence
-----------
All reads and writes go through SQLAlchemy async sessions against:
  - ``conversations``         (Alembic 012)
  - ``conversation_messages`` (Alembic 012 + 015)

Prior JSON-file storage and the SQLite FTS sidecar are **no longer used**.
Run the one-time backfill script before deploying this version:

    python -m apis.brain.scripts.backfill_conversations_to_postgres

See ``docs/runbooks/BRAIN_CONVERSATIONS_BACKFILL.md`` for the full runbook.

metadata column mapping
-----------------------
``conversations.metadata`` JSONB stores Conversation fields without dedicated
columns::

    tags, urgency, persona, product_slug, sentiment, participants,
    status, snooze_until (ISO-8601 string), parent_action_id, links (dict),
    needs_founder_action, organization_id

``conversation_messages.message_metadata`` JSONB stores ThreadMessage fields
without dedicated columns::

    author (ConversationParticipant dict), attachments (list), reactions (dict),
    parent_message_id (str | None)

parent_action_id decision
-------------------------
Stored in ``conversations.metadata["parent_action_id"]``.  Not promoted to a
dedicated column in this migration because the primary query pattern is
string-equality dedup; JSONB handles this adequately.  A follow-up migration
can ADD COLUMN if queryability becomes a bottleneck.

feature-flag decision
---------------------
``BRAIN_CONVERSATIONS_USE_POSTGRES`` flag was considered and **omitted**.  A
flag with a JSON-file fallback would require the fallback to log ``WARNING``
on every call (per no-silent-fallback.mdc), creating noise.  The safer gate
is the backfill runbook itself: operators confirm Postgres row counts before
deploy.  There is no runtime read-fallback.

sync-caller compatibility
-------------------------
The public functions remain **synchronous** to preserve ~30 existing callers
(schedulers, expense service, audits) without a cascading refactor.  Async DB
work is dispatched via ``_run()``, which uses ``asyncio.run()`` when no event
loop is running, or a thread-pool executor when called from inside an existing
event loop (e.g. APScheduler async jobs, async FastAPI routes).  A follow-up
workstream will migrate all callers to ``async def`` and remove the thread-pool
path.  See docs/KNOWLEDGE.md D## (logged with this PR) for rationale.

medallion: ops
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import uuid as _uuid_mod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import yaml
from pydantic import ValidationError
from sqlalchemy import func, select, text

from app import database as _db_module
from app.models.conversation_mirror import ConversationMessageRecord, ConversationRecord
from app.schemas.conversation import (
    AppendMessageRequest,
    Attachment,
    Conversation,
    ConversationCreate,
    ConversationLinks,
    ConversationParticipant,
    ConversationsListPage,
    StatusLevel,
    ThreadMessage,
    UrgencyLevel,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Coroutine

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / helpers shared with callers
# ---------------------------------------------------------------------------

_EXPENSE_TAG_ALLOWLIST = frozenset(
    {"expense-approval", "expense-monthly-close", "expense-rule-change"}
)

_HIGH_URGENCY: set[str] = {"high", "critical"}


def _validate_conversation_tags(tags: list[str]) -> None:
    for t in tags:
        if t.startswith("expense-") and t not in _EXPENSE_TAG_ALLOWLIST:
            raise ValueError(f"Unknown expense-related tag: {t!r}")


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


def _default_status(urgency: UrgencyLevel) -> StatusLevel:
    if urgency in _HIGH_URGENCY:
        return "needs-action"
    return "open"


# ---------------------------------------------------------------------------
# Async session context manager
# ---------------------------------------------------------------------------

_T = TypeVar("_T")


@asynccontextmanager
async def _session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager yielding a DB session; commits on success, rolls back on error."""
    async with _db_module.async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Sync-caller compatibility layer (thread-pool executor)
# ---------------------------------------------------------------------------

# Thread pool for callers that are already inside a running event loop
# (e.g. APScheduler async jobs, FastAPI async routes calling sync services).
# Sync callers with no event loop use asyncio.run() directly (no thread needed).
_tp = concurrent.futures.ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="conv-svc",
)


def _run(coro: Coroutine[Any, Any, _T]) -> _T:
    """Execute *coro* safely from sync code, even when called inside a running event loop.

    - No running loop  → ``asyncio.run()`` in the caller's thread (zero overhead).
    - Running loop     → spawns a thread with its own event loop to avoid
      ``RuntimeError: This event loop is already running``.

    The thread-pool path blocks the calling thread until the coroutine completes.
    For Brain's internal-tool load this is acceptable.  A follow-up workstream
    will migrate all callers to async so this path is never triggered in
    production.
    """
    try:
        asyncio.get_running_loop()
        # Already inside an event loop — must use a separate thread.
        return _tp.submit(asyncio.run, coro).result()
    except RuntimeError:
        # No running loop — safe to call asyncio.run() directly.
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Schema conversion helpers
# ---------------------------------------------------------------------------


def _conversation_to_meta(conv: Conversation) -> dict[str, Any]:
    """Build the ``conversations.metadata`` JSONB payload from a Conversation instance."""
    return {
        "tags": conv.tags,
        "urgency": conv.urgency,
        "persona": conv.persona,
        "product_slug": conv.product_slug,
        "sentiment": conv.sentiment,
        "participants": [p.model_dump() for p in conv.participants],
        "status": conv.status,
        "snooze_until": conv.snooze_until.isoformat() if conv.snooze_until else None,
        "parent_action_id": conv.parent_action_id,
        "links": conv.links.model_dump() if conv.links else None,
        "needs_founder_action": conv.needs_founder_action,
        "organization_id": conv.organization_id,
    }


def _thread_message_to_meta(msg: ThreadMessage) -> dict[str, Any]:
    """Build the ``message_metadata`` JSONB payload for a ThreadMessage."""
    return {
        "author": msg.author.model_dump(),
        "attachments": [a.model_dump() for a in msg.attachments],
        "reactions": msg.reactions,
        "parent_message_id": msg.parent_message_id,
    }


def _author_kind_to_role(kind: str) -> str:
    """Map Pydantic ``ConversationParticipant.kind`` to the DB ``role`` CHECK constraint."""
    return "persona" if kind == "persona" else "user"


def _row_to_thread_message(row: ConversationMessageRecord) -> ThreadMessage:
    meta: dict[str, Any] = row.message_metadata or {}
    author_raw = meta.get("author")
    if author_raw:
        try:
            author = ConversationParticipant.model_validate(author_raw)
        except (ValidationError, TypeError):
            kind = "persona" if row.role == "persona" else "founder"
            author = ConversationParticipant(
                id=row.persona_slug or "system",
                kind=kind,
            )
    else:
        # Legacy row: reconstruct minimal author from role/persona_slug
        kind = "persona" if row.role == "persona" else "founder"
        author = ConversationParticipant(
            id=row.persona_slug or "system",
            kind=kind,
        )
    attachments: list[Attachment] = []
    for a in meta.get("attachments", []):
        try:
            attachments.append(Attachment.model_validate(a))
        except (ValidationError, TypeError) as exc:
            logger.warning(
                "conversations: skipping malformed attachment in msg %s: %s", row.id, exc
            )
    return ThreadMessage(
        id=str(row.id),
        author=author,
        body_md=row.content,
        attachments=attachments,
        created_at=row.created_at,
        reactions=meta.get("reactions", {}),
        parent_message_id=meta.get("parent_message_id"),
    )


def _row_to_conversation(
    conv_row: ConversationRecord,
    msg_rows: list[ConversationMessageRecord],
) -> Conversation:
    m: dict[str, Any] = conv_row.metadata_ or {}

    snooze_until: datetime | None = None
    raw_snooze = m.get("snooze_until")
    if raw_snooze:
        try:
            snooze_until = datetime.fromisoformat(raw_snooze)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "conversations: bad snooze_until %r for %s: %s",
                raw_snooze,
                conv_row.id,
                exc,
            )

    participants: list[ConversationParticipant] = []
    for p in m.get("participants", []):
        try:
            participants.append(ConversationParticipant.model_validate(p))
        except (ValidationError, TypeError) as exc:
            logger.warning(
                "conversations: skipping malformed participant for %s: %s", conv_row.id, exc
            )

    links: ConversationLinks | None = None
    raw_links = m.get("links")
    if raw_links:
        try:
            links = ConversationLinks.model_validate(raw_links)
        except (ValidationError, TypeError) as exc:
            logger.warning("conversations: skipping malformed links for %s: %s", conv_row.id, exc)

    sorted_msgs = sorted(msg_rows, key=lambda r: r.created_at)
    return Conversation(
        id=str(conv_row.id),
        title=conv_row.title,
        tags=m.get("tags", []),
        urgency=m.get("urgency", "normal"),
        persona=m.get("persona"),
        product_slug=m.get("product_slug"),
        sentiment=m.get("sentiment"),
        participants=participants,
        messages=[_row_to_thread_message(mr) for mr in sorted_msgs],
        created_at=conv_row.created_at,
        updated_at=conv_row.updated_at,
        status=m.get("status", "open"),
        snooze_until=snooze_until,
        parent_action_id=m.get("parent_action_id"),
        links=links,
        needs_founder_action=m.get("needs_founder_action", False),
        organization_id=m.get("organization_id"),
    )


# ---------------------------------------------------------------------------
# Async DB helpers (internal — called via _run() from public sync API)
# ---------------------------------------------------------------------------


async def _load_messages(
    session: AsyncSession,
    conversation_uuid: _uuid_mod.UUID,
) -> list[ConversationMessageRecord]:
    result = await session.execute(
        select(ConversationMessageRecord)
        .where(ConversationMessageRecord.conversation_id == conversation_uuid)
        .order_by(ConversationMessageRecord.created_at.asc())
    )
    return list(result.scalars().all())


async def _async_get_conversation(
    conversation_id: str,
    *,
    organization_id: str | None = None,
) -> Conversation:
    try:
        conv_uuid = _uuid_mod.UUID(conversation_id)
    except ValueError as exc:
        raise KeyError(f"Conversation {conversation_id!r} not found") from exc

    async with _session() as session:
        result = await session.execute(
            select(ConversationRecord).where(ConversationRecord.id == conv_uuid)
        )
        conv_row = result.scalar_one_or_none()
        if conv_row is None:
            raise KeyError(f"Conversation {conversation_id!r} not found")
        msg_rows = await _load_messages(session, conv_uuid)
        conv = _row_to_conversation(conv_row, msg_rows)

    _ensure_conversation_organization(conv, organization_id)
    return conv


async def _upsert_conversation_row(
    session: AsyncSession,
    conv: Conversation,
) -> None:
    """Upsert the ConversationRecord for *conv* in an already-open session."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    conv_uuid = _uuid_mod.UUID(conv.id)
    await session.execute(
        pg_insert(ConversationRecord)
        .values(
            id=conv_uuid,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            metadata_=_conversation_to_meta(conv),
        )
        .on_conflict_do_update(
            index_elements=["id"],
            set_={
                "title": conv.title,
                "updated_at": conv.updated_at,
                "metadata_": _conversation_to_meta(conv),
            },
        )
    )


async def _upsert_message_row(
    session: AsyncSession,
    msg: ThreadMessage,
    conversation_uuid: _uuid_mod.UUID,
) -> None:
    """Upsert a single ConversationMessageRecord."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    msg_uuid = _uuid_mod.UUID(msg.id)
    role = _author_kind_to_role(msg.author.kind)
    await session.execute(
        pg_insert(ConversationMessageRecord)
        .values(
            id=msg_uuid,
            conversation_id=conversation_uuid,
            role=role,
            content=msg.body_md,
            persona_slug=msg.author.id if msg.author.kind == "persona" else None,
            model_used=None,
            created_at=msg.created_at,
            # Compute tsvector explicitly so tests (no trigger) and production both work.
            content_tsv=func.to_tsvector("english", msg.body_md),
            message_metadata=_thread_message_to_meta(msg),
        )
        .on_conflict_do_update(
            index_elements=["id"],
            set_={
                "content": msg.body_md,
                "content_tsv": func.to_tsvector("english", msg.body_md),
                "message_metadata": _thread_message_to_meta(msg),
                "persona_slug": msg.author.id if msg.author.kind == "persona" else None,
            },
        )
    )


async def _async_save_conversation(conv: Conversation) -> None:
    """Full replace-all-messages upsert.

    Used by the expense service (which modifies a Conversation copy and saves
    the whole object) and by the backfill script.
    """
    conv_uuid = _uuid_mod.UUID(conv.id)
    async with _session() as session:
        await _upsert_conversation_row(session, conv)
        # Delete all existing messages for this conversation, then re-insert.
        # This is a replace-all semantics: the expense service sends the full
        # updated message list, so a DELETE+INSERT is always consistent.
        await session.execute(
            text("DELETE FROM conversation_messages WHERE conversation_id = :cid").bindparams(
                cid=conv_uuid
            )
        )
        for msg in conv.messages:
            await _upsert_message_row(session, msg, conv_uuid)


async def _async_create_conversation(
    create: ConversationCreate,
    *,
    organization_id: str | None = None,
    push_user_id: str | None = None,
) -> Conversation:
    _validate_conversation_tags(create.tags)
    now = datetime.now(UTC)
    status: StatusLevel = (
        "needs-action" if create.needs_founder_action else _default_status(create.urgency)
    )
    from uuid import uuid4

    conv = Conversation(
        id=str(uuid4()),
        title=create.title,
        tags=create.tags,
        urgency=create.urgency,
        persona=create.persona,
        product_slug=create.product_slug,
        sentiment=create.sentiment,
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

    conv_uuid = _uuid_mod.UUID(conv.id)
    async with _session() as session:
        await _upsert_conversation_row(session, conv)
        for msg in conv.messages:
            await _upsert_message_row(session, msg, conv_uuid)

    _maybe_push_or_email(conv, push_user_id=push_user_id or "founder")
    return conv


async def _async_list_conversations(
    status_filter: str | None,
    search: str | None,
    cursor: str | None,
    limit: int,
    *,
    organization_id: str | None,
    product_slug: str | None,
) -> ConversationsListPage:
    async with _session() as session:
        # ------------------------------------------------------------------ FTS
        candidate_uuids: list[_uuid_mod.UUID] | None = None
        if search:
            # FTS on message content via tsvector + ILIKE on conversation title.
            # Title ILIKE trade-off: simpler than a tsvector index on title; for
            # Brain's scale (<<10 000 conversations) the sequential scan is fast.
            fts_result = await session.execute(
                text(
                    """
                    WITH fts_hits AS (
                        SELECT DISTINCT cm.conversation_id,
                            MAX(ts_rank(cm.content_tsv,
                                plainto_tsquery('english', :q))) AS rank
                        FROM conversation_messages cm
                        WHERE cm.content_tsv IS NOT NULL
                          AND cm.content_tsv @@ plainto_tsquery('english', :q)
                        GROUP BY cm.conversation_id
                    ),
                    title_hits AS (
                        SELECT c.id AS conversation_id, 0.5::float AS rank
                        FROM conversations c
                        WHERE c.title ILIKE :pat
                    ),
                    combined AS (
                        SELECT conversation_id, MAX(rank) AS rank
                        FROM (
                            SELECT * FROM fts_hits
                            UNION ALL
                            SELECT * FROM title_hits
                        ) u
                        GROUP BY conversation_id
                    )
                    SELECT conversation_id FROM combined ORDER BY rank DESC
                    """
                ),
                {"q": search, "pat": f"%{search}%"},
            )
            candidate_uuids = [row[0] for row in fts_result]
            if not candidate_uuids:
                return ConversationsListPage(items=[], next_cursor=None, total=0)

        # -------------------------------------------------- load conversations
        stmt = select(ConversationRecord)
        if candidate_uuids is not None:
            stmt = stmt.where(ConversationRecord.id.in_(candidate_uuids))
        # Apply status filter at SQL level for efficiency.
        filter_status: str | None = (
            None if (status_filter is None or status_filter == "all") else status_filter
        )
        if filter_status:
            stmt = stmt.where(ConversationRecord.metadata_["status"].astext == filter_status)
        stmt = stmt.order_by(ConversationRecord.updated_at.desc())

        conv_result = await session.execute(stmt)
        all_conv_rows = list(conv_result.scalars().all())

        # --------------------------------------------------- load messages
        msgs_by_conv: dict[_uuid_mod.UUID, list[ConversationMessageRecord]] = {}
        if all_conv_rows:
            conv_uuids = [r.id for r in all_conv_rows]
            msg_result = await session.execute(
                select(ConversationMessageRecord)
                .where(ConversationMessageRecord.conversation_id.in_(conv_uuids))
                .order_by(ConversationMessageRecord.created_at.asc())
            )
            for mr in msg_result.scalars():
                msgs_by_conv.setdefault(mr.conversation_id, []).append(mr)

    # -------------------------------------------- Python-level filters + sort
    all_convs = [_row_to_conversation(r, msgs_by_conv.get(r.id, [])) for r in all_conv_rows]

    filtered: list[Conversation] = [
        c
        for c in all_convs
        if _conversation_matches_organization(c, organization_id)
        and (product_slug is None or (c.product_slug or "") == product_slug)
    ]

    # Preserve FTS relevance order when search was used, else sort by updated_at.
    if candidate_uuids is not None:
        uuid_rank: dict[str, int] = {str(uid): idx for idx, uid in enumerate(candidate_uuids)}
        filtered.sort(key=lambda c: uuid_rank.get(c.id, len(candidate_uuids)))
    else:
        filtered.sort(key=lambda c: c.updated_at, reverse=True)

    total = len(filtered)

    # Cursor pagination: identical logic to the JSON-file implementation.
    start_idx = 0
    if cursor:
        for i, c in enumerate(filtered):
            if c.id == cursor:
                start_idx = i + 1
                break

    page = filtered[start_idx : start_idx + limit]
    next_cursor = page[-1].id if len(page) == limit and start_idx + limit < total else None
    return ConversationsListPage(items=page, next_cursor=next_cursor, total=total)


async def _async_append_message(
    conversation_id: str,
    req: AppendMessageRequest,
    *,
    organization_id: str | None = None,
) -> ThreadMessage:
    conv = await _async_get_conversation(conversation_id, organization_id=organization_id)
    parent_id = req.parent_message_id
    if parent_id and not any(m.id == parent_id for m in conv.messages):
        raise ValueError(f"Parent message {parent_id!r} not found in conversation")
    from uuid import uuid4

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
    conv_uuid = _uuid_mod.UUID(conversation_id)
    async with _session() as session:
        # Append the new message row
        await _upsert_message_row(session, msg, conv_uuid)
        # Update conversation updated_at and metadata.status (unchanged here, just timestamp)
        new_meta = _conversation_to_meta(conv)
        await session.execute(
            text(
                "UPDATE conversations SET updated_at = :ts, metadata = :meta WHERE id = :cid"
            ).bindparams(ts=now, meta=new_meta, cid=conv_uuid)
        )
    return msg


async def _async_update_conversation_status(
    conversation_id: str,
    status: StatusLevel,
    *,
    organization_id: str | None = None,
) -> Conversation:
    conv = await _async_get_conversation(conversation_id, organization_id=organization_id)
    now = datetime.now(UTC)
    conv = conv.model_copy(
        update={
            "status": status,
            "updated_at": now,
            "snooze_until": None if status != "snoozed" else conv.snooze_until,
        }
    )
    await _async_save_conversation(conv)
    return conv


async def _async_snooze(
    conversation_id: str,
    until: datetime,
    *,
    organization_id: str | None = None,
) -> Conversation:
    conv = await _async_get_conversation(conversation_id, organization_id=organization_id)
    now = datetime.now(UTC)
    conv = conv.model_copy(update={"status": "snoozed", "snooze_until": until, "updated_at": now})
    await _async_save_conversation(conv)
    return conv


async def _async_react(
    conversation_id: str,
    message_id: str,
    emoji: str,
    participant_id: str,
    *,
    organization_id: str | None = None,
) -> ThreadMessage:
    conv = await _async_get_conversation(conversation_id, organization_id=organization_id)
    target: ThreadMessage | None = None
    updated_msgs: list[ThreadMessage] = []
    for msg in conv.messages:
        if msg.id == message_id:
            reactors = dict(msg.reactions)
            bucket = list(reactors.get(emoji, []))
            if participant_id in bucket:
                bucket.remove(participant_id)
            else:
                bucket.append(participant_id)
            if bucket:
                reactors[emoji] = bucket
            else:
                reactors.pop(emoji, None)
            target = msg.model_copy(update={"reactions": reactors})
            updated_msgs.append(target)
        else:
            updated_msgs.append(msg)
    if target is None:
        raise KeyError(f"Message {message_id!r} not found in conversation {conversation_id!r}")
    now = datetime.now(UTC)
    updated_conv = conv.model_copy(update={"messages": updated_msgs, "updated_at": now})
    await _async_save_conversation(updated_conv)
    return target


async def _async_search_conversations(
    query: str,
    limit: int,
    *,
    organization_id: str | None = None,
) -> list[Conversation]:
    page = await _async_list_conversations(
        status_filter=None,
        search=query,
        cursor=None,
        limit=limit,
        organization_id=organization_id,
        product_slug=None,
    )
    return page.items


async def _async_unread_count(
    status_filter: str = "needs-action",
    *,
    organization_id: str | None = None,
) -> int:
    page = await _async_list_conversations(
        status_filter=status_filter,
        search=None,
        cursor=None,
        limit=10_000,
        organization_id=organization_id,
        product_slug=None,
    )
    return page.total


async def _async_admin_conversation_counts(
    *,
    organization_id: str | None = None,
) -> tuple[int, int]:
    today = datetime.now(UTC).date()
    page = await _async_list_conversations(
        status_filter=None,
        search=None,
        cursor=None,
        limit=10_000,
        organization_id=organization_id,
        product_slug=None,
    )
    today_updated = sum(1 for c in page.items if c.updated_at.astimezone(UTC).date() == today)
    return page.total, today_updated


async def _async_needs_action_badge_metrics(
    status_filter: str = "needs-action",
    *,
    organization_id: str | None = None,
) -> dict[str, int | bool]:
    page = await _async_list_conversations(
        status_filter=status_filter,
        search=None,
        cursor=None,
        limit=10_000,
        organization_id=organization_id,
        product_slug=None,
    )
    return {
        "count": page.total,
        "has_critical": any(c.urgency == "critical" for c in page.items),
    }


# ---------------------------------------------------------------------------
# Notification helpers (unchanged — same as JSON-file implementation)
# ---------------------------------------------------------------------------


def _maybe_push_or_email(conv: Conversation, *, push_user_id: str = "founder") -> None:
    """Deliver founder notifications for high/critical + needs_founder_action.

    Runs web push (when VAPID is configured) and Gmail SMTP as a fallback.
    ``EmailConfigError`` is re-raised so callers see misconfiguration (no-silent-fallback).
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
        raise
    except Exception as exc:
        logger.error(
            "email_outbound: SMTP send failed for conv %s — dead-lettered: %s",
            conv.id,
            exc,
        )


# ---------------------------------------------------------------------------
# Public synchronous API (preserves all existing caller signatures)
# ---------------------------------------------------------------------------


def create_conversation(
    create: ConversationCreate,
    *,
    organization_id: str | None = None,
    push_user_id: str | None = None,
) -> Conversation:
    """Create a new Conversation and persist it to Postgres."""
    return _run(
        _async_create_conversation(
            create,
            organization_id=organization_id,
            push_user_id=push_user_id,
        )
    )


def get_conversation(
    conversation_id: str,
    *,
    organization_id: str | None = None,
) -> Conversation:
    """Load a single Conversation by ID.

    Raises KeyError if not found.
    Raises PermissionError if the conversation does not belong to *organization_id*.
    """
    return _run(_async_get_conversation(conversation_id, organization_id=organization_id))


def list_conversations(
    status_filter: str | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    *,
    organization_id: str | None = None,
    product_slug: str | None = None,
) -> ConversationsListPage:
    """Return a cursor-paginated page of conversations.

    *status_filter* maps to ``status`` values: ``needs-action``, ``open``,
    ``snoozed``, ``resolved``, ``archived``.  ``all`` or None returns
    everything.

    *search* performs Postgres FTS (message bodies) + ILIKE (title).

    *cursor* is the last conversation ID seen; pagination continues from
    the item immediately after it.
    """
    return _run(
        _async_list_conversations(
            status_filter,
            search,
            cursor,
            limit,
            organization_id=organization_id,
            product_slug=product_slug,
        )
    )


def append_message(
    conversation_id: str,
    req: AppendMessageRequest,
    *,
    organization_id: str | None = None,
) -> ThreadMessage:
    """Append a ThreadMessage to an existing conversation."""
    return _run(_async_append_message(conversation_id, req, organization_id=organization_id))


def update_conversation_status(
    conversation_id: str,
    status: StatusLevel,
    *,
    organization_id: str | None = None,
) -> Conversation:
    """Update the status of a conversation."""
    return _run(
        _async_update_conversation_status(conversation_id, status, organization_id=organization_id)
    )


def snooze(
    conversation_id: str,
    until: datetime,
    *,
    organization_id: str | None = None,
) -> Conversation:
    """Snooze a conversation until the given datetime."""
    return _run(_async_snooze(conversation_id, until, organization_id=organization_id))


def react(
    conversation_id: str,
    message_id: str,
    emoji: str,
    participant_id: str,
    *,
    organization_id: str | None = None,
) -> ThreadMessage:
    """Add (or remove if already present) an emoji reaction to a message."""
    return _run(
        _async_react(
            conversation_id,
            message_id,
            emoji,
            participant_id,
            organization_id=organization_id,
        )
    )


def search_conversations(
    query: str,
    limit: int = 20,
    *,
    organization_id: str | None = None,
) -> list[Conversation]:
    """Full-text search via Postgres tsvector index on message bodies + ILIKE on title."""
    return _run(_async_search_conversations(query, limit, organization_id=organization_id))


def unread_count(
    status_filter: str = "needs-action",
    *,
    organization_id: str | None = None,
) -> int:
    """Return the count of conversations matching *status_filter* (for badge/PWA)."""
    return _run(_async_unread_count(status_filter, organization_id=organization_id))


def admin_conversation_counts(
    *,
    organization_id: str | None = None,
) -> tuple[int, int]:
    """Return (total conversations, count updated today UTC) for admin stats."""
    return _run(_async_admin_conversation_counts(organization_id=organization_id))


def needs_action_badge_metrics(
    status_filter: str = "needs-action",
    *,
    organization_id: str | None = None,
) -> dict[str, int | bool]:
    """Count + whether any matching row is urgency=critical (sidebar badge styling)."""
    return _run(_async_needs_action_badge_metrics(status_filter, organization_id=organization_id))


def _save_conversation(conv: Conversation) -> None:
    """Full upsert of a Conversation including all messages.

    .. deprecated::
        This private function is called directly by ``expenses.py``
        (``resolve_expense_linked_conversation``).  That caller should be
        migrated to use :func:`update_conversation_status` or an explicit
        public mutator in a follow-up PR.  The function will remain until
        that migration is complete.
    """
    logger.warning(
        "conversations._save_conversation: called directly (deprecated private API); "
        "caller should migrate to a public mutator.  conv_id=%s",
        conv.id,
    )
    _run(_async_save_conversation(conv))


# ---------------------------------------------------------------------------
# Backfill helpers
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


def backfill_founder_actions_detailed(
    path: Path | None = None,
) -> FounderActionsBackfillResult:
    """Import founder action tiers → Conversations (idempotent, Postgres-backed).

    Resolution order:
    1. Explicit ``path`` when provided
    2. ``apis/brain/data/founder_actions.yaml``
    3. ``apis/brain/data/founder_actions.json``
    4. ``apps/studio/src/data/founder-actions.json``

    Idempotency: dedup key is ``parent_action_id = slugify(title)``.
    Existing conversations with the same ``parent_action_id`` are skipped.
    """
    import json
    import os

    data: dict[str, Any] | None = None
    source_kind: SourceKind = "none"
    parse_error: str | None = None
    resolved_path: Path | None = None

    def _data_dir() -> Path:
        repo_root = os.environ.get("REPO_ROOT", "").strip()
        if repo_root:
            return Path(repo_root) / "apis" / "brain" / "data"
        return Path(__file__).resolve().parents[2] / "data"

    def _try_load_json(p: Path, kind: SourceKind) -> None:
        nonlocal data, source_kind, parse_error, resolved_path
        if data is not None or not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
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
                created=0, source_kind="none", parse_error=parse_error
            )

    if data is None:
        default_yaml = _data_dir() / "founder_actions.yaml"
        if default_yaml.exists():
            try:
                data = yaml.safe_load(default_yaml.read_text(encoding="utf-8"))
                source_kind = "yaml"
                resolved_path = default_yaml
                logger.info("backfill: using YAML at %s", default_yaml)
            except (OSError, yaml.YAMLError) as exc:
                logger.warning("backfill: could not read default YAML: %s", exc)

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

    # Collect existing parent_action_ids from Postgres (for dedup)
    existing_parent_ids: set[str] = _run(_async_collect_existing_parent_action_ids())

    created = 0
    for tier in tiers:
        tier_id: str = tier.get("id", "")
        tier_urgency: UrgencyLevel = "critical" if tier_id == "critical" else "normal"
        items: list[dict[str, Any]] = tier.get("items", [])
        for item in items:
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            parent_action_id = _slugify(title)
            if parent_action_id in existing_parent_ids:
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
            existing_parent_ids.add(parent_action_id)
            created += 1
            logger.info("backfill: created conversation %r (%s)", conv.id, title)

    logger.info(
        "backfill: created %d conversations (source=%s path=%s)",
        created,
        source_kind,
        resolved_path,
    )
    return FounderActionsBackfillResult(created=created, source_kind=source_kind, parse_error=None)


async def _async_collect_existing_parent_action_ids() -> set[str]:
    """Return the set of all non-null parent_action_ids already in Postgres."""
    async with _session() as session:
        result = await session.execute(
            text(
                "SELECT metadata->>'parent_action_id' "
                "FROM conversations "
                "WHERE metadata->>'parent_action_id' IS NOT NULL"
            )
        )
        return {row[0] for row in result if row[0]}


def _slugify(text: str) -> str:
    import re

    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")[:120] or "action"
