"""Tests for knowledge seed ingestion and retrieval."""

import os
import tempfile

import pytest

from app.services.memory import search_episodes, store_episode
from app.services.seed import (
    SPRINT_LESSONS_SOURCE,
    _chunk_by_headers,
    _extract_lessons,
    ingest_docs,
    ingest_sprint_lessons,
)


class TestChunking:
    """Test markdown chunking logic."""

    def test_chunk_by_headers_basic(self):
        text = """## Introduction
This is the intro.

## Methods
This describes the methods.

## Results
Here are the results.
"""
        chunks = _chunk_by_headers(text)
        assert len(chunks) == 3
        assert chunks[0]["header"] == "Introduction"
        assert chunks[1]["header"] == "Methods"
        assert chunks[2]["header"] == "Results"

    def test_chunk_by_headers_large_section(self):
        large_content = "x" * 3000
        text = f"## Large Section\n{large_content}"
        chunks = _chunk_by_headers(text, max_size=2000)
        assert len(chunks) >= 2
        assert chunks[0]["header"] == "Large Section"
        assert chunks[1]["header"] == "Large Section (part 2)"

    def test_chunk_by_headers_no_headers(self):
        text = "Just some text without headers."
        chunks = _chunk_by_headers(text)
        assert len(chunks) == 1
        assert chunks[0]["header"] == "Overview"


@pytest.mark.asyncio
async def test_ingest_docs_creates_episodes(db_session):
    """Test that ingest_docs creates episodes from docs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = os.path.join(tmpdir, "docs")
        os.makedirs(docs_dir)

        with open(os.path.join(docs_dir, "KNOWLEDGE.md"), "w") as f:
            f.write("""# Knowledge Base

## Decision D1
We decided to use Cloud Vision for OCR.

## Decision D2
Railway was replaced with Render.
""")

        count = await ingest_docs(db_session, tmpdir, organization_id="test-org")
        assert count >= 2


@pytest.mark.asyncio
async def test_seeded_docs_are_retrievable(db_session):
    """Test that seeded docs can be retrieved via search."""
    await store_episode(
        db_session,
        organization_id="test-org",
        source="seed:docs",
        summary="[KNOWLEDGE.md] Decision D4 — MeF Transmitter",
        full_context="We decided to own our IRS MeF Transmitter as the north star.",
        importance=0.8,
        skip_embedding=True,
    )
    await db_session.flush()

    episodes = await search_episodes(
        db_session,
        organization_id="test-org",
        query="MeF transmitter",
        limit=5,
        skip_embedding=True,
    )

    assert len(episodes) >= 1
    assert any("MeF" in e.summary for e in episodes)


@pytest.mark.asyncio
async def test_search_returns_empty_for_no_matches(db_session):
    """Test that search returns empty list when no matches."""
    episodes = await search_episodes(
        db_session,
        organization_id="nonexistent-org",
        query="something random",
        limit=5,
        skip_embedding=True,
    )
    assert episodes == []


class TestSprintLessonsExtraction:
    """The lesson-extraction regex needs to be permissive enough to handle
    every shape we use in docs/sprints/, but strict enough not to grab
    bullets from Tracks tables or Follow-ups."""

    def test_basic_what_we_learned(self):
        md = """# Sprint X

## Outcome

- something shipped

## What we learned

- Lesson one is about caching.
- Lesson two is about retries.

## Follow-ups

- this should not be picked up
"""
        assert _extract_lessons(md) == [
            "Lesson one is about caching.",
            "Lesson two is about retries.",
        ]

    def test_lessons_alias_heading(self):
        md = """## Lessons learned

* Bullet with a star marker still counts.
"""
        assert _extract_lessons(md) == ["Bullet with a star marker still counts."]

    def test_no_lessons_section_returns_empty(self):
        md = "## Outcome\n\n- only outcomes here\n"
        assert _extract_lessons(md) == []

    def test_stops_at_next_h2(self):
        md = """## What we learned

- only this lesson

## Tracks

- not a lesson
- also not a lesson
"""
        assert _extract_lessons(md) == ["only this lesson"]


@pytest.mark.asyncio
async def test_ingest_sprint_lessons_is_idempotent(db_session):
    """Re-running the ingester must not duplicate already-stored lessons."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sprints_dir = os.path.join(tmpdir, "docs", "sprints")
        os.makedirs(sprints_dir)
        with open(os.path.join(sprints_dir, "EXAMPLE_SPRINT.md"), "w") as f:
            f.write("""---
status: shipped
---

# Example sprint

## What we learned

- Cheap-model parallel delegation cleared the docs inventory in minutes.
- A repo-native tracker beats Jira when docs are where work is happening.
""")

        first = await ingest_sprint_lessons(
            db_session, tmpdir, organization_id="test-org", skip_embedding=True
        )
        await db_session.flush()
        assert first["created"] == 2
        assert first["sprints_scanned"] == 1

        # Second run sees the same sha1-keyed source_refs and inserts nothing.
        second = await ingest_sprint_lessons(
            db_session, tmpdir, organization_id="test-org", skip_embedding=True
        )
        assert second["created"] == 0
        assert second["skipped"] == 2


@pytest.mark.asyncio
async def test_ingested_lessons_are_retrievable(db_session):
    """End-to-end: lesson bullets must be findable via the same search
    pipeline that runs over seed:docs episodes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sprints_dir = os.path.join(tmpdir, "docs", "sprints")
        os.makedirs(sprints_dir)
        with open(os.path.join(sprints_dir, "DOCS_2026Q2.md"), "w") as f:
            f.write("""## What we learned

- Server components reading env-injected data MUST mark force-dynamic.
""")

        await ingest_sprint_lessons(
            db_session, tmpdir, organization_id="test-org", skip_embedding=True
        )
        await db_session.flush()

        results = await search_episodes(
            db_session,
            organization_id="test-org",
            query="force-dynamic env",
            limit=5,
            skip_embedding=True,
        )
        assert len(results) >= 1
        assert all(ep.source == SPRINT_LESSONS_SOURCE for ep in results)
