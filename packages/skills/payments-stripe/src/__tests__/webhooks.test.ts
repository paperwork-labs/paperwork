import Stripe from "stripe";
import { describe, expect, it } from "vitest";

import { handleEvent, verifyWebhook } from "../webhooks.js";

describe("verifyWebhook", () => {
  /** Placeholder for HMAC only (not a real Stripe signing secret; avoids `whsec_` secret scanners). */
  const secret = "test_hmac_webhook_secret_a1b2c3d4e5f6789012345678901234";

  const sign = (payload: string) =>
    Stripe.webhooks.generateTestHeaderString({ payload, secret });

  it("rejects bad signatures", () => {
    const payload = JSON.stringify(
      buildSubscriptionEventPayload("customer.subscription.created"),
    );
    const header = sign(payload);
    expect(() => verifyWebhook(`${secret}_mismatch`, payload, header)).toThrow(
      Stripe.errors.StripeSignatureVerificationError,
    );
  });

  it("parses customer.subscription.created", () => {
    const payload = JSON.stringify(
      buildSubscriptionEventPayload("customer.subscription.created"),
    );
    const ev = verifyWebhook(secret, payload, sign(payload));
    expect(ev.type).toBe("subscription.created");
    expect(ev.customerId).toBe("cus_test_1");
    expect(ev.subscriptionId).toBe("sub_test_1");
    expect(ev.amount).toEqual({ value: 10_00, currency: "USD" });
  });

  it("parses customer.subscription.updated", () => {
    const payload = JSON.stringify(
      buildSubscriptionEventPayload("customer.subscription.updated"),
    );
    const ev = verifyWebhook(secret, payload, sign(payload));
    expect(ev.type).toBe("subscription.updated");
  });

  it("parses customer.subscription.deleted", () => {
    const payload = JSON.stringify(
      buildSubscriptionEventPayload("customer.subscription.deleted"),
    );
    const ev = verifyWebhook(secret, payload, sign(payload));
    expect(ev.type).toBe("subscription.deleted");
  });

  it("parses invoice.paid", () => {
    const payload = JSON.stringify(buildInvoiceEventPayload("invoice.paid"));
    const ev = verifyWebhook(secret, payload, sign(payload));
    expect(ev.type).toBe("invoice.paid");
    expect(ev.amount).toEqual({ value: 2500, currency: "USD" });
  });

  it("parses invoice.payment_failed as invoice.failed", () => {
    const payload = JSON.stringify(
      buildInvoiceEventPayload("invoice.payment_failed"),
    );
    const ev = verifyWebhook(secret, payload, sign(payload));
    expect(ev.type).toBe("invoice.failed");
    expect(ev.amount?.value).toBe(2500);
  });
});

describe("handleEvent", () => {
  it("throws on unsupported event types", () => {
    const ev = {
      id: "evt_x",
      object: "event",
      api_version: "2024-06-20",
      created: Math.floor(Date.now() / 1000),
      type: "charge.succeeded",
      data: { object: {} },
    } as unknown as Stripe.Event;
    expect(() => handleEvent(ev)).toThrow(/Unsupported Stripe webhook type/);
  });
});

function buildSubscriptionEventPayload(type: string) {
  const subscription = {
    id: "sub_test_1",
    object: "subscription",
    customer: "cus_test_1",
    status: "active",
    start_date: 1_700_000_000,
    canceled_at: null,
    items: {
      object: "list",
      data: [
        {
          id: "si_test",
          object: "subscription_item",
          quantity: 1,
          price: {
            id: "price_test",
            object: "price",
            unit_amount: 10_00,
            currency: "usd",
            recurring: { interval: "month", interval_count: 1 },
          },
        },
      ],
    },
  };

  return {
    id: "evt_test_subscription",
    object: "event",
    api_version: "2024-06-20",
    created: Math.floor(Date.now() / 1000),
    livemode: false,
    pending_webhooks: 0,
    request: { id: null, idempotency_key: null },
    type,
    data: {
      object: subscription,
      previous_attributes: {},
    },
  };
}

function buildInvoiceEventPayload(
  type: "invoice.paid" | "invoice.payment_failed",
) {
  const invoice = {
    id: "in_test",
    object: "invoice",
    customer: "cus_test_1",
    subscription: "sub_test_1",
    amount_paid: 2500,
    amount_due: 2500,
    currency: "usd",
  };

  return {
    id: "evt_test_invoice",
    object: "event",
    api_version: "2024-06-20",
    created: Math.floor(Date.now() / 1000),
    livemode: false,
    pending_webhooks: 0,
    request: { id: null, idempotency_key: null },
    type,
    data: {
      object: invoice,
      previous_attributes: {},
    },
  };
}
