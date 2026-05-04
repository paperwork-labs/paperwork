"""Admin read models for grouped Cursor transcript sessions (transcript_episodes).

medallion: ops
"""

from __future__ import annotations

from pydantic import BaseModel


class TranscriptListItem(BaseModel):
    id: str
    session_id: str
    started_at: str
    ended_at: str
    title: str
    tags: list[str]
    message_count: int


class TranscriptListPayload(BaseModel):
    items: list[TranscriptListItem]
    next_cursor: str | None = None


class TranscriptMessageItem(BaseModel):
    turn_index: int
    user_message: str
    assistant_message: str
    summary: str | None = None
    ingested_at: str


class TranscriptDetailPayload(BaseModel):
    id: str
    session_id: str
    started_at: str
    ended_at: str
    title: str
    tags: list[str]
    message_count: int
    messages: list[TranscriptMessageItem]
