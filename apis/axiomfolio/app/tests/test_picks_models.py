"""Tests for the picks pipeline data models.

Covers:
* Migration shape — every table has expected columns and indexes.
* Model invariants — defaults, enum coercion, relationship loading.
* Lifecycle helpers — ``ValidatedPick.is_active`` correctness.
* Multi-tenancy boundary — engagements scope per user.
* Provenance contract — at least one of ``source_email_parse_id``
  or ``promoted_from_candidate_id`` is set for picks that originate
  from upstream signals (manual UI picks may have neither).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import (
    Candidate,
    CandidateQueueState,
    EmailInbox,
    EmailParse,
    EmailParseStatus,
    EngagementType,
    MacroOutlook,
    PickAction,
    PickEngagement,
    PickStatus,
    PositionChange,
    SourceAttribution,
    SourceType,
    User,
    ValidatedPick,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def validator_user(db_session) -> User:
    user = User(
        username="validator_one",
        email="validator_one@axiomfolio.test",
        full_name="Validator One",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def subscriber_user(db_session) -> User:
    user = User(
        username="subscriber_one",
        email="subscriber_one@axiomfolio.test",
        full_name="Subscriber One",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def email(db_session) -> EmailInbox:
    msg = EmailInbox(
        message_id="<test-msg-001@axiomfolio.test>",
        source_label="validator_primary",
        sender="validator@example.com",
        subject="Picks for Monday",
        body_text="Buy NVDA on the breakout. Stop 110.",
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(msg)
    db_session.flush()
    return msg


@pytest.fixture
def email_parse(db_session, email: EmailInbox) -> EmailParse:
    parse = EmailParse(
        email_id=email.id,
        schema_version="picks_v1",
        parser_model="gpt-4o-mini",
        parser_provider="openai",
        structured_output={"picks": [{"symbol": "NVDA", "action": "buy"}]},
        status=EmailParseStatus.OK,
    )
    db_session.add(parse)
    db_session.flush()
    return parse


# ---------------------------------------------------------------------------
# Schema shape (verifies the migration created what the model expects)
# ---------------------------------------------------------------------------


class TestSchemaShape:
    """Sanity-check that the migration created the tables with the columns
    the model expects. If this fails the migration and model have drifted."""

    EXPECTED_TABLES = {
        "email_inbox",
        "email_parses",
        "candidates",
        "validated_picks",
        "pick_engagements",
        "source_attributions",
        "macro_outlooks",
        "position_changes",
        "picks_audit_log",
    }

    def test_all_tables_exist(self, db_session):
        inspector = inspect(db_session.bind)
        existing = set(inspector.get_table_names())
        missing = self.EXPECTED_TABLES - existing
        assert not missing, f"Migration is missing tables: {sorted(missing)}"

    @pytest.mark.parametrize(
        "table,required",
        [
            (
                "email_inbox",
                {
                    "id",
                    "message_id",
                    "sender",
                    "received_at",
                    "source_label",
                    "raw_payload",
                    "ingestion_status",
                },
            ),
            ("email_parses", {"id", "email_id", "schema_version", "parser_model", "status"}),
            (
                "candidates",
                {
                    "id",
                    "symbol",
                    "generator_name",
                    "score",
                    "pick_quality_score",
                    "pick_quality_breakdown",
                    "status",
                    "state_transitioned_at",
                    "state_transitioned_by",
                    "source_email_parse_id",
                    "suggested_target",
                    "suggested_stop",
                    "published_at",
                },
            ),
            (
                "validated_picks",
                {
                    "id",
                    "source_email_parse_id",
                    "promoted_from_candidate_id",
                    "validator_user_id",
                    "validator_pseudonym",
                    "symbol",
                    "action",
                    "status",
                    "expires_at",
                    "superseded_by_id",
                },
            ),
            (
                "pick_engagements",
                {"id", "pick_id", "user_id", "engagement_type", "occurred_at"},
            ),
            (
                "source_attributions",
                {"id", "artifact_kind", "artifact_id", "source_type"},
            ),
            ("macro_outlooks", {"id", "validator_user_id", "thesis", "status"}),
            ("position_changes", {"id", "validator_user_id", "symbol", "action", "status"}),
            (
                "picks_audit_log",
                {
                    "id",
                    "candidate_id",
                    "from_state",
                    "to_state",
                    "actor_user_id",
                    "reason",
                    "created_at",
                },
            ),
        ],
    )
    def test_required_columns_present(self, db_session, table, required):
        inspector = inspect(db_session.bind)
        cols = {c["name"] for c in inspector.get_columns(table)}
        missing = required - cols
        assert not missing, f"{table}: migration is missing columns {sorted(missing)}"


# ---------------------------------------------------------------------------
# EmailInbox / EmailParse
# ---------------------------------------------------------------------------


class TestEmailIngestion:
    def test_email_uniqueness_on_message_id(self, db_session, email):
        duplicate = EmailInbox(
            message_id=email.message_id,
            source_label="validator_primary",
            sender="other@example.com",
            received_at=datetime.now(timezone.utc),
        )
        with pytest.raises(IntegrityError):
            try:
                db_session.add(duplicate)
                db_session.flush()
            except IntegrityError:
                db_session.rollback()
                raise

    def test_email_parse_back_relationship(self, db_session, email, email_parse):
        db_session.refresh(email)
        assert any(p.id == email_parse.id for p in email.parses)
        assert email_parse.email is email

    def test_email_parse_uniqueness_on_schema_and_model(
        self, db_session, email, email_parse
    ):
        duplicate = EmailParse(
            email_id=email.id,
            schema_version=email_parse.schema_version,
            parser_model=email_parse.parser_model,
            status=EmailParseStatus.OK,
        )
        with pytest.raises(IntegrityError):
            try:
                db_session.add(duplicate)
                db_session.flush()
            except IntegrityError:
                db_session.rollback()
                raise

    def test_email_parse_status_default(self, db_session, email):
        parse = EmailParse(
            email_id=email.id,
            schema_version="picks_v1",
            parser_model="gpt-4o-mini",
        )
        db_session.add(parse)
        db_session.flush()
        db_session.refresh(parse)
        assert parse.status == EmailParseStatus.PENDING


# ---------------------------------------------------------------------------
# ValidatedPick lifecycle
# ---------------------------------------------------------------------------


class TestValidatedPickLifecycle:
    def _pick(self, validator_user, **kwargs):
        defaults = dict(
            validator_user_id=validator_user.id,
            symbol="NVDA",
            action=PickAction.BUY,
            reason_summary="Stage 2A breakout, RS Mansfield > 70.",
            suggested_entry=Decimal("125.50"),
            suggested_stop=Decimal("119.00"),
            suggested_size_pct=Decimal("0.0500"),
        )
        defaults.update(kwargs)
        return ValidatedPick(**defaults)

    def test_default_pseudonym_is_twisted_slice(self, db_session, validator_user):
        pick = self._pick(validator_user)
        db_session.add(pick)
        db_session.flush()
        db_session.refresh(pick)
        assert pick.validator_pseudonym == "Twisted Slice"

    def test_draft_pick_is_not_active(self, db_session, validator_user):
        pick = self._pick(validator_user)
        db_session.add(pick)
        db_session.flush()
        assert pick.is_active() is False

    def test_published_pick_with_future_expiry_is_active(
        self, db_session, validator_user
    ):
        pick = self._pick(
            validator_user,
            status=PickStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=5),
        )
        db_session.add(pick)
        db_session.flush()
        assert pick.is_active() is True

    def test_published_pick_with_past_expiry_is_inactive(
        self, db_session, validator_user
    ):
        pick = self._pick(
            validator_user,
            status=PickStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc) - timedelta(days=20),
            expires_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        db_session.add(pick)
        db_session.flush()
        assert pick.is_active() is False

    def test_published_pick_with_no_expiry_is_active(
        self, db_session, validator_user
    ):
        pick = self._pick(
            validator_user,
            status=PickStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
            expires_at=None,
        )
        db_session.add(pick)
        db_session.flush()
        assert pick.is_active() is True

    def test_superseded_pick_is_inactive(self, db_session, validator_user):
        original = self._pick(
            validator_user,
            status=PickStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        )
        db_session.add(original)
        db_session.flush()
        replacement = self._pick(
            validator_user,
            action=PickAction.TRIM,
            reason_summary="Trim 25% into strength.",
            status=PickStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        )
        db_session.add(replacement)
        db_session.flush()
        original.superseded_by_id = replacement.id
        db_session.flush()
        assert original.is_active() is False
        assert replacement.is_active() is True

    def test_decimal_fields_round_trip_without_float_loss(
        self, db_session, validator_user
    ):
        pick = self._pick(
            validator_user,
            suggested_entry=Decimal("125.123456"),
            suggested_stop=Decimal("119.987654"),
            suggested_size_pct=Decimal("0.0250"),
        )
        db_session.add(pick)
        db_session.flush()
        db_session.refresh(pick)
        assert isinstance(pick.suggested_entry, Decimal)
        assert pick.suggested_entry == Decimal("125.123456")
        assert pick.suggested_stop == Decimal("119.987654")
        assert pick.suggested_size_pct == Decimal("0.0250")


# ---------------------------------------------------------------------------
# Provenance contract
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_pick_can_link_back_to_email_parse(
        self, db_session, validator_user, email_parse
    ):
        pick = ValidatedPick(
            source_email_parse_id=email_parse.id,
            validator_user_id=validator_user.id,
            symbol="NVDA",
            action=PickAction.BUY,
            reason_summary="From validator email.",
        )
        db_session.add(pick)
        db_session.flush()
        db_session.refresh(pick)
        assert pick.source_parse is email_parse
        assert pick in email_parse.picks

    def test_candidate_promotion_links_both_directions(
        self, db_session, validator_user
    ):
        cand = Candidate(
            symbol="MSFT",
            generator_name="stage2a_rs_strong",
            generator_version="v1",
            score=Decimal("87.5000"),
            action_suggestion=PickAction.BUY,
            rationale_summary="Stage 2A + RS Mansfield 78 + insider buy.",
        )
        db_session.add(cand)
        db_session.flush()

        pick = ValidatedPick(
            promoted_from_candidate_id=cand.id,
            validator_user_id=validator_user.id,
            symbol="MSFT",
            action=PickAction.BUY,
            reason_summary="Promoted from system candidate.",
        )
        db_session.add(pick)
        db_session.flush()
        cand.promoted_to_pick_id = pick.id
        cand.status = CandidateQueueState.PUBLISHED
        db_session.flush()

        db_session.refresh(cand)
        assert cand.promoted_pick is pick
        assert cand.status == CandidateQueueState.PUBLISHED

    def test_source_attribution_links_to_pick_and_email(
        self, db_session, validator_user, email, email_parse
    ):
        pick = ValidatedPick(
            source_email_parse_id=email_parse.id,
            validator_user_id=validator_user.id,
            symbol="NVDA",
            action=PickAction.BUY,
            reason_summary="From validator email.",
        )
        db_session.add(pick)
        db_session.flush()

        attribution = SourceAttribution(
            artifact_kind="validated_pick",
            artifact_id=pick.id,
            source_type=SourceType.EMAIL,
            source_email_id=email.id,
            excerpt="Buy NVDA on the breakout. Stop 110.",
            confidence=Decimal("0.920"),
        )
        db_session.add(attribution)
        db_session.flush()
        db_session.refresh(attribution)
        assert attribution.source_email_id == email.id
        assert attribution.artifact_id == pick.id
        assert attribution.confidence == Decimal("0.920")


# ---------------------------------------------------------------------------
# Engagements (multi-tenant boundary)
# ---------------------------------------------------------------------------


class TestPickEngagement:
    def test_engagement_idempotency_on_user_pick_type(
        self, db_session, validator_user, subscriber_user
    ):
        pick = ValidatedPick(
            validator_user_id=validator_user.id,
            symbol="NVDA",
            action=PickAction.BUY,
            reason_summary="Test pick.",
        )
        db_session.add(pick)
        db_session.flush()

        first = PickEngagement(
            pick_id=pick.id,
            user_id=subscriber_user.id,
            engagement_type=EngagementType.VIEWED,
        )
        db_session.add(first)
        db_session.flush()

        duplicate = PickEngagement(
            pick_id=pick.id,
            user_id=subscriber_user.id,
            engagement_type=EngagementType.VIEWED,
        )
        with pytest.raises(IntegrityError):
            try:
                db_session.add(duplicate)
                db_session.flush()
            except IntegrityError:
                db_session.rollback()
                raise

    def test_different_engagement_types_coexist(
        self, db_session, validator_user, subscriber_user
    ):
        pick = ValidatedPick(
            validator_user_id=validator_user.id,
            symbol="NVDA",
            action=PickAction.BUY,
            reason_summary="Test pick.",
        )
        db_session.add(pick)
        db_session.flush()

        for et in (EngagementType.VIEWED, EngagementType.EXECUTED):
            db_session.add(
                PickEngagement(
                    pick_id=pick.id,
                    user_id=subscriber_user.id,
                    engagement_type=et,
                )
            )
        db_session.flush()

        db_session.refresh(pick)
        assert {e.engagement_type for e in pick.engagements} == {
            EngagementType.VIEWED,
            EngagementType.EXECUTED,
        }


# ---------------------------------------------------------------------------
# Sibling signals (MacroOutlook, PositionChange)
# ---------------------------------------------------------------------------


class TestSiblingSignals:
    def test_macro_outlook_round_trip(self, db_session, validator_user, email_parse):
        outlook = MacroOutlook(
            source_email_parse_id=email_parse.id,
            validator_user_id=validator_user.id,
            regime_call="R3",
            thesis="Choppy, lean defensive on rallies until breadth confirms.",
            time_horizon_days=14,
            confidence=Decimal("0.650"),
            status=PickStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
        )
        db_session.add(outlook)
        db_session.flush()
        db_session.refresh(outlook)
        assert outlook.regime_call == "R3"
        assert outlook.confidence == Decimal("0.650")
        assert outlook.status == PickStatus.PUBLISHED
        assert outlook.validator_pseudonym == "Twisted Slice"

    def test_position_change_round_trip(
        self, db_session, validator_user, email_parse
    ):
        change = PositionChange(
            source_email_parse_id=email_parse.id,
            validator_user_id=validator_user.id,
            symbol="AAPL",
            action=PickAction.TRIM,
            size_change_pct=Decimal("0.2500"),
            reason="Trim 25% into the earnings rip; keep core.",
            status=PickStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
        )
        db_session.add(change)
        db_session.flush()
        db_session.refresh(change)
        assert change.action == PickAction.TRIM
        assert change.size_change_pct == Decimal("0.2500")
        assert change.validator_pseudonym == "Twisted Slice"


# ---------------------------------------------------------------------------
# Enum coercion
# ---------------------------------------------------------------------------


class TestEnumCoercion:
    @pytest.mark.parametrize("action", list(PickAction))
    def test_pick_action_round_trips(self, db_session, validator_user, action):
        pick = ValidatedPick(
            validator_user_id=validator_user.id,
            symbol="X",
            action=action,
            reason_summary=f"action={action.value}",
        )
        db_session.add(pick)
        db_session.flush()
        db_session.refresh(pick)
        assert pick.action == action

    @pytest.mark.parametrize("status", list(PickStatus))
    def test_pick_status_round_trips(self, db_session, validator_user, status):
        pick = ValidatedPick(
            validator_user_id=validator_user.id,
            symbol="Y",
            action=PickAction.BUY,
            reason_summary="status round-trip",
            status=status,
        )
        db_session.add(pick)
        db_session.flush()
        db_session.refresh(pick)
        assert pick.status == status
