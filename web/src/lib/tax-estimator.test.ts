import { describe, it, expect } from "vitest";
import { estimateRefund } from "./tax-estimator";

describe("estimateRefund", () => {
  it("calculates refund for $50k wages with $8k federal withheld", () => {
    const result = estimateRefund(5_000_000, 800_000);

    expect(result.adjustedGrossIncome).toBe(5_000_000);
    expect(result.standardDeduction).toBe(1_575_000);
    expect(result.taxableIncome).toBe(3_425_000);
    // 10% on 1,192,500 = 119,250
    // 12% on 2,232,500 = 267,900
    expect(result.federalTax).toBe(387_150);
    expect(result.totalWithheld).toBe(800_000);
    expect(result.refundAmount).toBe(412_850);
    expect(result.owedAmount).toBe(0);
  });

  it("calculates owed amount when withholding is low", () => {
    const result = estimateRefund(10_000_000, 100_000);

    expect(result.taxableIncome).toBe(8_425_000);
    // 10% on 1,192,500 = 119,250
    // 12% on 3,655,000 = 438,600
    // 22% on 3,577,500 = 787,050
    expect(result.federalTax).toBe(1_344_900);
    expect(result.refundAmount).toBe(0);
    expect(result.owedAmount).toBe(1_244_900);
  });

  it("returns zero tax when income is below standard deduction", () => {
    const result = estimateRefund(1_000_000, 50_000);

    expect(result.taxableIncome).toBe(0);
    expect(result.federalTax).toBe(0);
    expect(result.refundAmount).toBe(50_000);
    expect(result.owedAmount).toBe(0);
  });

  it("handles zero wages", () => {
    const result = estimateRefund(0, 0);

    expect(result.adjustedGrossIncome).toBe(0);
    expect(result.taxableIncome).toBe(0);
    expect(result.federalTax).toBe(0);
    expect(result.refundAmount).toBe(0);
    expect(result.owedAmount).toBe(0);
  });

  it("matches backend test: exact bracket boundaries", () => {
    const result = estimateRefund(
      1_192_500 + 1_575_000, // wages = bracket_max + deduction
      0,
    );

    expect(result.taxableIncome).toBe(1_192_500);
    expect(result.federalTax).toBe(119_250); // 10% of 1,192,500
  });

  it("totalWithheld equals federal withheld only", () => {
    const result = estimateRefund(5_000_000, 300_000);

    expect(result.totalWithheld).toBe(300_000);
  });
});
