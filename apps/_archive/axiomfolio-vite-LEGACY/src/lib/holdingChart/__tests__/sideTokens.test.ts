import { describe, expect, it } from "vitest";

import { isBuySide, isSellSide, BUY_TOKENS, SELL_TOKENS } from "../sideTokens";

describe("sideTokens", () => {
  it("BUY_TOKENS and SELL_TOKENS are disjoint", () => {
    for (const buy of BUY_TOKENS) {
      expect(SELL_TOKENS.has(buy)).toBe(false);
    }
  });

  describe("isBuySide", () => {
    it.each(["BUY", "B", "BOUGHT", "buy", "b", "bought", " Buy ", "  BOUGHT "])(
      "accepts %p",
      (token) => {
        expect(isBuySide(token)).toBe(true);
      },
    );

    it.each(["SELL", "S", "SOLD", "TRANSFER", "JNK", ""])(
      "rejects %p",
      (token) => {
        expect(isBuySide(token)).toBe(false);
      },
    );

    it("rejects null / undefined", () => {
      expect(isBuySide(null)).toBe(false);
      expect(isBuySide(undefined)).toBe(false);
    });
  });

  describe("isSellSide", () => {
    it.each(["SELL", "S", "SOLD", "sell", "s", "sold", " Sell ", "  SOLD "])(
      "accepts %p",
      (token) => {
        expect(isSellSide(token)).toBe(true);
      },
    );

    it.each(["BUY", "B", "BOUGHT", "TRANSFER", ""])(
      "rejects %p",
      (token) => {
        expect(isSellSide(token)).toBe(false);
      },
    );

    it("rejects null / undefined", () => {
      expect(isSellSide(null)).toBe(false);
      expect(isSellSide(undefined)).toBe(false);
    });
  });
});
