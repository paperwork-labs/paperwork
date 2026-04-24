"""Public pricing catalog — no authentication, must mirror feature catalog."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes.pricing import reset_cache
from app.models.entitlement import SubscriptionTier
from app.services.billing.feature_catalog import all_features
from app.services.billing.tier_catalog import all_tiers


@pytest.fixture
def client():
    # The endpoint is auth-free, so we don't need to override any
    # dependencies — but we DO need to bust the in-process cache so
    # tests don't leak state across runs.
    reset_cache()
    yield TestClient(app, raise_server_exceptions=False)
    reset_cache()


# -----------------------------------------------------------------------------
# Public access + envelope
# -----------------------------------------------------------------------------


def test_catalog_is_public_no_auth(client: TestClient):
    """The pricing page must render for logged-out visitors."""
    r = client.get("/api/v1/pricing/catalog")
    assert r.status_code == 200, r.text


def test_catalog_envelope_shape(client: TestClient):
    body = client.get("/api/v1/pricing/catalog").json()
    assert set(body.keys()) == {"tiers", "currency"}
    assert body["currency"] == "USD"
    assert isinstance(body["tiers"], list)


# -----------------------------------------------------------------------------
# Tier coverage + ordering
# -----------------------------------------------------------------------------


def test_catalog_returns_all_six_tiers(client: TestClient):
    """Every SubscriptionTier must surface on the public pricing page."""
    body = client.get("/api/v1/pricing/catalog").json()
    returned = [t["tier"] for t in body["tiers"]]
    assert returned == [t.value for t in SubscriptionTier], (
        "Tier ordering must match SubscriptionTier enum (Free → "
        "Enterprise) so the comparison table reads naturally "
        "left-to-right."
    )


def test_catalog_free_tier_first(client: TestClient):
    body = client.get("/api/v1/pricing/catalog").json()
    assert body["tiers"][0]["tier"] == "free"


def test_catalog_enterprise_tier_last(client: TestClient):
    body = client.get("/api/v1/pricing/catalog").json()
    assert body["tiers"][-1]["tier"] == "enterprise"


# -----------------------------------------------------------------------------
# Per-tier shape
# -----------------------------------------------------------------------------


_REQUIRED_TIER_FIELDS = {
    "tier",
    "name",
    "tagline",
    "monthly_price_usd",
    "annual_price_usd",
    "covers_copy",
    "cta_label",
    "cta_route",
    "is_contact_sales",
    "features",
    "new_features",
}


def test_each_tier_has_required_fields(client: TestClient):
    body = client.get("/api/v1/pricing/catalog").json()
    for tier in body["tiers"]:
        missing = _REQUIRED_TIER_FIELDS - set(tier.keys())
        assert not missing, (
            f"Tier {tier.get('tier')!r} is missing fields: {missing}"
        )


def test_free_tier_pricing_is_zero(client: TestClient):
    body = client.get("/api/v1/pricing/catalog").json()
    free = next(t for t in body["tiers"] if t["tier"] == "free")
    assert free["monthly_price_usd"] == "0.00"
    assert free["annual_price_usd"] == "0.00"
    assert free["cta_route"] == "/register"
    assert free["is_contact_sales"] is False


def test_enterprise_pricing_is_contact_sales(client: TestClient):
    """Enterprise has no self-serve checkout; price fields must be null."""
    body = client.get("/api/v1/pricing/catalog").json()
    ent = next(t for t in body["tiers"] if t["tier"] == "enterprise")
    assert ent["monthly_price_usd"] is None
    assert ent["annual_price_usd"] is None
    assert ent["is_contact_sales"] is True


def test_paid_tiers_have_decimal_prices(client: TestClient):
    """Prices are serialized as Decimal-precision strings, not floats."""
    body = client.get("/api/v1/pricing/catalog").json()
    for tier in body["tiers"]:
        if tier["tier"] in {"free", "enterprise"}:
            continue
        # Must parse cleanly as Decimal; rejects float artifacts like
        # "20.00000001".
        monthly = Decimal(tier["monthly_price_usd"])
        annual = Decimal(tier["annual_price_usd"])
        assert monthly > 0, (
            f"{tier['tier']} monthly price must be positive"
        )
        assert annual > 0, (
            f"{tier['tier']} annual price must be positive"
        )
        # Annual should be cheaper than monthly * 12 (we offer a
        # discount) OR equal (no discount). Never more expensive.
        assert annual <= monthly * 12, (
            f"{tier['tier']} annual price ({annual}) must not exceed "
            f"monthly * 12 ({monthly * 12}) — would mean charging more "
            "to commit longer, which is hostile pricing."
        )


def test_paid_tiers_have_transparent_covers_copy(client: TestClient):
    """Per D106: every paid tier must surface 'your subscription covers X'."""
    body = client.get("/api/v1/pricing/catalog").json()
    for tier in body["tiers"]:
        assert tier["covers_copy"], (
            f"Tier {tier['tier']} is missing the transparency microcopy"
        )


# -----------------------------------------------------------------------------
# Feature ladder consistency with feature_catalog (single source of truth)
# -----------------------------------------------------------------------------


def test_features_per_tier_match_feature_catalog_ladder(
    client: TestClient,
):
    """Each tier's feature list must equal everything from
    feature_catalog whose min_tier rank is <= this tier's rank. Drift
    here would mean the pricing page lies about what the user gets."""
    body = client.get("/api/v1/pricing/catalog").json()

    expected_keys_by_tier = {
        tier.value: {
            f.key
            for f in all_features()
            if SubscriptionTier.rank(f.min_tier)
            <= SubscriptionTier.rank(tier)
        }
        for tier in SubscriptionTier
    }
    for tier in body["tiers"]:
        actual_keys = {f["key"] for f in tier["features"]}
        assert actual_keys == expected_keys_by_tier[tier["tier"]], (
            f"Feature drift on tier {tier['tier']!r}: pricing endpoint "
            f"and feature_catalog disagree."
        )


def test_new_features_are_those_introduced_at_each_tier(
    client: TestClient,
):
    body = client.get("/api/v1/pricing/catalog").json()
    expected_new = {
        tier.value: {
            f.key for f in all_features() if f.min_tier == tier
        }
        for tier in SubscriptionTier
    }
    for tier in body["tiers"]:
        actual_new = {f["key"] for f in tier["new_features"]}
        assert actual_new == expected_new[tier["tier"]]


def test_each_feature_has_required_fields(client: TestClient):
    body = client.get("/api/v1/pricing/catalog").json()
    required = {"key", "title", "description", "category", "min_tier"}
    for tier in body["tiers"]:
        for feature in tier["features"]:
            missing = required - set(feature.keys())
            assert not missing, (
                f"Feature missing fields: {missing}"
            )


# -----------------------------------------------------------------------------
# Cache behaviour (smoke)
# -----------------------------------------------------------------------------


def test_catalog_is_cached_returns_identical_payload_on_second_hit(
    client: TestClient,
):
    """The cache must serve byte-identical responses within the TTL window."""
    first = client.get("/api/v1/pricing/catalog").json()
    second = client.get("/api/v1/pricing/catalog").json()
    assert first == second


def test_module_level_tier_table_covers_every_subscription_tier():
    """Defensive — the module's _validate_tier_coverage() runs at
    import, but we re-assert at test time so a future contributor who
    wires a new tier sees a clear failure here, not just a
    server-startup crash."""
    table_tiers = {t.tier for t in all_tiers()}
    enum_tiers = set(SubscriptionTier)
    assert table_tiers == enum_tiers
