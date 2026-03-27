"""Tests for knowledge seed ingestion and retrieval."""

import os
import tempfile

import pytest

from app.services.memory import search_episodes, store_episode
from app.services.seed import _chunk_by_headers, ingest_docs


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
    )
    await db_session.flush()

    episodes = await search_episodes(
        db_session,
        organization_id="test-org",
        query="MeF transmitter",
        limit=5,
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
    )
    assert episodes == []
