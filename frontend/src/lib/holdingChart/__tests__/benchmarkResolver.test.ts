import { describe, expect, it } from "vitest";

import {
  describeBenchmark,
  resolveBenchmarkSymbol,
  SECTOR_TO_ETF,
} from "../benchmarkResolver";

describe("resolveBenchmarkSymbol", () => {
  it("returns SPY by default when no snapshot or override is provided", () => {
    expect(resolveBenchmarkSymbol("AAPL")).toBe("SPY");
    expect(resolveBenchmarkSymbol("AAPL", null)).toBe("SPY");
  });

  it("uppercases and trims explicit overrides", () => {
    expect(resolveBenchmarkSymbol("AAPL", null, "qqq")).toBe("QQQ");
    expect(resolveBenchmarkSymbol("AAPL", null, "  iwm  ")).toBe("IWM");
  });

  it("ignores empty or whitespace-only overrides", () => {
    expect(resolveBenchmarkSymbol("AAPL", null, "")).toBe("SPY");
    expect(resolveBenchmarkSymbol("AAPL", null, "   ")).toBe("SPY");
  });

  it("override beats every other rule", () => {
    expect(
      resolveBenchmarkSymbol(
        "AAPL",
        { instrument_type: "ETF", sector: "Technology" },
        "QQQ",
      ),
    ).toBe("QQQ");
  });

  it("ETF instrument types resolve to SPY (broad market reference)", () => {
    expect(
      resolveBenchmarkSymbol("XLK", { instrument_type: "ETF", sector: "Technology" }),
    ).toBe("SPY");
    expect(
      resolveBenchmarkSymbol("spy", { instrument_type: "etf" }),
    ).toBe("SPY");
  });

  it("CRYPTO instrument types resolve to BTC-USD", () => {
    expect(
      resolveBenchmarkSymbol("DOGE-USD", { instrument_type: "CRYPTO" }),
    ).toBe("BTC-USD");
  });

  it.each([
    ["BTC", "BTC-USD"],
    ["BTC-USD", "BTC-USD"],
    ["ETH-USD", "BTC-USD"],
    ["sol", "BTC-USD"],
    ["DOGEUSD", "BTC-USD"],
    ["LINK-USD", "BTC-USD"],
  ])("recognises %s as crypto via ticker pattern → %s", (sym, expected) => {
    expect(resolveBenchmarkSymbol(sym)).toBe(expected);
  });

  it("falls through to sector lookup when not ETF / crypto", () => {
    expect(
      resolveBenchmarkSymbol("AAPL", { sector: "Information Technology" }),
    ).toBe("XLK");
    expect(
      resolveBenchmarkSymbol("UNH", { sector: "Health Care" }),
    ).toBe("XLV");
    expect(
      resolveBenchmarkSymbol("JPM", { sector: "Financials" }),
    ).toBe("XLF");
    expect(
      resolveBenchmarkSymbol("DIS", { sector: "Communication Services" }),
    ).toBe("XLC");
    expect(
      resolveBenchmarkSymbol("AMZN", { sector: "Consumer Discretionary" }),
    ).toBe("XLY");
    expect(
      resolveBenchmarkSymbol("AMZN", { sector: "Consumer Cyclical" }),
    ).toBe("XLY");
    expect(
      resolveBenchmarkSymbol("PG", { sector: "Consumer Staples" }),
    ).toBe("XLP");
    expect(
      resolveBenchmarkSymbol("PG", { sector: "Consumer Defensive" }),
    ).toBe("XLP");
    expect(
      resolveBenchmarkSymbol("XOM", { sector: "Energy" }),
    ).toBe("XLE");
    expect(
      resolveBenchmarkSymbol("NEE", { sector: "Utilities" }),
    ).toBe("XLU");
    expect(
      resolveBenchmarkSymbol("PLD", { sector: "Real Estate" }),
    ).toBe("XLRE");
    expect(
      resolveBenchmarkSymbol("CAT", { sector: "Industrials" }),
    ).toBe("XLI");
    expect(
      resolveBenchmarkSymbol("DOW", { sector: "Basic Materials" }),
    ).toBe("XLB");
    expect(
      resolveBenchmarkSymbol("DOW", { sector: "Materials" }),
    ).toBe("XLB");
  });

  it("sector match is case-insensitive and tolerates whitespace", () => {
    expect(
      resolveBenchmarkSymbol("AAPL", { sector: "  technology  " }),
    ).toBe("XLK");
    expect(
      resolveBenchmarkSymbol("AAPL", { sector: "TECHNOLOGY" }),
    ).toBe("XLK");
  });

  it("falls back to SPY when sector is null, empty, or unknown", () => {
    expect(resolveBenchmarkSymbol("AAPL", { sector: null })).toBe("SPY");
    expect(resolveBenchmarkSymbol("AAPL", { sector: "" })).toBe("SPY");
    expect(resolveBenchmarkSymbol("AAPL", { sector: "Mystery Box" })).toBe("SPY");
  });

  it("SECTOR_TO_ETF map exposes the patterns for UI display", () => {
    // Acts as a regression guard: if an entry is removed, downstream UI
    // (e.g. "see all sector ETFs" picker) would silently lose a row.
    const etfs = SECTOR_TO_ETF.map(([, etf]) => etf);
    expect(etfs).toContain("XLK");
    expect(etfs).toContain("XLRE");
    expect(etfs).toContain("XLB");
  });
});

describe("describeBenchmark", () => {
  it("returns rich descriptor for known indices", () => {
    expect(describeBenchmark("SPY")).toEqual({
      label: "vs S&P 500",
      tooltip: "S&P 500 ETF",
    });
    expect(describeBenchmark("XLK")).toEqual({
      label: "vs XLK",
      tooltip: "Technology Select Sector SPDR",
    });
    expect(describeBenchmark("BTC-USD")).toEqual({
      label: "vs Bitcoin",
      tooltip: "Bitcoin / USD",
    });
  });

  it("normalises case before lookup", () => {
    expect(describeBenchmark("spy").label).toBe("vs S&P 500");
    expect(describeBenchmark("  qqq  ").tooltip).toContain("Nasdaq");
  });

  it("falls back to a generic descriptor for unknown tickers", () => {
    expect(describeBenchmark("ACME")).toEqual({
      label: "vs ACME",
      tooltip: "ACME",
    });
  });
});
