import { describe, expect, it } from "vitest";

import {
  bucketDividendsByDay,
  bucketTradesByDay,
  buildTradeMarkers,
  periodToDividendDays,
  type DividendRow,
  type TradeRow,
} from "../tradeMarkers";

describe("bucketTradesByDay", () => {
  it("returns empty for empty input", () => {
    expect(bucketTradesByDay([])).toEqual([]);
  });

  it("groups multiple rows on the same day, accepts B / S aliases case-insensitively", () => {
    const rows: TradeRow[] = [
      { transaction_date: "2025-09-01T14:30:00Z", side: "buy", quantity: 10, price: 100 },
      { transaction_date: "2025-09-01T15:45:00Z", side: "B", quantity: 5, price: 102 },
      { transaction_date: "2025-09-01T16:00:00Z", side: "S", quantity: 3, price: 105 },
    ];
    const buckets = bucketTradesByDay(rows);
    expect(buckets).toHaveLength(1);
    const b = buckets[0];
    expect(b.dayKey).toBe("2025-09-01");
    expect(b.buys).toHaveLength(2);
    expect(b.sells).toHaveLength(1);
    // Net shares = (10 + 5) − 3 = 12.
    expect(b.totalShares).toBe(12);
    // Weighted avg = (10·100 + 5·102 + 3·105) / 18 = 1825 / 18.
    expect(b.weightedAvgPrice).toBeCloseTo(1825 / 18, 5);
  });

  it("recognizes every shared buy alias (BUY / B / BOUGHT) and every sell alias (SELL / S / SOLD)", () => {
    // Regression: `tradeMarkers.isBuySide` used to accept only BUY / B,
    // while `sinceIBoughtRange.isBuySide` accepted BOUGHT too — so a
    // BOUGHT-side row counted toward "Since I bought" but silently
    // disappeared from the marker overlay. Both predicates now share
    // `sideTokens.ts`, and the full token set must round-trip.
    const rows: TradeRow[] = [
      { transaction_date: "2025-09-01", side: "BUY", quantity: 1 },
      { transaction_date: "2025-09-01", side: "B", quantity: 1 },
      { transaction_date: "2025-09-01", side: "bought", quantity: 1 },
      { transaction_date: "2025-09-02", side: "SELL", quantity: 1 },
      { transaction_date: "2025-09-02", side: "S", quantity: 1 },
      { transaction_date: "2025-09-02", side: "Sold", quantity: 1 },
    ];
    const buckets = bucketTradesByDay(rows);
    expect(buckets).toHaveLength(2);
    const day1 = buckets.find((b) => b.dayKey === "2025-09-01")!;
    const day2 = buckets.find((b) => b.dayKey === "2025-09-02")!;
    expect(day1.buys).toHaveLength(3);
    expect(day1.sells).toHaveLength(0);
    expect(day2.buys).toHaveLength(0);
    expect(day2.sells).toHaveLength(3);
  });

  it("falls back to `date` when `transaction_date` is missing", () => {
    const rows: TradeRow[] = [
      { date: "2025-08-15", side: "BUY", quantity: 7, price: 50 },
    ];
    const buckets = bucketTradesByDay(rows);
    expect(buckets).toHaveLength(1);
    expect(buckets[0].dayKey).toBe("2025-08-15");
    expect(buckets[0].buys).toHaveLength(1);
  });

  it("skips rows with unparseable dates and unknown sides", () => {
    const rows: TradeRow[] = [
      { transaction_date: "not-a-date", side: "BUY", quantity: 1 },
      { transaction_date: "2025-01-01T00:00:00Z", side: "transfer", quantity: 1 },
      { transaction_date: "2025-01-02T00:00:00Z", side: "BUY", quantity: 1 },
    ];
    const buckets = bucketTradesByDay(rows);
    expect(buckets).toHaveLength(1);
    expect(buckets[0].dayKey).toBe("2025-01-02");
  });

  it("treats negative quantities as their absolute value", () => {
    const rows: TradeRow[] = [
      { transaction_date: "2025-03-04", side: "SELL", quantity: -5, price: 80 },
    ];
    const buckets = bucketTradesByDay(rows);
    expect(buckets[0].totalShares).toBe(-5);
    expect(buckets[0].weightedAvgPrice).toBe(80);
  });

  it("returns 0 weighted price when no rows had a price", () => {
    const rows: TradeRow[] = [
      { transaction_date: "2025-04-01", side: "BUY", quantity: 10 },
    ];
    const buckets = bucketTradesByDay(rows);
    expect(buckets[0].weightedAvgPrice).toBe(0);
  });

  it("emits buckets in ascending day order", () => {
    const rows: TradeRow[] = [
      { transaction_date: "2025-12-01", side: "BUY", quantity: 1 },
      { transaction_date: "2025-01-01", side: "BUY", quantity: 1 },
      { transaction_date: "2025-06-01", side: "BUY", quantity: 1 },
    ];
    const buckets = bucketTradesByDay(rows);
    expect(buckets.map((b) => b.dayKey)).toEqual([
      "2025-01-01",
      "2025-06-01",
      "2025-12-01",
    ]);
  });
});

describe("bucketDividendsByDay", () => {
  it("filters to symbol case-insensitively", () => {
    const rows: DividendRow[] = [
      { symbol: "aapl", ex_date: "2025-08-15", dividend_per_share: 0.24, shares_held: 100, total_dividend: 24 },
      { symbol: "MSFT", ex_date: "2025-08-15", dividend_per_share: 0.75, shares_held: 50, total_dividend: 37.5 },
    ];
    const buckets = bucketDividendsByDay(rows, "AAPL");
    expect(buckets).toHaveLength(1);
    expect(buckets[0].perShare).toBeCloseTo(0.24, 5);
    expect(buckets[0].totalAmount).toBeCloseTo(24, 5);
  });

  it("sums total_dividend across multiple lots same ex-date", () => {
    const rows: DividendRow[] = [
      { symbol: "AAPL", ex_date: "2025-08-15", dividend_per_share: 0.24, shares_held: 100, total_dividend: 24, account_id: "acct-1" },
      { symbol: "AAPL", ex_date: "2025-08-15", dividend_per_share: 0.24, shares_held: 50, total_dividend: 12, account_id: "acct-2" },
    ];
    const buckets = bucketDividendsByDay(rows, "AAPL");
    expect(buckets).toHaveLength(1);
    expect(buckets[0].totalAmount).toBeCloseTo(36, 5);
    expect(buckets[0].rowCount).toBe(2);
    // Weighted per-share is the same since both lots paid the same per-share rate.
    expect(buckets[0].perShare).toBeCloseTo(0.24, 5);
  });

  it("returns empty when symbol is whitespace", () => {
    const rows: DividendRow[] = [
      { symbol: "AAPL", ex_date: "2025-08-15", dividend_per_share: 0.24 },
    ];
    expect(bucketDividendsByDay(rows, "")).toEqual([]);
    expect(bucketDividendsByDay(rows, "   ")).toEqual([]);
  });

  it("skips rows with unparseable ex_date", () => {
    const rows: DividendRow[] = [
      { symbol: "AAPL", ex_date: undefined, dividend_per_share: 0.24, shares_held: 100, total_dividend: 24 },
      { symbol: "AAPL", ex_date: "nope", dividend_per_share: 0.24, shares_held: 100, total_dividend: 24 },
      { symbol: "AAPL", ex_date: "2025-09-01", dividend_per_share: 0.30, shares_held: 100, total_dividend: 30 },
    ];
    const buckets = bucketDividendsByDay(rows, "AAPL");
    expect(buckets).toHaveLength(1);
    expect(buckets[0].dayKey).toBe("2025-09-01");
  });

  it("preserves the first non-empty currency", () => {
    const rows: DividendRow[] = [
      { symbol: "AAPL", ex_date: "2025-09-01", dividend_per_share: 0.24, shares_held: 100, total_dividend: 24, currency: "USD" },
    ];
    expect(bucketDividendsByDay(rows, "AAPL")[0].currency).toBe("USD");
  });

  it("falls back to a simple per-share average when shares_held is missing", () => {
    const rows: DividendRow[] = [
      { symbol: "AAPL", ex_date: "2025-09-01", dividend_per_share: 0.20 },
      { symbol: "AAPL", ex_date: "2025-09-01", dividend_per_share: 0.30 },
    ];
    const buckets = bucketDividendsByDay(rows, "AAPL");
    expect(buckets[0].perShare).toBeCloseTo(0.25, 5);
  });

  it("emits buckets in ascending day order", () => {
    const rows: DividendRow[] = [
      { symbol: "AAPL", ex_date: "2025-12-01", dividend_per_share: 0.24, shares_held: 1, total_dividend: 0.24 },
      { symbol: "AAPL", ex_date: "2025-03-01", dividend_per_share: 0.24, shares_held: 1, total_dividend: 0.24 },
      { symbol: "AAPL", ex_date: "2025-06-01", dividend_per_share: 0.24, shares_held: 1, total_dividend: 0.24 },
    ];
    const buckets = bucketDividendsByDay(rows, "AAPL");
    expect(buckets.map((b) => b.dayKey)).toEqual([
      "2025-03-01",
      "2025-06-01",
      "2025-12-01",
    ]);
  });
});

describe("buildTradeMarkers", () => {
  it("emits arrowUp belowBar for net-buy days", () => {
    const buckets = bucketTradesByDay([
      { transaction_date: "2025-09-01", side: "BUY", quantity: 10, price: 100 },
    ]);
    const markers = buildTradeMarkers(buckets);
    expect(markers).toHaveLength(1);
    expect(markers[0].shape).toBe("arrowUp");
    expect(markers[0].position).toBe("belowBar");
    expect(markers[0].id).toBe("2025-09-01:buy");
    // Single trade → no count badge.
    expect(markers[0].text).toBeUndefined();
  });

  it("emits arrowDown aboveBar for sell-only days", () => {
    const buckets = bucketTradesByDay([
      { transaction_date: "2025-09-02", side: "SELL", quantity: 10, price: 100 },
    ]);
    const markers = buildTradeMarkers(buckets);
    expect(markers[0].shape).toBe("arrowDown");
    expect(markers[0].position).toBe("aboveBar");
    expect(markers[0].id).toBe("2025-09-02:sell");
  });

  it("emits a circle 'B+S' marker for the simple 1-buy + 1-sell mixed day", () => {
    const buckets = bucketTradesByDay([
      { transaction_date: "2025-09-03", side: "BUY", quantity: 10, price: 100 },
      { transaction_date: "2025-09-03", side: "SELL", quantity: 5, price: 102 },
    ]);
    const markers = buildTradeMarkers(buckets);
    expect(markers[0].shape).toBe("circle");
    expect(markers[0].text).toBe("B+S");
    expect(markers[0].id).toBe("2025-09-03:mixed");
  });

  it("appends a count badge to mixed days with more than 2 trades", () => {
    // 5 buys + 3 sells = 8 → "B+S ×8". Without the count, this cluster
    // would visually flatten to the same glyph as a 1-buy + 1-sell day.
    const rows: TradeRow[] = [];
    for (let i = 0; i < 5; i += 1) {
      rows.push({ transaction_date: "2025-09-04", side: "BUY", quantity: 1, price: 10 });
    }
    for (let i = 0; i < 3; i += 1) {
      rows.push({ transaction_date: "2025-09-04", side: "SELL", quantity: 1, price: 12 });
    }
    const markers = buildTradeMarkers(bucketTradesByDay(rows));
    expect(markers).toHaveLength(1);
    expect(markers[0].shape).toBe("circle");
    expect(markers[0].text).toBe("B+S ×8");
    expect(markers[0].id).toBe("2025-09-04:mixed");
  });

  it("adds a count badge when there are 2+ trades same side same day", () => {
    const buckets = bucketTradesByDay([
      { transaction_date: "2025-09-04", side: "BUY", quantity: 1, price: 10 },
      { transaction_date: "2025-09-04", side: "BUY", quantity: 1, price: 10 },
      { transaction_date: "2025-09-04", side: "BUY", quantity: 1, price: 10 },
    ]);
    const markers = buildTradeMarkers(buckets);
    expect(markers[0].text).toBe("×3");
  });
});

describe("periodToDividendDays", () => {
  it("maps each known period", () => {
    expect(periodToDividendDays("1mo")).toBe(31);
    expect(periodToDividendDays("3mo")).toBe(93);
    expect(periodToDividendDays("6mo")).toBe(186);
    expect(periodToDividendDays("ytd")).toBe(365);
    expect(periodToDividendDays("1y")).toBe(365);
    expect(periodToDividendDays("5y")).toBe(1825);
    expect(periodToDividendDays("max")).toBe(3650);
    expect(periodToDividendDays("since")).toBe(1825);
  });

  it("falls back to 365 for unknown periods", () => {
    expect(periodToDividendDays("garbage")).toBe(365);
  });
});
