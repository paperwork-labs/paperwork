"""Tests for ``GET /api/v1/admin/transcripts`` read routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.transcript_episode import TranscriptEpisode


@pytest.mark.no_pg_conv
async def test_transcripts_list_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/admin/transcripts")
    assert res.status_code == 401


@pytest.mark.no_pg_conv
async def test_transcripts_list_detail_cursor_and_missing(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "transcripts-test-secret")
    headers = {"X-Brain-Secret": "transcripts-test-secret"}

    tid = str(uuid.uuid4())
    ingested = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    db_session.add_all(
        [
            TranscriptEpisode(
                transcript_id=tid,
                turn_index=0,
                user_message="plan the rollout",
                assistant_message="here is a draft",
                summary="Rollout plan",
                persona_slugs=["engineering"],
                ingested_at=ingested,
            ),
            TranscriptEpisode(
                transcript_id=tid,
                turn_index=1,
                user_message="follow up",
                assistant_message="done",
                summary=None,
                persona_slugs=["ea"],
                ingested_at=datetime(2026, 5, 4, 12, 5, tzinfo=UTC),
            ),
        ]
    )
    await db_session.commit()

    res = await client.get("/api/v1/admin/transcripts", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["next_cursor"] is None
    assert len(data["items"]) == 1
    row = data["items"][0]
    assert row["id"] == tid
    assert row["session_id"] == tid
    assert row["message_count"] == 2
    assert row["title"] == "Rollout plan"
    assert "engineering" in row["tags"] and "ea" in row["tags"]

    detail_res = await client.get(f"/api/v1/admin/transcripts/{tid}", headers=headers)
    assert detail_res.status_code == 200
    detail_body = detail_res.json()
    assert detail_body["success"] is True
    detail = detail_body["data"]
    assert detail["message_count"] == 2
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["turn_index"] == 0

    missing = await client.get(f"/api/v1/admin/transcripts/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404

    invalid_id = await client.get("/api/v1/admin/transcripts/not-a-uuid", headers=headers)
    assert invalid_id.status_code == 404

    bad_cursor = await client.get("/api/v1/admin/transcripts?cursor=@@@", headers=headers)
    assert bad_cursor.status_code == 400
