"""
Entitlement system tests
========================

Covers:

* SubscriptionTier ordering (rank, comparisons, is_allowed)
* FeatureCatalog completeness + lookups
* EntitlementService.get_or_create lazy creation
* EntitlementService.check decision matrix
* EntitlementService.manual_set_tier audit trail
* EntitlementService.apply_subscription_state respects MANUAL refusal
* Entitlement.is_active grace period for past_due
* Public catalog response includes every defined feature

These are pure-Python tests where possible (no DB required) to keep them
fast and to make them runnable in environments where TEST_DATABASE_URL is
not set. The service-level tests use db_session and exercise the real
Entitlement model + auto-create flow.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.entitlement import (
    Entitlement,
    EntitlementStatus,
    SubscriptionTier,
)
from app.services.billing.feature_catalog import (
    all_features,
    get_feature,
    is_allowed,
)


# =============================================================================
# Tier ordering & ranking — pure logic, no DB needed
# =============================================================================


class TestSubscriptionTierRank:
    def test_rank_is_strictly_monotonic(self):
        ranks = [SubscriptionTier.rank(t) for t in SubscriptionTier]
        assert ranks == sorted(ranks), "Tier ranks must be monotonically increasing"
        assert len(set(ranks)) == len(ranks), "Tier ranks must be unique"

    def test_free_is_lowest(self):
        assert SubscriptionTier.rank(SubscriptionTier.FREE) == 0

    def test_enterprise_is_highest(self):
        ranks = {t: SubscriptionTier.rank(t) for t in SubscriptionTier}
        assert ranks[SubscriptionTier.ENTERPRISE] == max(ranks.values())

    def test_unknown_string_is_free(self):
        assert SubscriptionTier.rank("not_a_real_tier") == 0
        assert SubscriptionTier.rank(None) == 0

    def test_string_input_is_case_insensitive(self):
        assert SubscriptionTier.rank("PRO") == SubscriptionTier.rank(
            SubscriptionTier.PRO
        )
        assert SubscriptionTier.rank("Pro_Plus") == SubscriptionTier.rank(
            SubscriptionTier.PRO_PLUS
        )

    def test_rich_comparisons(self):
        assert SubscriptionTier.PRO_PLUS > SubscriptionTier.PRO
        assert SubscriptionTier.PRO < SubscriptionTier.QUANT_DESK
        assert SubscriptionTier.ENTERPRISE >= SubscriptionTier.QUANT_DESK
        assert SubscriptionTier.FREE <= SubscriptionTier.PRO


# =============================================================================
# Feature catalog — pure lookup
# =============================================================================


class TestFeatureCatalog:
    def test_get_known_feature(self):
        f = get_feature("brain.native_chat")
        assert f.key == "brain.native_chat"
        # Ladder 3: native chat opens at PRO (with daily cap); PRO_PLUS
        # removes the cap. See tier_catalog._TIERS and feature_catalog.
        assert f.min_tier == SubscriptionTier.PRO

    def test_unknown_feature_raises_keyerror(self):
        with pytest.raises(KeyError, match="Unknown feature key"):
            get_feature("not.a.real.feature")

    def test_all_features_is_non_empty(self):
        features = all_features()
        assert len(features) > 0

    def test_all_features_keys_are_unique(self):
        keys = [f.key for f in all_features()]
        assert len(keys) == len(set(keys))

    def test_categories_are_finite(self):
        # We hard-code the allowed categories so a typo gets caught here.
        allowed = {"data", "picks", "brain", "execution", "research", "ops", "mcp", "strategy"}
        for f in all_features():
            assert f.category in allowed, f"Feature {f.key} has unknown category"

    def test_native_chat_is_pro(self):
        f = get_feature("brain.native_chat")
        assert f.min_tier == SubscriptionTier.PRO

    def test_is_allowed_satisfies_higher_tier(self):
        assert is_allowed(SubscriptionTier.PRO_PLUS, "data.cached_indicators")
        assert is_allowed(
            SubscriptionTier.ENTERPRISE, "execution.tax_aware_exit"
        )

    def test_is_allowed_blocks_lower_tier(self):
        assert not is_allowed(SubscriptionTier.FREE, "brain.native_chat")
        assert is_allowed(SubscriptionTier.PRO, "brain.native_chat")

    def test_picks_feed_full_requires_pro(self):
        f = get_feature("picks.feed_full")
        assert f.min_tier == SubscriptionTier.PRO
        assert not is_allowed(SubscriptionTier.FREE, "picks.feed_full")
        assert is_allowed(SubscriptionTier.PRO, "picks.feed_full")


# =============================================================================
# Entitlement model helpers — past_due grace period
# =============================================================================


class TestEntitlementGracePeriod:
    def _make(self, status: EntitlementStatus, period_end: datetime) -> Entitlement:
        # Construct an unsaved instance — we only exercise the helper methods,
        # so no DB is required.
        ent = Entitlement(
            user_id=1,
            tier=SubscriptionTier.PRO_PLUS,
            status=status,
            current_period_end=period_end,
        )
        return ent

    def test_active_status_is_active(self):
        now = datetime.now(timezone.utc)
        ent = self._make(EntitlementStatus.ACTIVE, now + timedelta(days=10))
        assert ent.is_active(now) is True

    def test_canceled_is_not_active(self):
        now = datetime.now(timezone.utc)
        ent = self._make(EntitlementStatus.CANCELED, now - timedelta(days=1))
        assert ent.is_active(now) is False

    def test_past_due_within_grace_is_active(self):
        now = datetime.now(timezone.utc)
        # 24h past period end, within the 72h grace window
        ent = self._make(EntitlementStatus.PAST_DUE, now - timedelta(hours=24))
        assert ent.is_active(now) is True

    def test_past_due_after_grace_is_not_active(self):
        now = datetime.now(timezone.utc)
        # 96h past period end, outside the 72h grace window
        ent = self._make(EntitlementStatus.PAST_DUE, now - timedelta(hours=96))
        assert ent.is_active(now) is False

    def test_effective_tier_falls_back_to_free_when_inactive(self):
        now = datetime.now(timezone.utc)
        ent = self._make(EntitlementStatus.CANCELED, now - timedelta(days=10))
        assert ent.effective_tier(now) == SubscriptionTier.FREE

    def test_effective_tier_returns_persisted_when_active(self):
        now = datetime.now(timezone.utc)
        ent = self._make(EntitlementStatus.ACTIVE, now + timedelta(days=10))
        assert ent.effective_tier(now) == SubscriptionTier.PRO_PLUS


# =============================================================================
# EntitlementService — exercises real DB interactions
# =============================================================================


def _create_user(session, username: str = "ent_test_user"):
    """Local helper. We make a fresh user per test rather than reuse a shared
    fixture so the unique-on-user_id constraint never trips on rollback edge
    cases."""
    from app.models.user import User

    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="x",
        is_active=True,
        is_approved=True,
    )
    session.add(user)
    session.flush()
    return user


class TestEntitlementService:
    def test_get_or_create_makes_free_row_on_first_read(self, db_session):
        from app.services.billing.entitlement_service import (
            EntitlementService,
        )

        user = _create_user(db_session, "ent_first_read")
        ent = EntitlementService.get_or_create(db_session, user)
        assert ent.user_id == user.id
        assert ent.tier == SubscriptionTier.FREE
        assert ent.status == EntitlementStatus.ACTIVE
        assert ent.metadata_json["source"] == "auto_create_on_first_read"

    def test_get_or_create_is_idempotent(self, db_session):
        from app.services.billing.entitlement_service import (
            EntitlementService,
        )

        user = _create_user(db_session, "ent_idempotent")
        a = EntitlementService.get_or_create(db_session, user)
        b = EntitlementService.get_or_create(db_session, user)
        assert a.id == b.id

    def test_check_blocks_native_chat_for_free_user(self, db_session):
        from app.services.billing.entitlement_service import (
            EntitlementService,
        )

        user = _create_user(db_session, "ent_free_chat")
        decision = EntitlementService.check(db_session, user, "brain.native_chat")
        assert decision.allowed is False
        # Ladder 3: PRO is the floor for native chat; PRO_PLUS removes the cap.
        assert decision.required_tier == SubscriptionTier.PRO
        assert decision.current_tier == SubscriptionTier.FREE
        assert "Requires" in decision.reason

    def test_check_allows_after_manual_upgrade(self, db_session):
        from app.services.billing.entitlement_service import (
            EntitlementService,
        )

        user = _create_user(db_session, "ent_manual")
        EntitlementService.manual_set_tier(
            db_session,
            user=user,
            new_tier=SubscriptionTier.PRO_PLUS,
            actor="test_operator",
            note="comp account for fixture",
        )
        decision = EntitlementService.check(db_session, user, "brain.native_chat")
        assert decision.allowed is True

    def test_manual_set_tier_records_audit_event(self, db_session):
        from app.services.billing.entitlement_service import (
            EntitlementService,
        )

        user = _create_user(db_session, "ent_audit")
        EntitlementService.manual_set_tier(
            db_session,
            user=user,
            new_tier=SubscriptionTier.QUANT_DESK,
            actor="ops@axiomfolio.com",
        )
        ent = EntitlementService.get_or_create(db_session, user)
        audit = ent.metadata_json.get("audit") or []
        assert any(e["event"] == "manual_set_tier" for e in audit)
        last = audit[-1]
        assert last["actor"] == "ops@axiomfolio.com"
        assert last["to_tier"] == "quant_desk"

    def test_apply_subscription_refuses_to_overwrite_manual(self, db_session):
        from app.services.billing.entitlement_service import (
            EntitlementService,
        )

        user = _create_user(db_session, "ent_manual_protect")
        EntitlementService.manual_set_tier(
            db_session,
            user=user,
            new_tier=SubscriptionTier.PRO_PLUS,
            actor="ops",
        )
        ent = EntitlementService.apply_subscription_state(
            db_session,
            user=user,
            tier=SubscriptionTier.FREE,  # would be a downgrade
            status=EntitlementStatus.ACTIVE,
            stripe_customer_id="cus_test",
            stripe_subscription_id="sub_test",
            stripe_price_id="price_test",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
            trial_ends_at=None,
            cancel_at_period_end=False,
            stripe_event_id="evt_123",
        )
        # Tier and status MUST be untouched.
        assert ent.tier == SubscriptionTier.PRO_PLUS
        assert ent.status == EntitlementStatus.MANUAL
        # The blocked attempt must be audited.
        audit = ent.metadata_json["audit"]
        assert any(e["event"] == "stripe_overwrite_blocked" for e in audit)

    def test_apply_subscription_updates_normal_entitlement(self, db_session):
        from app.services.billing.entitlement_service import (
            EntitlementService,
        )

        user = _create_user(db_session, "ent_stripe_normal")
        period_end = datetime.now(timezone.utc) + timedelta(days=30)
        ent = EntitlementService.apply_subscription_state(
            db_session,
            user=user,
            tier=SubscriptionTier.PRO,
            status=EntitlementStatus.ACTIVE,
            stripe_customer_id="cus_real",
            stripe_subscription_id="sub_real",
            stripe_price_id="price_pro_monthly",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=period_end,
            trial_ends_at=None,
            cancel_at_period_end=False,
            stripe_event_id="evt_real",
        )
        assert ent.tier == SubscriptionTier.PRO
        assert ent.stripe_customer_id == "cus_real"
        assert ent.current_period_end == period_end

    def test_audit_log_is_capped_at_50_events(self, db_session):
        # Smoke test: prevent the JSON column from growing unbounded as a
        # user churns through tier changes.
        from app.services.billing.entitlement_service import (
            EntitlementService,
        )

        user = _create_user(db_session, "ent_audit_cap")
        for i in range(60):
            EntitlementService.manual_set_tier(
                db_session,
                user=user,
                new_tier=(
                    SubscriptionTier.PRO if i % 2 == 0 else SubscriptionTier.FREE
                ),
                actor="test",
                note=f"cycle {i}",
            )
        ent = EntitlementService.get_or_create(db_session, user)
        assert len(ent.metadata_json["audit"]) == 50, (
            "Audit list must be capped at 50 entries to protect column size"
        )
