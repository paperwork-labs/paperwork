"""Pydantic schemas for the unified Conversations surface (WS-69 PR E).

Models the Brain-canonical Conversation store: participants, messages,
attachments, cursor-paginated list response, and request bodies for create /
update operations.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field


class ConversationLinks(BaseModel):
    """Typed cross-links from a Conversation to other Brain entities."""

    expense_id: str | None = None


class ConversationParticipant(BaseModel):
    id: str
    kind: Literal["founder", "persona", "cofounder", "external"]
    display_name: str | None = None


class Attachment(BaseModel):
    id: str
    kind: Literal["image", "file", "link"]
    url: str
    mime: str | None = None
    size_bytes: int | None = None
    thumbnail_url: str | None = None


class ThreadMessage(BaseModel):
    id: str
    author: ConversationParticipant
    body_md: str
    attachments: list[Attachment] = Field(default_factory=list)
    created_at: datetime
    reactions: dict[str, list[str]] = Field(default_factory=dict)


UrgencyLevel = Literal["info", "normal", "high", "critical"]
StatusLevel = Literal["open", "needs-action", "snoozed", "resolved", "archived"]


class Conversation(BaseModel):
    id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    urgency: UrgencyLevel = "normal"
    persona: str | None = None
    participants: list[ConversationParticipant] = Field(default_factory=list)
    messages: list[ThreadMessage] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    status: StatusLevel = "open"
    snooze_until: datetime | None = None
    parent_action_id: str | None = None
    links: ConversationLinks | None = None
    needs_founder_action: bool = False


class ConversationsListPage(BaseModel):
    """Cursor-paginated response for GET /admin/conversations."""

    items: list[Conversation]
    next_cursor: str | None = None
    total: int


class ConversationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    body_md: str = ""
    tags: list[str] = Field(default_factory=list)
    urgency: UrgencyLevel = "normal"
    persona: str | None = None
    participants: list[ConversationParticipant] = Field(default_factory=list)
    parent_action_id: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    links: ConversationLinks | None = None
    needs_founder_action: bool = False


class ConversationUpdate(BaseModel):
    title: str | None = None
    tags: list[str] | None = None
    urgency: UrgencyLevel | None = None
    persona: str | None = None
    status: StatusLevel | None = None
    snooze_until: datetime | None = None


class AppendMessageRequest(BaseModel):
    author: ConversationParticipant
    body_md: str = Field(..., min_length=1)
    attachments: list[Attachment] = Field(default_factory=list)


class ReactRequest(BaseModel):
    emoji: str = Field(..., min_length=1, max_length=32)
    participant_id: str


class SnoozeRequest(BaseModel):
    until: datetime


class StatusUpdateRequest(BaseModel):
    status: StatusLevel
