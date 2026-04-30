"""Tests for the unified Conversations service (WS-69 PR E).

Covers: create, get, list, filter, search, append_message, update_status,
snooze, react, backfill, unread_count.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import app.services.conversations as svc
from app.schemas.conversation import (
    AppendMessageRequest,
    ConversationCreate,
    ConversationParticipant,
)


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect all service file I/O to a temp directory."""
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    # The service resolves to tmp_path/apis/brain/data
    data_dir = tmp_path / "apis" / "brain" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _make_create(
    title: str = "Test convo",
    body_md: str = "hello",
    urgency: str = "normal",
    tags: list[str] | None = None,
    parent_action_id: str | None = None,
) -> ConversationCreate:
    return ConversationCreate(
        title=title,
        body_md=body_md,
        urgency=urgency,  # type: ignore[arg-type]
        tags=tags or [],
        parent_action_id=parent_action_id,
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
    with pytest.raises(KeyError):
        svc.get_conversation("does-not-exist")


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
    svc.create_conversation(_make_create(urgency="high"))  # → needs-action
    svc.create_conversation(_make_create(urgency="normal"))  # → open
    page = svc.list_conversations(status_filter="needs-action")
    assert page.total == 1
    assert page.items[0].urgency == "high"


def test_list_conversations_filter_open() -> None:
    svc.create_conversation(_make_create(urgency="normal"))  # open
    svc.create_conversation(_make_create(urgency="high"))  # needs-action
    page = svc.list_conversations(status_filter="open")
    assert page.total == 1


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
    req = AppendMessageRequest(
        author=ConversationParticipant(id="founder", kind="founder"),
        body_md="x",
        attachments=[],
    )
    with pytest.raises(KeyError):
        svc.append_message("no-such-id", req)


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
    # Stored as timezone-aware ISO; compare without microseconds
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
    result = svc.react(conv.id, msg.id, "👍", "founder")  # toggle off
    assert "👍" not in result.reactions


def test_react_missing_message_raises() -> None:
    conv = svc.create_conversation(_make_create(body_md="msg"))
    with pytest.raises(KeyError):
        svc.react(conv.id, "no-such-msg", "👍", "founder")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_finds_by_title() -> None:
    svc.create_conversation(_make_create(title="Invoice processing delay"))
    svc.create_conversation(_make_create(title="Unrelated topic"))
    results = svc.search_conversations("Invoice")
    titles = [r.title for r in results]
    assert any("Invoice" in t for t in titles)


def test_search_returns_empty_for_no_match() -> None:
    svc.create_conversation(_make_create(title="Something random"))
    results = svc.search_conversations("xyzzy-no-match-ever")
    assert results == []


# ---------------------------------------------------------------------------
# unread_count
# ---------------------------------------------------------------------------


def test_unread_count_needs_action() -> None:
    svc.create_conversation(_make_create(urgency="high"))
    svc.create_conversation(_make_create(urgency="critical"))
    svc.create_conversation(_make_create(urgency="normal"))  # open
    count = svc.unread_count(status_filter="needs-action")
    assert count == 2


def test_needs_action_badge_metrics_includes_critical_flag() -> None:
    svc.create_conversation(_make_create(urgency="critical"))
    svc.create_conversation(_make_create(urgency="high"))
    metrics = svc.needs_action_badge_metrics(status_filter="needs-action")
    assert metrics["count"] == 2
    assert metrics["has_critical"] is True


# ---------------------------------------------------------------------------
# backfill
# ---------------------------------------------------------------------------


def test_backfill_from_json_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Backfill reads the Studio JSON cache when no YAML exists."""
    data_dir = tmp_path / "apis" / "brain" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))

    # Create a minimal Studio-format founder-actions.json
    studio_dir = tmp_path / "apps" / "studio" / "src" / "data"
    studio_dir.mkdir(parents=True, exist_ok=True)
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


def test_backfill_reads_brain_data_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """apis/brain/data/founder_actions.json is used when YAML + Studio JSON are absent."""
    data_dir = tmp_path / "apis" / "brain" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
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
    assert second.created == 0


def test_backfill_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running backfill twice creates no duplicates."""
    data_dir = tmp_path / "apis" / "brain" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))

    studio_dir = tmp_path / "apps" / "studio" / "src" / "data"
    studio_dir.mkdir(parents=True, exist_ok=True)
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
    assert second == 0  # idempotent


def test_backfill_parent_action_id_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "apis" / "brain" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))

    studio_dir = tmp_path / "apps" / "studio" / "src" / "data"
    studio_dir.mkdir(parents=True, exist_ok=True)
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
