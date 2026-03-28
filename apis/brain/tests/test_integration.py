"""Integration tests for the Brain pipeline: seed → process → retrieve."""

import pytest

from app.services import agent, memory


@pytest.mark.asyncio
async def test_store_and_search_basic(db_session):
    """Basic test: store an episode, then search for it."""
    episode = await memory.store_episode(
        db_session,
        organization_id="test-org",
        source="test",
        summary="The MeF transmitter deadline is October 2026",
        full_context="IRS ATS testing must complete in October 2026 for January 2027 launch.",
        importance=0.8,
        skip_embedding=True,
    )
    await db_session.flush()

    assert episode.id is not None
    assert episode.organization_id == "test-org"
    assert "MeF" in episode.summary

    episodes = await memory.search_episodes(
        db_session,
        organization_id="test-org",
        query="MeF deadline",
        limit=5,
        skip_embedding=True,
    )

    assert len(episodes) >= 1
    assert any("MeF" in e.summary for e in episodes)


@pytest.mark.asyncio
async def test_agent_process_uses_memory(db_session, redis_mock):
    """Test that agent.process retrieves relevant memory."""
    await memory.store_episode(
        db_session,
        organization_id="test-org",
        source="seed:docs",
        summary="[TASKS.md] Phase 11 Brain API",
        full_context="P11.1 is the Brain API scaffold. P11.2 is the agent loop.",
        importance=0.8,
        skip_embedding=True,
    )
    await db_session.flush()

    result = await agent.process(
        db_session,
        redis_mock,
        organization_id="test-org",
        org_name="Test Org",
        message="What is P11.1?",
        channel="test",
        request_id="test-123",
    )

    assert result["response"] is not None
    assert result["persona"] is not None


@pytest.mark.asyncio
async def test_memory_fatigue_reduces_score(db_session, redis_mock):
    """D15: Recently-recalled episodes should be penalized."""
    episode = await memory.store_episode(
        db_session,
        organization_id="test-org",
        source="test",
        summary="Unique test content for fatigue testing",
        importance=0.8,
        skip_embedding=True,
    )
    await db_session.flush()

    await memory.mark_recalled(redis_mock, "test-org", [episode.id])

    fatigue_ids = await memory.get_fatigue_ids(redis_mock, "test-org")
    assert episode.id in fatigue_ids


@pytest.mark.asyncio
async def test_pii_scrubbed_on_store(db_session):
    """D11: PII should be scrubbed before storage."""
    episode = await memory.store_episode(
        db_session,
        organization_id="test-org",
        source="test",
        summary="User SSN is 123-45-6789 and phone is 555-123-4567",
        skip_embedding=True,
    )
    await db_session.flush()

    assert "123-45-6789" not in episode.summary
    assert "XXX-XX-" in episode.summary or "[SSN]" in episode.summary


@pytest.mark.asyncio
async def test_organization_isolation(db_session):
    """Episodes from one org should not be visible to another."""
    await memory.store_episode(
        db_session,
        organization_id="org-a",
        source="test",
        summary="Secret data for org A only",
        skip_embedding=True,
    )
    await memory.store_episode(
        db_session,
        organization_id="org-b",
        source="test",
        summary="Secret data for org B only",
        skip_embedding=True,
    )
    await db_session.flush()

    episodes_a = await memory.search_episodes(
        db_session,
        organization_id="org-a",
        query="secret data",
        limit=10,
        skip_embedding=True,
    )

    episodes_b = await memory.search_episodes(
        db_session,
        organization_id="org-b",
        query="secret data",
        limit=10,
        skip_embedding=True,
    )

    assert all(e.organization_id == "org-a" for e in episodes_a)
    assert all(e.organization_id == "org-b" for e in episodes_b)


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_processing(db_session, redis_mock):
    """D10: Duplicate requests should be detected."""
    from app.services import idempotency

    request_id = "unique-request-123"
    org_id = "test-org"

    is_dup_1 = await idempotency.check_and_set(redis_mock, request_id, org_id)
    assert is_dup_1 is False

    is_dup_2 = await idempotency.check_and_set(redis_mock, request_id, org_id)
    assert is_dup_2 is True
