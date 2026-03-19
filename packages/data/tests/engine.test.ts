import { describe, it, expect, beforeEach } from "vitest";
import { loadFormationData, getStateFormationRules, getAllFormationStates, getFormationFee } from "../src/engine/formation";
import { loadTaxData, getStateTaxRules, calculateStateTax } from "../src/engine/tax";
import { checkFreshness } from "../src/engine/freshness";
import type { FormationRules } from "../src/types/formation";
import type { StateTaxRules } from "../src/types/tax";

const mockVerification = {
  last_verified: "2026-03-18T00:00:00.000Z",
  sources: [{ name: "Test", url: "https://example.com", accessed_at: "2026-03-18T00:00:00.000Z" }],
  verified_by: "human_review" as const,
  confidence: 0.95,
};

describe("Formation Engine", () => {
  const deFormation: FormationRules = {
    state: "DE",
    state_name: "Delaware",
    entity_type: "LLC",
    sos_url: "https://corp.delaware.gov",
    filing_office: "Division of Corporations",
    fees: {
      standard: { amount_cents: 9000, description: "Standard", is_expedited: false, processing_days: 15 },
      expedited: { amount_cents: 10000, description: "Expedited", is_expedited: true, processing_days: 1 },
    },
    filing: { primary: { method: "api", url: "https://icis.corp.delaware.gov" } },
    requirements: {
      articles_of_organization: true,
      operating_agreement_required: false,
      publication_required: false,
      registered_agent_required: true,
      annual_report_required: false,
      franchise_tax: true,
      franchise_tax_amount_cents: 30000,
    },
    processing: { standard_days: 15, expedited_days: 1 },
    naming: { required_suffix: ["LLC"], restricted_words: [] },
    compliance: {},
    verification: mockVerification,
  };

  beforeEach(() => {
    loadFormationData("DE", deFormation);
  });

  it("loads and retrieves formation rules", () => {
    const rules = getStateFormationRules("DE");
    expect(rules).toBeDefined();
    expect(rules?.state_name).toBe("Delaware");
  });

  it("returns undefined for unloaded states", () => {
    expect(getStateFormationRules("CA")).toBeUndefined();
  });

  it("lists loaded states", () => {
    expect(getAllFormationStates()).toContain("DE");
  });

  it("returns standard fee", () => {
    expect(getFormationFee("DE")).toBe(9000);
  });

  it("returns expedited fee", () => {
    expect(getFormationFee("DE", true)).toBe(10000);
  });
});

describe("Tax Engine", () => {
  const flatTax: StateTaxRules = {
    state: "CO",
    state_name: "Colorado",
    tax_year: 2026,
    income_tax: {
      type: "flat",
      flat_rate_bps: 440,
    },
    standard_deductions: [
      { filing_status: "single", amount_cents: 1510000 },
    ],
    personal_exemption: { amount_cents: 0, phases_out: false },
    notable_credits: [],
    notable_deductions: [],
    local_taxes: { has_local_income_tax: false },
    reciprocity: { has_reciprocity: false },
    dor_url: "https://tax.colorado.gov",
    verification: mockVerification,
  };

  beforeEach(() => {
    loadTaxData("CO", flatTax);
  });

  it("calculates flat tax correctly", () => {
    // $100,000 income = 10,000,000 cents
    // Standard deduction: $15,100 = 1,510,000 cents
    // Taxable: $84,900 = 8,490,000 cents
    // Tax: 8,490,000 * 440 / 10000 = 373,560 cents = $3,735.60
    const tax = calculateStateTax("CO", 10000000, "single");
    expect(tax).toBe(373560);
  });

  it("returns 0 for no-income-tax states", () => {
    const noTax: StateTaxRules = {
      ...flatTax,
      state: "TX",
      state_name: "Texas",
      income_tax: { type: "none" },
    };
    loadTaxData("TX", noTax);
    expect(calculateStateTax("TX", 10000000, "single")).toBe(0);
  });

  it("returns undefined for unloaded states", () => {
    expect(calculateStateTax("NY", 5000000, "single")).toBeUndefined();
  });
});

describe("Freshness", () => {
  it("marks recent data as fresh", () => {
    const result = checkFreshness("CA", "formation", new Date().toISOString());
    expect(result.is_stale).toBe(false);
    expect(result.days_since_verification).toBe(0);
  });

  it("marks old data as stale", () => {
    const oldDate = new Date();
    oldDate.setDate(oldDate.getDate() - 101);
    const result = checkFreshness("CA", "tax", oldDate.toISOString());
    expect(result.is_stale).toBe(true);
    expect(result.days_since_verification).toBeGreaterThanOrEqual(100);
  });

  it("treats invalid date as stale", () => {
    const result = checkFreshness("CA", "tax", "not-a-date");
    expect(result.is_stale).toBe(true);
    expect(result.days_since_verification).toBe(Infinity);
  });

  it("treats empty string date as stale", () => {
    const result = checkFreshness("CA", "formation", "");
    expect(result.is_stale).toBe(true);
    expect(result.days_since_verification).toBe(Infinity);
  });
});
