"""Unit tests for the Stripe billing scaffold.

These tests do NOT require the real `stripe` SDK to be importable; they pass
a stub module + sink directly into `StripeWebhookProcessor`. The `stripe`
package is added to ``requirements.txt`` in this PR but the test layer must
work without network access.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

import pytest

from app.services.billing.price_catalog import (
    BillingInterval,
    PriceCatalog,
    PriceEntry,
    TierSlug,
    resolve_tier_for_price,
)
from app.services.billing.stripe_client import (
    StripeClientFactory,
    StripeNotConfigured,
)
from app.services.billing.stripe_webhook import (
    ProcessResult,
    StripeSignatureError,
    StripeWebhookError,
    StripeWebhookProcessor,
    SubscriptionState,
    SubscriptionStatus,
    _DictIdempotencyStore,
    _max_tier,
    _unix_to_dt,
)

# Tests in this module do not touch the database.
pytestmark = pytest.mark.no_db


# --------------------------------------------------------------------------- #
# Test doubles                                                                #
# --------------------------------------------------------------------------- #


class _StubResolver:
    def __init__(self, mapping: Dict[str, int], by_email: Optional[Dict[str, int]] = None):
        self._by_customer = mapping
        self._by_email = by_email or {}

    def resolve(self, *, stripe_customer_id, email, metadata):
        if metadata.get("user_id") is not None:
            try:
                return int(metadata["user_id"])
            except (TypeError, ValueError):
                return None
        if stripe_customer_id and stripe_customer_id in self._by_customer:
            return self._by_customer[stripe_customer_id]
        if email and email.lower() in self._by_email:
            return self._by_email[email.lower()]
        return None


class _RecordingSink:
    def __init__(self) -> None:
        self.applied: List[SubscriptionState] = []
        self.fail = False

    def apply(self, state: SubscriptionState) -> None:
        if self.fail:
            raise RuntimeError("simulated downstream failure")
        self.applied.append(state)


@dataclass
class _StubWebhookNamespace:
    """Stub for `stripe.Webhook` used by verify_and_parse."""

    accept: bool = True

    def construct_event(self, payload: bytes, sig_header: str, secret: str):
        if not self.accept:
            raise ValueError("bad sig (stub)")
        return json.loads(payload.decode("utf-8"))


@dataclass
class _StubStripeModule:
    """Minimal stub of the `stripe` SDK module."""

    Webhook: _StubWebhookNamespace = field(default_factory=_StubWebhookNamespace)
    api_key: Optional[str] = None
    api_version: Optional[str] = None
    Customer: Any = None
    Subscription: Any = None
    Checkout: Any = None
    Event: Any = None


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def catalog() -> PriceCatalog:
    return PriceCatalog.from_env(
        {
            "STRIPE_PRICE_PRO_MONTHLY": "price_pro_m",
            "STRIPE_PRICE_PRO_ANNUAL": "price_pro_y",
            "STRIPE_PRICE_PRO_PLUS_MONTHLY": "price_proplus_m",
            "STRIPE_PRICE_PRO_PLUS_ANNUAL": "",
            "STRIPE_PRICE_QUANT_DESK_MONTHLY": "price_qd_m",
            "STRIPE_PRICE_QUANT_DESK_ANNUAL": "",
            "STRIPE_PRICE_ENTERPRISE_MONTHLY": "",
            "STRIPE_PRICE_ENTERPRISE_ANNUAL": "",
        }
    )


@pytest.fixture
def stub_stripe() -> _StubStripeModule:
    return _StubStripeModule()


@pytest.fixture
def processor(catalog, stub_stripe) -> tuple[StripeWebhookProcessor, _RecordingSink, _StubResolver]:
    sink = _RecordingSink()
    resolver = _StubResolver(
        mapping={"cus_alice": 1, "cus_bob": 2}, by_email={"alice@example.com": 1}
    )
    proc = StripeWebhookProcessor(
        webhook_secret="whsec_stub",
        catalog=catalog,
        user_resolver=resolver,
        sink=sink,
        stripe_module=stub_stripe,
    )
    return proc, sink, resolver


# --------------------------------------------------------------------------- #
# PriceCatalog                                                                #
# --------------------------------------------------------------------------- #


class TestPriceCatalog:
    def test_from_env_skips_blank_values(self, catalog):
        assert len(catalog) == 4  # only the non-empty entries
        assert "price_pro_m" in catalog
        assert "" not in catalog

    def test_resolve_returns_correct_tier_and_interval(self, catalog):
        entry = catalog.resolve("price_pro_y")
        assert entry is not None
        assert entry.tier == TierSlug.PRO
        assert entry.interval == BillingInterval.ANNUAL

    def test_unknown_price_returns_none(self, catalog):
        assert catalog.resolve("price_does_not_exist") is None

    def test_from_env_keeps_first_when_same_price_used_twice(self):
        # Two env vars share the same price ID -> keep the first; the second
        # is silently dropped (with a logger.warning we don't assert on here
        # because the project disables some loggers in test mode).
        env = {
            "STRIPE_PRICE_PRO_MONTHLY": "price_shared",
            "STRIPE_PRICE_PRO_PLUS_MONTHLY": "price_shared",
        }
        for spec in (
            "STRIPE_PRICE_PRO_ANNUAL",
            "STRIPE_PRICE_PRO_PLUS_ANNUAL",
            "STRIPE_PRICE_QUANT_DESK_MONTHLY",
            "STRIPE_PRICE_QUANT_DESK_ANNUAL",
            "STRIPE_PRICE_ENTERPRISE_MONTHLY",
            "STRIPE_PRICE_ENTERPRISE_ANNUAL",
        ):
            env[spec] = ""
        cat = PriceCatalog.from_env(env)
        assert len(cat) == 1
        # The first one wins (PRO, not PRO_PLUS) since _CATALOG_SPEC is ordered.
        entry = cat.resolve("price_shared")
        assert entry is not None
        assert entry.tier == TierSlug.PRO

    def test_key_entry_mismatch_raises(self):
        with pytest.raises(ValueError, match="key/entry mismatch"):
            PriceCatalog({"price_x": PriceEntry("price_y", TierSlug.PRO, BillingInterval.MONTHLY)})

    def test_resolve_tier_for_price_helper(self, catalog):
        assert resolve_tier_for_price("price_proplus_m", catalog) == TierSlug.PRO_PLUS
        assert resolve_tier_for_price("nope", catalog) is None


# --------------------------------------------------------------------------- #
# StripeClientFactory                                                         #
# --------------------------------------------------------------------------- #


class TestStripeClientFactory:
    def test_get_without_api_key_raises(self):
        f = StripeClientFactory(loader=lambda: _StubStripeModule())
        with pytest.raises(StripeNotConfigured):
            f.get(api_key=None)

    def test_get_sets_api_key_and_version(self):
        stub = _StubStripeModule()
        f = StripeClientFactory(loader=lambda: stub)
        out = f.get(api_key="sk_test_x", api_version="2024-06-20")
        assert out is stub
        assert stub.api_key == "sk_test_x"
        assert stub.api_version == "2024-06-20"

    def test_api_key_rotation_picked_up(self):
        stub = _StubStripeModule()
        f = StripeClientFactory(loader=lambda: stub)
        f.get(api_key="sk_test_a")
        f.get(api_key="sk_test_b")  # rotated
        assert stub.api_key == "sk_test_b"

    def test_default_loader_raises_when_stripe_missing(self, monkeypatch):
        # Force ImportError by removing 'stripe' from sys.modules and breaking
        # the import path. Easier: directly call the loader's fallback.
        f = StripeClientFactory()
        # Monkey-patch the loader to simulate ImportError.
        f._loader = lambda: (_ for _ in ()).throw(ImportError("no stripe"))
        with pytest.raises(StripeNotConfigured):
            f.get(api_key=None)


# --------------------------------------------------------------------------- #
# Verification                                                                #
# --------------------------------------------------------------------------- #


class TestVerifyAndParse:
    def test_missing_secret_raises_not_configured(self, catalog, stub_stripe):
        proc = StripeWebhookProcessor(
            webhook_secret=None,
            catalog=catalog,
            user_resolver=_StubResolver({}),
            sink=_RecordingSink(),
            stripe_module=stub_stripe,
        )
        with pytest.raises(StripeNotConfigured):
            proc.verify_and_parse(b"{}", "t=1,v1=abc")

    def test_missing_signature_header_raises(self, processor):
        proc, _, _ = processor
        with pytest.raises(StripeSignatureError, match="Missing"):
            proc.verify_and_parse(b"{}", None)

    def test_bad_signature_raises_signature_error(self, processor, stub_stripe):
        proc, _, _ = processor
        stub_stripe.Webhook.accept = False
        with pytest.raises(StripeSignatureError):
            proc.verify_and_parse(b'{"id":"evt_1","type":"x"}', "t=1,v1=bad")

    def test_valid_signature_returns_event_dict(self, processor):
        proc, _, _ = processor
        out = proc.verify_and_parse(
            b'{"id":"evt_ok","type":"customer.subscription.updated","data":{"object":{}}}',
            "t=1,v1=ok",
        )
        assert out["id"] == "evt_ok"
        assert out["type"] == "customer.subscription.updated"


# --------------------------------------------------------------------------- #
# Idempotency                                                                 #
# --------------------------------------------------------------------------- #


class TestIdempotency:
    def test_dict_store_marks_and_contains(self):
        store = _DictIdempotencyStore()
        assert "evt_1" not in store
        store.mark("evt_1")
        assert "evt_1" in store
        assert 12345 not in store  # type-coerce safe

    def test_handle_skips_duplicate_event(self, processor):
        proc, sink, _ = processor
        event = _make_subscription_event(
            "evt_dup", "customer.subscription.updated", customer="cus_alice"
        )
        first = proc.handle(event)
        second = proc.handle(event)
        assert first.acted is True
        assert second.acted is False
        assert second.reason == "duplicate"
        assert len(sink.applied) == 1


# --------------------------------------------------------------------------- #
# Event dispatch                                                              #
# --------------------------------------------------------------------------- #


def _make_checkout_event(
    event_id: str,
    customer: str = "cus_alice",
    price_id: str = "price_pro_m",
    payment_status: str = "paid",
    mode: str = "subscription",
    user_id_meta: Optional[int] = None,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "mode": mode,
                "payment_status": payment_status,
                "customer": customer,
                "customer_email": email,
                "subscription": "sub_test_1",
                "metadata": {"user_id": user_id_meta} if user_id_meta is not None else {},
                "line_items": {"data": [{"price": {"id": price_id}}]},
            }
        },
    }


def _make_subscription_event(
    event_id: str,
    event_type: str,
    customer: str = "cus_alice",
    price_id: str = "price_pro_m",
    status: str = "active",
    cancel_at_period_end: bool = False,
) -> Dict[str, Any]:
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": "sub_test_1",
                "customer": customer,
                "status": status,
                "cancel_at_period_end": cancel_at_period_end,
                "current_period_end": 1_800_000_000,
                "items": {"data": [{"price": {"id": price_id}}]},
                "metadata": {},
            }
        },
    }


def _make_invoice_event(
    event_id: str,
    event_type: str,
    customer: str = "cus_alice",
    price_id: str = "price_pro_m",
    subscription: Optional[str] = "sub_test_1",
) -> Dict[str, Any]:
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": "in_test_1",
                "customer": customer,
                "subscription": subscription,
                "billing_reason": "subscription_cycle",
                "period_end": 1_800_000_000,
                "lines": {"data": [{"price": {"id": price_id}}]},
                "metadata": {},
            }
        },
    }


class TestCheckoutSessionCompleted:
    def test_paid_subscription_applies_active_state(self, processor):
        proc, sink, _ = processor
        event = _make_checkout_event("evt_co_1", price_id="price_proplus_m")
        result = proc.handle(event)
        assert result.acted
        state = sink.applied[0]
        assert state.user_id == 1
        assert state.tier == TierSlug.PRO_PLUS
        assert state.status == SubscriptionStatus.ACTIVE
        assert state.stripe_customer_id == "cus_alice"
        assert state.stripe_subscription_id == "sub_test_1"
        assert state.cancel_at_period_end is False

    def test_non_subscription_mode_is_skipped(self, processor):
        proc, sink, _ = processor
        event = _make_checkout_event("evt_co_2", mode="payment")
        result = proc.handle(event)
        assert result.acked and not result.acted
        assert result.reason.startswith("checkout-mode")
        assert sink.applied == []

    def test_unpaid_checkout_is_skipped(self, processor):
        proc, sink, _ = processor
        event = _make_checkout_event("evt_co_3", payment_status="unpaid")
        result = proc.handle(event)
        assert not result.acted
        assert result.reason.startswith("checkout-payment-status")
        assert sink.applied == []

    def test_unknown_price_is_skipped(self, processor):
        proc, sink, _ = processor
        event = _make_checkout_event("evt_co_4", price_id="price_something_legacy")
        result = proc.handle(event)
        assert not result.acted
        assert result.reason == "checkout-no-known-price"

    def test_metadata_user_id_takes_precedence(self, processor):
        proc, sink, _ = processor
        event = _make_checkout_event(
            "evt_co_5", customer="cus_unknown", user_id_meta=1, price_id="price_pro_m"
        )
        result = proc.handle(event)
        assert result.acted
        assert sink.applied[0].user_id == 1

    def test_unresolvable_user_raises(self, processor):
        proc, _, _ = processor
        event = _make_checkout_event(
            "evt_co_6", customer="cus_ghost", email="ghost@nowhere.example"
        )
        with pytest.raises(StripeWebhookError, match="cannot resolve user"):
            proc.handle(event)


class TestSubscriptionEvents:
    def test_created_active_applies(self, processor):
        proc, sink, _ = processor
        event = _make_subscription_event("evt_s1", "customer.subscription.created")
        result = proc.handle(event)
        assert result.acted
        s = sink.applied[0]
        assert s.tier == TierSlug.PRO
        assert s.status == SubscriptionStatus.ACTIVE
        assert s.current_period_end is not None
        assert s.current_period_end.tzinfo is timezone.utc

    def test_updated_past_due_status_propagates(self, processor):
        proc, sink, _ = processor
        event = _make_subscription_event(
            "evt_s2", "customer.subscription.updated", status="past_due"
        )
        result = proc.handle(event)
        assert result.acted
        assert sink.applied[0].status == SubscriptionStatus.PAST_DUE

    def test_unknown_status_maps_to_past_due(self, processor):
        proc, sink, _ = processor
        event = _make_subscription_event(
            "evt_s3", "customer.subscription.updated", status="paused"
        )
        result = proc.handle(event)
        assert result.acted
        assert sink.applied[0].status == SubscriptionStatus.PAST_DUE

    def test_deleted_always_downgrades_to_free_canceled(self, processor):
        proc, sink, _ = processor
        event = _make_subscription_event(
            "evt_s4", "customer.subscription.deleted", price_id="price_pro_m"
        )
        result = proc.handle(event)
        assert result.acted
        s = sink.applied[0]
        assert s.tier == TierSlug.FREE
        assert s.status == SubscriptionStatus.CANCELED

    def test_deleted_with_unknown_price_still_downgrades(self, processor):
        # A canceled subscription must always free the user, even if the
        # current price is no longer in the catalog.
        proc, sink, _ = processor
        event = _make_subscription_event(
            "evt_s4b", "customer.subscription.deleted", price_id="price_legacy"
        )
        result = proc.handle(event)
        assert result.acted
        assert sink.applied[0].tier == TierSlug.FREE

    def test_multi_item_subscription_picks_highest_tier(self, processor):
        # Build a subscription with two items at different tiers.
        proc, sink, _ = processor
        event = _make_subscription_event("evt_s5", "customer.subscription.updated")
        event["data"]["object"]["items"]["data"] = [
            {"price": {"id": "price_pro_m"}},
            {"price": {"id": "price_proplus_m"}},
        ]
        result = proc.handle(event)
        assert result.acted
        assert sink.applied[0].tier == TierSlug.PRO_PLUS

    def test_cancel_at_period_end_flag_propagates(self, processor):
        proc, sink, _ = processor
        event = _make_subscription_event(
            "evt_s6", "customer.subscription.updated", cancel_at_period_end=True
        )
        proc.handle(event)
        assert sink.applied[0].cancel_at_period_end is True


class TestInvoiceEvents:
    def test_payment_failed_marks_past_due(self, processor):
        proc, sink, _ = processor
        event = _make_invoice_event("evt_i1", "invoice.payment_failed")
        proc.handle(event)
        assert sink.applied[0].status == SubscriptionStatus.PAST_DUE
        assert sink.applied[0].tier == TierSlug.PRO

    def test_payment_succeeded_marks_active(self, processor):
        proc, sink, _ = processor
        event = _make_invoice_event("evt_i2", "invoice.payment_succeeded")
        proc.handle(event)
        assert sink.applied[0].status == SubscriptionStatus.ACTIVE

    def test_invoice_without_subscription_skipped(self, processor):
        proc, sink, _ = processor
        event = _make_invoice_event("evt_i3", "invoice.payment_succeeded", subscription=None)
        result = proc.handle(event)
        assert not result.acted
        assert result.reason == "invoice-no-subscription"
        assert sink.applied == []


class TestUnhandledTypes:
    def test_unhandled_event_acked_not_acted(self, processor):
        proc, sink, _ = processor
        event = {"id": "evt_x", "type": "customer.created", "data": {"object": {}}}
        result = proc.handle(event)
        assert result.acked is True
        assert result.acted is False
        assert result.reason.startswith("unhandled:")
        assert sink.applied == []

    def test_event_missing_id_or_type_raises(self, processor):
        proc, _, _ = processor
        with pytest.raises(StripeWebhookError):
            proc.handle({"type": "customer.subscription.updated"})


# --------------------------------------------------------------------------- #
# Sink failure semantics                                                      #
# --------------------------------------------------------------------------- #


class TestSinkFailure:
    def test_sink_exception_propagates_and_does_not_mark_idempotent(self, processor):
        proc, sink, _ = processor
        sink.fail = True
        event = _make_subscription_event("evt_sink_fail", "customer.subscription.updated")
        with pytest.raises(StripeWebhookError, match="sink failed"):
            proc.handle(event)

        # Repair sink and replay the same event — must NOT be marked as duplicate.
        sink.fail = False
        result = proc.handle(event)
        assert result.acted
        assert len(sink.applied) == 1


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


class TestHelpers:
    def test_max_tier_picks_higher_rank(self):
        assert _max_tier(None, TierSlug.PRO) == TierSlug.PRO
        assert _max_tier(TierSlug.FREE, TierSlug.PRO) == TierSlug.PRO
        assert _max_tier(TierSlug.PRO_PLUS, TierSlug.PRO) == TierSlug.PRO_PLUS
        assert _max_tier(TierSlug.ENTERPRISE, TierSlug.QUANT_DESK) == TierSlug.ENTERPRISE

    def test_unix_to_dt_returns_aware_utc(self):
        out = _unix_to_dt(1_700_000_000)
        assert out is not None
        assert out.tzinfo is timezone.utc
        assert out.year == 2023

    def test_unix_to_dt_handles_garbage(self):
        assert _unix_to_dt(None) is None
        assert _unix_to_dt("not a number") is None


# --------------------------------------------------------------------------- #
# Process result shape                                                        #
# --------------------------------------------------------------------------- #


def test_process_result_carries_applied_state(processor):
    proc, sink, _ = processor
    event = _make_subscription_event("evt_pr_1", "customer.subscription.updated")
    result = proc.handle(event)
    assert isinstance(result, ProcessResult)
    assert result.state is not None
    assert result.state.source_event_id == "evt_pr_1"
    assert result.state.source_event_type == "customer.subscription.updated"
