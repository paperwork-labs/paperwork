import { describe, expect, it } from "vitest";

import { InvalidLedgerEntryError, Ledger } from "../ledger";

describe("Ledger", () => {
  it("append + balance: asset and expense pair", () => {
    const ledger = new Ledger();
    ledger.append({
      description: "SaaS charge",
      postings: [
        {
          account: "expense:saas:vercel",
          amount: { value: 12_00, currency: "USD" },
        },
        {
          account: "asset:cash:operating",
          amount: { value: -12_00, currency: "USD" },
        },
      ],
    });

    expect(ledger.balance("expense:saas:vercel")).toEqual({
      value: 12_00,
      currency: "USD",
    });
    expect(ledger.balance("asset:cash:operating")).toEqual({
      value: -12_00,
      currency: "USD",
    });
  });

  it("rejects unbalanced postings", () => {
    const ledger = new Ledger();
    expect(() =>
      ledger.append({
        description: "Broken",
        postings: [
          {
            account: "expense:other",
            amount: { value: 100, currency: "USD" },
          },
        ],
      }),
    ).toThrow(InvalidLedgerEntryError);
  });

  it("requires each currency to balance independently", () => {
    const ledger = new Ledger();
    expect(() =>
      ledger.append({
        description: "Cross-currency leak",
        postings: [
          { account: "a", amount: { value: 100, currency: "USD" } },
          { account: "b", amount: { value: -100, currency: "EUR" } },
        ],
      }),
    ).toThrow(InvalidLedgerEntryError);

    expect(() =>
      ledger.append({
        description: "OK multi-ccy",
        postings: [
          { account: "a1", amount: { value: 50, currency: "USD" } },
          { account: "a2", amount: { value: -50, currency: "USD" } },
          { account: "b1", amount: { value: 30, currency: "EUR" } },
          { account: "b2", amount: { value: -30, currency: "EUR" } },
        ],
      }),
    ).not.toThrow();
  });

  it("balance respects asOf cutoff", () => {
    const ledger = new Ledger();
    const t1 = "2026-01-01T12:00:00.000Z";
    const t2 = "2026-01-03T12:00:00.000Z";

    ledger.append({
      id: "e1",
      timestamp: t1,
      description: "First",
      postings: [
        { account: "asset:cash", amount: { value: 50, currency: "USD" } },
        { account: "income:other", amount: { value: -50, currency: "USD" } },
      ],
    });

    ledger.append({
      id: "e2",
      timestamp: t2,
      description: "Second",
      postings: [
        { account: "asset:cash", amount: { value: 25, currency: "USD" } },
        { account: "income:other", amount: { value: -25, currency: "USD" } },
      ],
    });

    const mid = new Date("2026-01-02T00:00:00.000Z");
    expect(ledger.balance("asset:cash", mid)).toEqual({
      value: 50,
      currency: "USD",
    });

    const end = new Date("2026-01-04T00:00:00.000Z");
    expect(ledger.balance("asset:cash", end)).toEqual({
      value: 75,
      currency: "USD",
    });
  });

  it("snapshot aggregates all accounts", () => {
    const ledger = new Ledger();
    ledger.append({
      description: "Opening",
      postings: [
        { account: "asset:cash", amount: { value: 100, currency: "USD" } },
        { account: "equity:opening", amount: { value: -100, currency: "USD" } },
      ],
    });

    const snap = ledger.snapshot();
    expect(snap.balances["asset:cash"]).toEqual({
      value: 100,
      currency: "USD",
    });
    expect(snap.balances["equity:opening"]).toEqual({
      value: -100,
      currency: "USD",
    });
    expect(snap.asOf).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("append-only: stored entries are not mutated when caller mutates input", () => {
    const ledger = new Ledger();
    const postings = [
      { account: "a", amount: { value: 10, currency: "USD" } },
      { account: "b", amount: { value: -10, currency: "USD" } },
    ];
    const payload = {
      description: "Mutate me",
      postings,
    };

    ledger.append(payload);

    postings[0]!.account = "compromised";
    postings[0]!.amount.value = 999;

    const [first] = ledger.entries();
    expect(first?.postings[0]?.account).toBe("a");
    expect(first?.postings[0]?.amount.value).toBe(10);
  });

  it("empty ledger: balance is zero (USD)", () => {
    const ledger = new Ledger();
    expect(ledger.balance("asset:cash")).toEqual({
      value: 0,
      currency: "USD",
    });
  });

  it("filter by account, reference, and metadata", () => {
    const ledger = new Ledger();
    ledger.append({
      description: "A",
      reference: "ref-a",
      metadata: { source: "plaid" },
      postings: [
        { account: "x", amount: { value: 1, currency: "USD" } },
        { account: "y", amount: { value: -1, currency: "USD" } },
      ],
    });
    ledger.append({
      description: "B",
      reference: "ref-b",
      metadata: { source: "manual" },
      postings: [
        { account: "z", amount: { value: 2, currency: "USD" } },
        { account: "w", amount: { value: -2, currency: "USD" } },
      ],
    });

    const hitsX = ledger.filter((e) =>
      e.postings.some((p) => p.account === "x"),
    );
    expect(hitsX).toHaveLength(1);
    expect(hitsX[0]?.reference).toBe("ref-a");

    const byRef = ledger.filter((e) => e.reference === "ref-b");
    expect(byRef).toHaveLength(1);
    expect(byRef[0]?.metadata?.source).toBe("manual");

    const plaid = ledger.filter((e) => e.metadata?.source === "plaid");
    expect(plaid).toHaveLength(1);
  });
});
