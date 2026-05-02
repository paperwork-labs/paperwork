"""Persona-authored replies in Conversation threads via litellm (WS-82 W10a).

Canonical thread storage remains JSON (:mod:`app.services.conversations`).
Optional rows in ``conversations`` / ``conversation_messages`` mirror persona
posts for Postgres-backed analytics.

medallion: ops
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence  # noqa: TC003
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

import app.services.conversations as conv_svc
from app.models.employee import Employee
from app.personas import PersonaSpec, get_spec, resolve_model
from app.schemas.conversation import (
    AppendMessageRequest,
    ConversationParticipant,
    PersonaReplyResponse,
    ThreadMessage,
)

logger = logging.getLogger(__name__)


class UnknownPersonaError(Exception):
    """Registry has no YAML spec for the requested persona slug."""

    def __init__(self, persona_slug: str) -> None:
        super().__init__(persona_slug)
        self.persona_slug = persona_slug


def _usage_total(response: Any) -> int:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if total is not None:
            return int(total)
        p = int(usage.get("prompt_tokens") or 0)
        c = int(usage.get("completion_tokens") or 0)
        return p + c
    tt = getattr(usage, "total_tokens", None)
    if tt is not None:
        return int(tt)
    pr = getattr(usage, "prompt_tokens", None)
    ct = getattr(usage, "completion_tokens", None)
    return int(pr or 0) + int(ct or 0)


def _fmt_thread(conv_messages: Sequence[ThreadMessage]) -> str:
    lines: list[str] = []
    for m in conv_messages:
        au = m.author
        tag = au.display_name or au.id
        lines.append(f"[{au.kind} — {tag}]\n{m.body_md}")
    return "\n\n---\n\n".join(lines) if lines else "(no prior messages)"


def _build_system_prompt(spec: PersonaSpec) -> str:
    prefix = (spec.tone_prefix or "").strip()
    core = (
        "You reply inside a Brain Conversation thread aimed at founders. "
        "Be concise and practical; use markdown when helpful."
    )
    if prefix:
        return f"{prefix}\n\n{core}\n\nPersona focus: {spec.description}"
    return f"{core}\n\nPersona focus: {spec.description}"


def conversation_uuid(cid: str) -> uuid.UUID:
    try:
        return uuid.UUID(cid)
    except ValueError as exc:
        raise ValueError(f"conversation_id must be UUID, got {cid!r}") from exc


async def generate_persona_reply_text(
    *,
    persona_slug: str,
    user_message: str,
    conversation_context_md: str,
) -> tuple[str, str, int]:
    """Call litellm for *persona_slug*. Returns ``(reply_text, model_used, tokens)``."""
    spec = get_spec(persona_slug)
    if spec is None:
        raise UnknownPersonaError(persona_slug)

    model_used, _esc = resolve_model(
        spec,
        message=user_message + "\n" + conversation_context_md,
    )
    system = _build_system_prompt(spec)
    user_block = (
        "Conversation title and thread excerpt follow. Answer the founder request.\n\n"
        f"--- Thread ---\n{conversation_context_md}\n\n"
        f"--- Founder request ---\n{user_message.strip()}"
    )

    max_tokens = int(spec.max_output_tokens or 4096)
    import litellm

    response = await litellm.acompletion(
        model=model_used,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_block},
        ],
        max_tokens=max_tokens,
        temperature=0.6,
    )
    reply = (response.choices[0].message.content or "").strip()
    if not reply:
        raise RuntimeError("Model returned empty reply")
    return reply, model_used, _usage_total(response)


async def mirror_persona_message_to_pg(
    db: AsyncSession,
    *,
    conversation_id_str: str,
    conversation_title: str,
    message_id_str: str,
    reply_text: str,
    persona_slug: str,
    model_used: str,
) -> None:
    """Upsert mirror ``conversations`` row and insert ``conversation_messages``."""
    try:
        from datetime import UTC, datetime

        from app.models.conversation_mirror import ConversationMessageRecord, ConversationRecord

        cid = conversation_uuid(conversation_id_str)
        mid = conversation_uuid(message_id_str)
        now = datetime.now(UTC)
        title = conversation_title[:5000]
        conv_tbl = ConversationRecord.__table__

        await db.execute(
            pg_insert(conv_tbl)
            .values(
                {
                    conv_tbl.c.id: cid,
                    conv_tbl.c.title: title,
                    conv_tbl.c.created_at: now,
                    conv_tbl.c.updated_at: now,
                }
            )
            .on_conflict_do_update(
                index_elements=[conv_tbl.c.id],
                set_={
                    conv_tbl.c.title: title,
                    conv_tbl.c.updated_at: now,
                },
            )
        )
        await db.execute(
            pg_insert(ConversationMessageRecord).values(
                id=mid,
                conversation_id=cid,
                role="persona",
                content=reply_text,
                persona_slug=persona_slug[:100],
                model_used=model_used[:100],
                created_at=now,
            )
        )
    except Exception:
        logger.exception(
            "conversation_persona_reply: Postgres mirror failed (conversation_id=%s)",
            conversation_id_str,
        )


async def run_conversation_persona_reply(
    db: AsyncSession,
    *,
    conversation_id: str,
    persona_slug: str,
    user_message: str,
    organization_id: str | None,
) -> PersonaReplyResponse:
    """Load thread, synthesize persona reply via litellm, persist JSON + mirror PG."""
    conv = conv_svc.get_conversation(conversation_id, organization_id=organization_id)

    spec = get_spec(persona_slug)
    if spec is None:
        raise UnknownPersonaError(persona_slug)

    thread_txt = _fmt_thread(conv.messages)
    title_line = conv.title.strip() if conv.title else "(untitled)"
    context_md = f"Title: {title_line}\n\n{thread_txt}"

    reply_text, model_used, tokens_used = await generate_persona_reply_text(
        persona_slug=persona_slug,
        user_message=user_message,
        conversation_context_md=context_md,
    )

    r = await db.execute(select(Employee).where(Employee.slug == persona_slug))
    emp = r.scalar_one_or_none()
    lbl = persona_slug
    if emp and emp.display_name and emp.display_name.strip():
        lbl = emp.display_name.strip()
    elif spec.name:
        lbl = spec.name

    msg = conv_svc.append_message(
        conversation_id,
        AppendMessageRequest(
            author=ConversationParticipant(
                id=persona_slug,
                kind="persona",
                display_name=lbl,
            ),
            body_md=reply_text,
            attachments=[],
        ),
        organization_id=organization_id,
    )
    await mirror_persona_message_to_pg(
        db,
        conversation_id_str=conversation_id,
        conversation_title=conv.title,
        message_id_str=msg.id,
        reply_text=reply_text,
        persona_slug=persona_slug,
        model_used=model_used,
    )
    return PersonaReplyResponse(
        reply=reply_text,
        persona_slug=persona_slug,
        model_used=model_used,
        tokens_used=tokens_used,
        message_id=msg.id,
    )
