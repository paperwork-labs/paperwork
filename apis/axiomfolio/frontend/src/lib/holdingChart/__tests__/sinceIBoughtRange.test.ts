import { describe, expect, it } from "vitest";

import {
  earliestBuyDate,
  periodCoveringDate,
} from "../sinceIBoughtRange";

const TODAY = new Date("2026-04-19T12:00:00Z");

describe("earliestBuyDate", () => {
  it("returns null for empty input", () => {
    expect(earliestBuyDate([], TODAY)).toBeNull();
  });

  it("returns null when no rows are buys", () => {
    const rows = [
      { transaction_date: "2024-01-01T10:00:00Z", side: "SELL" },
      { transaction_date: "2024-02-01T10:00:00Z", side: "S" },
    ];
    expect(earliestBuyDate(rows, TODAY)).toBeNull();
  });

  it("picks the earliest BUY across mixed sides and date columns", () => {
    const rows = [
      { transaction_date: "2024-03-01T10:00:00Z", side: "SELL" },
      { transaction_date: "2024-02-15T10:00:00Z", side: "BUY" },
      { date: "2023-11-04T09:30:00Z", side: "B" },
      { transaction_date: "2025-01-10T10:00:00Z", side: "BUY" },
    ];
    expect(earliestBuyDate(rows, TODAY)).toBe("2023-11-04");
  });

  it("treats lowercase / whitespace sides as buys", () => {
    const rows = [
      { transaction_date: "2024-04-01T10:00:00Z", side: "  buy  " },
      { transaction_date: "2024-03-01T10:00:00Z", side: "Bought" },
    ];
    expect(earliestBuyDate(rows, TODAY)).toBe("2024-03-01");
  });

  it("ignores rows missing a parseable date", () => {
    const rows = [
      { side: "BUY" },
      { transaction_date: "not a date", side: "BUY" },
      { transaction_date: "2024-06-01T10:00:00Z", side: "BUY" },
    ];
    expect(earliestBuyDate(rows, TODAY)).toBe("2024-06-01");
  });

  it("ignores rows missing a side entirely", () => {
    const rows = [
      { transaction_date: "2024-01-01T10:00:00Z" },
      { transaction_date: "2024-05-05T10:00:00Z", side: "BUY" },
    ];
    expect(earliestBuyDate(rows, TODAY)).toBe("2024-05-05");
  });

  it("ignores future-dated buys (data-quality guard)", () => {
    const rows = [
      { transaction_date: "2030-01-01T10:00:00Z", side: "BUY" },
      { transaction_date: "2026-04-19T10:00:00Z", side: "BUY" },
    ];
    // Today is 2026-04-19 so the future row is dropped, the same-day row
    // wins, and the 2030 row is silently ignored.
    expect(earliestBuyDate(rows, TODAY)).toBe("2026-04-19");
  });

  it("returns null when the only buys are in the future", () => {
    const rows = [{ transaction_date: "2030-01-01T10:00:00Z", side: "BUY" }];
    expect(earliestBuyDate(rows, TODAY)).toBeNull();
  });

  it("normalises to UTC YYYY-MM-DD regardless of input timezone", () => {
    // 2024-06-01 23:30 PST = 2024-06-02 06:30 UTC; the UTC day wins.
    const rows = [{ transaction_date: "2024-06-01T23:30:00-08:00", side: "BUY" }];
    expect(earliestBuyDate(rows, TODAY)).toBe("2024-06-02");
  });
});

describe("periodCoveringDate", () => {
  it("returns '1mo' for dates within the last month", () => {
    expect(periodCoveringDate("2026-04-01", TODAY)).toBe("1mo");
    expect(periodCoveringDate("2026-04-19", TODAY)).toBe("1mo");
  });

  it("returns '3mo' for dates within the last quarter", () => {
    expect(periodCoveringDate("2026-02-01", TODAY)).toBe("3mo");
  });

  it("returns '6mo' for dates within six months", () => {
    expect(periodCoveringDate("2025-12-01", TODAY)).toBe("6mo");
  });

  it("returns '1y' for dates within a year", () => {
    expect(periodCoveringDate("2025-06-01", TODAY)).toBe("1y");
  });

  it("returns '5y' for dates within five years", () => {
    expect(periodCoveringDate("2022-04-19", TODAY)).toBe("5y");
  });

  it("returns 'max' for dates older than five years", () => {
    expect(periodCoveringDate("2010-01-01", TODAY)).toBe("max");
  });

  it("returns '1y' fallback for unparseable dates", () => {
    expect(periodCoveringDate("not a date", TODAY)).toBe("1y");
  });
});
