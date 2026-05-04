"""Tests for the Postgres-canonical Conversations service (T1.0d Wave 0).

All tests require a running Postgres instance.  If the test database is not
reachable, every test in this module is automatically skipped (same pattern as
other DB-backed tests in this suite via the ``db_session`` fixture).

The service uses sync wrapper functions that internally call async DB helpers
via ``_run()``.  In sync test functions (no running event loop), ``_run()``
uses ``asyncio.run()`` directly — no thread pool needed.

Isolation strategy
------------------
The ``pg_conv_setup`` fixture (autouse) depends on ``db_session``, which runs
``Base.metadata.drop_all`` + ``create_all`` before each test and rolls back
after.  However, since the service commits its own sessions, we additionally
redirect ``app.database.async_session_factory`` to a fresh test-specific
factory connected to the test database.  Data committed during a test is
cleared by ``drop_all`` at the start of the next test.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.database as _db_mod
import app.services.conversations as svc
from app.models import *  # noqa: F403 — register ORM models with Base for create_all
from app.models.base import Base
from app.schemas.conversation import (
    AppendMessageRequest,
    ConversationCreate,
    ConversationParticipant,
)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://brain:brain_dev@localhost:5432/brain_test",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def pg_conv_setup(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None, None]:
    """Create test tables, redirect the service session factory, clean up after.

    Uses ``db_session``-compatible engine (drop_all + create_all) so every test
    starts with empty tables.  Skips if the test database is unavailable.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        await engine.dispose()
        pytest.skip("Test database not available")

    test_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    original_factory = _db_mod.async_session_factory
    monkeypatch.setattr(_db_mod, "async_session_factory", test_factory)

    yield

    monkeypatch.setattr(_db_mod, "async_session_factory", original_factory)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except Exception:
        pass
    await engine.dispose()


@pytest.fixture(autouse=True)
def _use_pg(pg_conv_setup: None) -> None:
    """Pull pg_conv_setup into every test automatically."""


def _make_create(
    title: str = "Test convo",
    body_md: str = "hello",
    urgency: str = "normal",
    tags: list[str] | None = None,
    parent_action_id: str | None = None,
    needs_founder_action: bool = False,
) -> ConversationCreate:
    return ConversationCreate(
        title=title,
        body_md=body_md,
        urgency=urgency,  # type: ignore[arg-type]
        tags=tags or [],
        parent_action_id=parent_action_id,
        needs_founder_action=needs_founder_action,
    )


# ---------------------------------------------------------------------------
# create / get
# ---------------------------------------------------------------------------


def test_create_conversation_returns_id() -> None:
    conv = svc.create_conversation(_make_create())
    assert conv.id
    assert conv.title == "Test convo"


def test_create_conversation_status_normal_is_open() -> None:
    conv = svc.create_conversation(_make_create(urgency="normal"))
    assert conv.status == "open"


def test_create_conversation_status_high_is_needs_action() -> None:
    conv = svc.create_conversation(_make_create(urgency="high"))
    assert conv.status == "needs-action"


def test_create_conversation_status_critical_is_needs_action() -> None:
    conv = svc.create_conversation(_make_create(urgency="critical"))
    assert conv.status == "needs-action"


def test_create_conversation_with_body_creates_first_message() -> None:
    conv = svc.create_conversation(_make_create(body_md="initial body"))
    assert len(conv.messages) == 1
    assert conv.messages[0].body_md == "initial body"


def test_create_conversation_empty_body_no_messages() -> None:
    create = ConversationCreate(title="No body", body_md="")
    conv = svc.create_conversation(create)
    assert conv.messages == []


def test_get_conversation_returns_created() -> None:
    conv = svc.create_conversation(_make_create())
    fetched = svc.get_conversation(conv.id)
    assert fetched.id == conv.id
    assert fetched.title == conv.title


def test_get_conversation_missing_raises_key_error() -> None:
    import uuid

    with pytest.raises(KeyError):
        svc.get_conversation(str(uuid.uuid4()))


def test_get_conversation_invalid_id_raises_key_error() -> None:
    with pytest.raises(KeyError):
        svc.get_conversation("not-a-uuid")


# ---------------------------------------------------------------------------
# list + filter
# ---------------------------------------------------------------------------


def test_list_conversations_empty_returns_zero() -> None:
    page = svc.list_conversations()
    assert page.items == []
    assert page.total == 0
    assert page.next_cursor is None


def test_list_conversations_returns_created() -> None:
    svc.create_conversation(_make_create(title="A"))
    svc.create_conversation(_make_create(title="B"))
    page = svc.list_conversations()
    assert page.total == 2
    titles = {c.title for c in page.items}
    assert "A" in titles
    assert "B" in titles


def test_list_conversations_filter_needs_action() -> None:
    svc.create_conversation(_make_create(urgency="high"))
    svc.create_conversation(_make_create(urgency="normal"))
    page = svc.list_conversations(status_filter="needs-action")
    assert page.total == 1
    assert page.items[0].urgency == "high"


def test_list_conversations_filter_open() -> None:
    svc.create_conversation(_make_create(urgency="normal"))
    svc.create_conversation(_make_create(urgency="high"))
    page = svc.list_conversations(status_filter="open")
    assert page.total == 1


def test_list_conversations_pagination_cursor() -> None:
    for i in range(5):
        svc.create_conversation(_make_create(title=f"Conv {i}"))
    page1 = svc.list_conversations(limit=3)
    assert len(page1.items) == 3
    assert page1.next_cursor is not None

    page2 = svc.list_conversations(limit=3, cursor=page1.next_cursor)
    assert len(page2.items) == 2
    assert page2.next_cursor is None

    all_ids = [c.id for c in page1.items] + [c.id for c in page2.items]
    assert len(set(all_ids)) == 5


# ---------------------------------------------------------------------------
# full-text search
# ---------------------------------------------------------------------------


def test_search_finds_by_message_content() -> None:
    svc.create_conversation(_make_create(title="Invoice delay", body_md="Invoice processing delay"))
    svc.create_conversation(_make_create(title="Unrelated", body_md="Something else entirely"))
    results = svc.search_conversations("Invoice")
    titles = [r.title for r in results]
    assert any("Invoice" in t for t in titles)


def test_search_finds_by_title_ilike() -> None:
    svc.create_conversation(_make_create(title="Quarterly Budget Review", body_md="details here"))
    svc.create_conversation(_make_create(title="Unrelated", body_md="unrelated"))
    results = svc.search_conversations("Quarterly")
    assert any("Quarterly" in r.title for r in results)


def test_search_returns_empty_for_no_match() -> None:
    svc.create_conversation(_make_create(title="Something random"))
    results = svc.search_conversations("xyzzy-no-match-ever")
    assert results == []


# ---------------------------------------------------------------------------
# append_message
# ---------------------------------------------------------------------------


def test_append_message_adds_to_thread() -> None:
    conv = svc.create_conversation(_make_create(body_md=""))
    req = AppendMessageRequest(
        author=ConversationParticipant(id="founder", kind="founder"),
        body_md="reply text",
        attachments=[],
    )
    msg = svc.append_message(conv.id, req)
    assert msg.body_md == "reply text"
    reloaded = svc.get_conversation(conv.id)
    assert any(m.id == msg.id for m in reloaded.messages)


def test_append_message_missing_conv_raises() -> None:
    import uuid

    req = AppendMessageRequest(
        author=ConversationParticipant(id="founder", kind="founder"),
        body_md="x",
        attachments=[],
    )
    with pytest.raises(KeyError):
        svc.append_message(str(uuid.uuid4()), req)


def test_append_message_with_parent_sets_parent_message_id() -> None:
    conv = svc.create_conversation(_make_create(body_md="root"))
    root = conv.messages[0]
    req = AppendMessageRequest(
        author=ConversationParticipant(id="founder", kind="founder"),
        body_md="reply text",
        attachments=[],
        parent_message_id=root.id,
    )
    msg = svc.append_message(conv.id, req)
    assert msg.parent_message_id == root.id


def test_append_message_bad_parent_raises_value_error() -> None:
    conv = svc.create_conversation(_make_create(body_md="only"))
    req = AppendMessageRequest(
        author=ConversationParticipant(id="founder", kind="founder"),
        body_md="orphan",
        attachments=[],
        parent_message_id="no-such-parent",
    )
    with pytest.raises(ValueError, match="Parent message"):
        svc.append_message(conv.id, req)


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------


def test_update_status_resolved() -> None:
    conv = svc.create_conversation(_make_create(urgency="high"))
    assert conv.status == "needs-action"
    updated = svc.update_conversation_status(conv.id, "resolved")
    assert updated.status == "resolved"
    assert svc.get_conversation(conv.id).status == "resolved"


def test_update_status_clears_snooze_until() -> None:
    conv = svc.create_conversation(_make_create())
    snoozed = svc.snooze(conv.id, datetime.now(UTC) + timedelta(hours=1))
    assert snoozed.snooze_until is not None
    updated = svc.update_conversation_status(conv.id, "resolved")
    assert updated.snooze_until is None


# ---------------------------------------------------------------------------
# snooze
# ---------------------------------------------------------------------------


def test_snooze_sets_status_and_until() -> None:
    conv = svc.create_conversation(_make_create())
    until = datetime.now(UTC) + timedelta(hours=4)
    snoozed = svc.snooze(conv.id, until)
    assert snoozed.status == "snoozed"
    assert snoozed.snooze_until is not None
    assert abs((snoozed.snooze_until - until).total_seconds()) < 1


# ---------------------------------------------------------------------------
# react
# ---------------------------------------------------------------------------


def test_react_adds_reaction() -> None:
    conv = svc.create_conversation(_make_create(body_md="msg"))
    msg = conv.messages[0]
    result = svc.react(conv.id, msg.id, "👍", "founder")
    assert "founder" in result.reactions.get("👍", [])


def test_react_toggle_removes_existing() -> None:
    conv = svc.create_conversation(_make_create(body_md="msg"))
    msg = conv.messages[0]
    svc.react(conv.id, msg.id, "👍", "founder")
    result = svc.react(conv.id, msg.id, "👍", "founder")
    assert "👍" not in result.reactions


def test_react_missing_message_raises() -> None:
    conv = svc.create_conversation(_make_create(body_md="msg"))
    with pytest.raises(KeyError):
        svc.react(conv.id, "no-such-msg", "👍", "founder")


# ---------------------------------------------------------------------------
# organization isolation
# ---------------------------------------------------------------------------


def test_organization_isolation_get() -> None:
    conv = svc.create_conversation(_make_create(), organization_id="org-a")
    with pytest.raises(PermissionError):
        svc.get_conversation(conv.id, organization_id="org-b")


def test_organization_isolation_list() -> None:
    svc.create_conversation(_make_create(title="Org A"), organization_id="org-a")
    svc.create_conversation(_make_create(title="Org B"), organization_id="org-b")
    page_a = svc.list_conversations(organization_id="org-a")
    assert page_a.total == 1
    assert page_a.items[0].title == "Org A"


# ---------------------------------------------------------------------------
# tag validation
# ---------------------------------------------------------------------------


def test_invalid_expense_tag_raises() -> None:
    with pytest.raises(ValueError, match="Unknown expense-related tag"):
        svc.create_conversation(_make_create(tags=["expense-unknown-tag"]))


def test_valid_expense_tags_accepted() -> None:
    for tag in ["expense-approval", "expense-monthly-close", "expense-rule-change"]:
        conv = svc.create_conversation(_make_create(tags=[tag]))
        assert tag in conv.tags


# ---------------------------------------------------------------------------
# unread_count / badge metrics
# ---------------------------------------------------------------------------


def test_unread_count_needs_action() -> None:
    svc.create_conversation(_make_create(urgency="high"))
    svc.create_conversation(_make_create(urgency="critical"))
    svc.create_conversation(_make_create(urgency="normal"))
    count = svc.unread_count(status_filter="needs-action")
    assert count == 2


def test_needs_action_badge_metrics_includes_critical_flag() -> None:
    svc.create_conversation(_make_create(urgency="critical"))
    svc.create_conversation(_make_create(urgency="high"))
    metrics = svc.needs_action_badge_metrics(status_filter="needs-action")
    assert metrics["count"] == 2
    assert metrics["has_critical"] is True


# ---------------------------------------------------------------------------
# persona reply preserved (author stored and retrieved)
# ---------------------------------------------------------------------------


def test_persona_reply_author_round_trips() -> None:
    conv = svc.create_conversation(_make_create(body_md="question"))
    persona_author = ConversationParticipant(
        id="ea",
        kind="persona",
        display_name="Executive Assistant",
    )
    req = AppendMessageRequest(
        author=persona_author,
        body_md="Here is the answer.",
        attachments=[],
    )
    msg = svc.append_message(conv.id, req)
    reloaded = svc.get_conversation(conv.id)
    persona_msg = next(m for m in reloaded.messages if m.id == msg.id)
    assert persona_msg.author.kind == "persona"
    assert persona_msg.author.id == "ea"
    assert persona_msg.author.display_name == "Executive Assistant"


# ---------------------------------------------------------------------------
# backfill (founder_actions → Conversations)
# ---------------------------------------------------------------------------


def test_backfill_from_json_fallback(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Backfill reads the Studio JSON cache when no YAML exists."""
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    studio_dir = tmp_path / "apps" / "studio" / "src" / "data"
    studio_dir.mkdir(parents=True, exist_ok=True)
    import json

    payload = {
        "tiers": [
            {
                "id": "critical",
                "label": "Critical",
                "items": [
                    {
                        "title": "Fix the broken pipeline",
                        "why": "CI is red",
                        "where": "GitHub Actions",
                        "steps": ["1. Check logs"],
                        "verification": "CI green",
                        "eta": "30 min",
                        "runbookUrl": "https://example.com",
                        "source": "manual",
                    }
                ],
            },
            {
                "id": "operational",
                "label": "Operational",
                "items": [
                    {
                        "title": "Rotate API key",
                        "why": "Key expires soon",
                        "where": "Vendor dashboard",
                        "steps": [],
                        "verification": "Old key deactivated",
                        "eta": "10 min",
                        "runbookUrl": "https://example.com",
                        "source": "manual",
                    }
                ],
            },
        ],
        "resolved": [],
        "counts": {"critical": 1, "operational": 1, "totalPending": 2},
    }
    (studio_dir / "founder-actions.json").write_text(json.dumps(payload), encoding="utf-8")

    created = svc.backfill_from_founder_actions_yaml()
    assert created == 2

    page = svc.list_conversations(status_filter="needs-action")
    assert page.total == 2
    for c in page.items:
        assert c.needs_founder_action is True
    titles = {c.title for c in page.items}
    assert "Fix the broken pipeline" in titles
    assert "Rotate API key" in titles


def test_backfill_reads_brain_data_json(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """apis/brain/data/founder_actions.json is used when YAML + Studio JSON absent."""
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    data_dir = tmp_path / "apis" / "brain" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    import json

    payload = {
        "tiers": [
            {
                "id": "operational",
                "items": [
                    {
                        "title": "Brain JSON only item",
                        "why": "w",
                        "where": "x",
                        "steps": [],
                        "verification": "y",
                        "eta": "1h",
                        "runbookUrl": "https://example.com",
                        "source": "runbook",
                    }
                ],
            }
        ],
        "counts": {},
    }
    (data_dir / "founder_actions.json").write_text(json.dumps(payload), encoding="utf-8")
    first = svc.backfill_founder_actions_detailed()
    assert first.created == 1
    assert first.source_kind == "brain_json"
    second = svc.backfill_founder_actions_detailed()
    assert second.created == 0  # idempotent


def test_backfill_is_idempotent(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running backfill twice creates no duplicates."""
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    studio_dir = tmp_path / "apps" / "studio" / "src" / "data"
    studio_dir.mkdir(parents=True, exist_ok=True)
    import json

    payload = {
        "tiers": [
            {
                "id": "critical",
                "label": "C",
                "items": [
                    {
                        "title": "Item one",
                        "why": "x",
                        "where": "y",
                        "steps": [],
                        "verification": "z",
                        "eta": "1h",
                        "runbookUrl": "https://x.com",
                        "source": "s",
                    }
                ],
            }
        ],
        "resolved": [],
        "counts": {},
    }
    (studio_dir / "founder-actions.json").write_text(json.dumps(payload), encoding="utf-8")

    first = svc.backfill_from_founder_actions_yaml()
    second = svc.backfill_from_founder_actions_yaml()
    assert first == 1
    assert second == 0


def test_backfill_parent_action_id_set(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    studio_dir = tmp_path / "apps" / "studio" / "src" / "data"
    studio_dir.mkdir(parents=True, exist_ok=True)
    import json

    payload = {
        "tiers": [
            {
                "id": "critical",
                "label": "C",
                "items": [
                    {
                        "title": "Do something important",
                        "why": "y",
                        "where": "z",
                        "steps": [],
                        "verification": "v",
                        "eta": "1h",
                        "runbookUrl": "https://x.com",
                        "source": "s",
                    }
                ],
            }
        ],
        "resolved": [],
        "counts": {},
    }
    (studio_dir / "founder-actions.json").write_text(json.dumps(payload), encoding="utf-8")

    svc.backfill_from_founder_actions_yaml()
    page = svc.list_conversations()
    conv = page.items[0]
    assert conv.parent_action_id is not None
    assert "do_something_important" in conv.parent_action_id
