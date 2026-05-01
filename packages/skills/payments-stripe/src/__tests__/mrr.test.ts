import { describe, expect, it } from "vitest";

import { monthlyMinorFromStripeItems, snapshotMrrFromSubscriptions } from "../mrr.js";

describe("monthlyMinorFromStripeItems", () => {
  it("converts annual prices to monthly (cents)", () => {
    const sub = {
      items: {
        data: [
          {
            quantity: 1,
            price: {
              unit_amount: 120_00,
              currency: "usd",
              recurring: { interval: "year" as const, interval_count: 1 },
            },
          },
        ],
      },
    };
    expect(monthlyMinorFromStripeItems(sub)).toEqual({
      value: 10_00,
      currency: "USD",
    });
  });
});

describe("snapshotMrrFromSubscriptions", () => {
  const base = {
    customerId: "cus_x",
    subscriptionId: "sub_x",
    startedAt: new Date("2025-01-01T00:00:00.000Z"),
    amount: { value: 1000, currency: "USD" },
  } as const;

  it("sums MRR from active subscriptions only", () => {
    const asOf = new Date("2026-05-01T00:00:00.000Z");
    const snap = snapshotMrrFromSubscriptions(
      [
        {
          ...base,
          subscriptionId: "sub_1",
          customerId: "cus_1",
          status: "active",
        },
        {
          ...base,
          subscriptionId: "sub_2",
          customerId: "cus_2",
          status: "active",
          amount: { value: 500, currency: "USD" },
        },
      ],
      asOf,
    );
    expect(snap.asOf).toBe(asOf);
    expect(snap.totalMrr).toEqual({ value: 1500, currency: "USD" });
    expect(snap.customerCount).toBe(2);
    expect(snap.newMrr).toEqual({ value: 0, currency: "USD" });
  });

  it("excludes trialing and cancelled; includes past_due", () => {
    const asOf = new Date("2026-05-01T00:00:00.000Z");
    const snap = snapshotMrrFromSubscriptions(
      [
        {
          ...base,
          subscriptionId: "sub_t",
          status: "trialing",
          amount: { value: 9999, currency: "USD" },
        },
        {
          ...base,
          subscriptionId: "sub_c",
          status: "cancelled",
          amount: { value: 8888, currency: "USD" },
        },
        {
          ...base,
          subscriptionId: "sub_p",
          status: "past_due",
          amount: { value: 2000, currency: "USD" },
        },
      ],
      asOf,
    );
    expect(snap.totalMrr).toEqual({ value: 2000, currency: "USD" });
    expect(snap.customerCount).toBe(1);
  });

  it("rejects mixed currency in contributing subscriptions", () => {
    expect(() =>
      snapshotMrrFromSubscriptions([
        {
          ...base,
          subscriptionId: "sub_a",
          status: "active",
          amount: { value: 100, currency: "USD" },
        },
        {
          ...base,
          subscriptionId: "sub_b",
          status: "active",
          amount: { value: 100, currency: "EUR" },
        },
      ]),
    ).toThrow(/Mixed-currency/);
  });
});
