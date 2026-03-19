import { describe, it, expect } from "vitest";
import { FormationRulesSchema } from "../src/schemas/formation.schema";
import { StateTaxRulesSchema } from "../src/schemas/tax.schema";
import { StateCodeSchema, VerificationMetaSchema } from "../src/schemas/common.schema";

describe("StateCodeSchema", () => {
  it("accepts valid state codes", () => {
    expect(StateCodeSchema.parse("CA")).toBe("CA");
    expect(StateCodeSchema.parse("NY")).toBe("NY");
    expect(StateCodeSchema.parse("DC")).toBe("DC");
  });

  it("rejects invalid state codes", () => {
    expect(() => StateCodeSchema.parse("XX")).toThrow();
    expect(() => StateCodeSchema.parse("")).toThrow();
    expect(() => StateCodeSchema.parse("California")).toThrow();
  });
});

describe("VerificationMetaSchema", () => {
  it("accepts valid verification metadata", () => {
    const valid = {
      last_verified: "2026-03-18T00:00:00.000Z",
      sources: [{ name: "State SOS", url: "https://sos.ca.gov", accessed_at: "2026-03-18T00:00:00.000Z" }],
      verified_by: "human_review",
      confidence: 0.95,
    };
    expect(() => VerificationMetaSchema.parse(valid)).not.toThrow();
  });

  it("rejects confidence outside 0-1 range", () => {
    const invalid = {
      last_verified: "2026-03-18T00:00:00.000Z",
      sources: [{ name: "Source", url: "https://example.com", accessed_at: "2026-03-18T00:00:00.000Z" }],
      verified_by: "ai_extraction",
      confidence: 1.5,
    };
    expect(() => VerificationMetaSchema.parse(invalid)).toThrow();
  });

  it("rejects empty sources array", () => {
    const invalid = {
      last_verified: "2026-03-18T00:00:00.000Z",
      sources: [],
      verified_by: "ai_extraction",
      confidence: 0.8,
    };
    expect(() => VerificationMetaSchema.parse(invalid)).toThrow();
  });
});

describe("FormationRulesSchema", () => {
  const validFormation = {
    state: "DE",
    state_name: "Delaware",
    entity_type: "LLC",
    sos_url: "https://corp.delaware.gov",
    filing_office: "Division of Corporations",
    fees: {
      standard: { amount_cents: 9000, description: "Standard LLC filing fee", is_expedited: false, processing_days: 15 },
      expedited: { amount_cents: 10000, description: "24-hour expedited", is_expedited: true, processing_days: 1 },
    },
    filing: {
      primary: { method: "api", url: "https://icis.corp.delaware.gov/publicxmlservice" },
    },
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
    naming: { required_suffix: ["LLC", "L.L.C."], restricted_words: ["Bank", "Insurance"] },
    compliance: { franchise_tax_due: "June 1" },
    verification: {
      last_verified: "2026-03-18T00:00:00.000Z",
      sources: [{ name: "Delaware SOS", url: "https://corp.delaware.gov", accessed_at: "2026-03-18T00:00:00.000Z" }],
      verified_by: "human_review",
      confidence: 0.98,
    },
  };

  it("accepts valid formation rules", () => {
    expect(() => FormationRulesSchema.parse(validFormation)).not.toThrow();
  });

  it("rejects negative fee amounts", () => {
    const invalid = { ...validFormation, fees: { standard: { ...validFormation.fees.standard, amount_cents: -100 } } };
    expect(() => FormationRulesSchema.parse(invalid)).toThrow();
  });

  it("rejects invalid state code", () => {
    const invalid = { ...validFormation, state: "XX" };
    expect(() => FormationRulesSchema.parse(invalid)).toThrow();
  });
});

describe("StateTaxRulesSchema", () => {
  const validTaxRules = {
    state: "CA",
    state_name: "California",
    tax_year: 2026,
    income_tax: {
      type: "progressive",
      brackets: {
        single: [
          { min_income_cents: 0, max_income_cents: 1112200, rate_bps: 100 },
          { min_income_cents: 1112200, max_income_cents: 2637500, rate_bps: 200 },
          { min_income_cents: 2637500, max_income_cents: null, rate_bps: 400 },
        ],
        married_filing_jointly: [
          { min_income_cents: 0, max_income_cents: 2224400, rate_bps: 100 },
          { min_income_cents: 2224400, max_income_cents: null, rate_bps: 200 },
        ],
        married_filing_separately: [
          { min_income_cents: 0, max_income_cents: 1112200, rate_bps: 100 },
        ],
        head_of_household: [
          { min_income_cents: 0, max_income_cents: 1112200, rate_bps: 100 },
        ],
      },
    },
    standard_deductions: [
      { filing_status: "single", amount_cents: 560800 },
      { filing_status: "married_filing_jointly", amount_cents: 1121600 },
    ],
    personal_exemption: { amount_cents: 14400, phases_out: true, phase_out_threshold_cents: 22100000 },
    notable_credits: [{ name: "Renter's Credit", description: "Credit for renters", max_amount_cents: 6000 }],
    notable_deductions: [],
    local_taxes: { has_local_income_tax: false },
    reciprocity: { has_reciprocity: false },
    dor_url: "https://www.ftb.ca.gov",
    verification: {
      last_verified: "2026-03-18T00:00:00.000Z",
      sources: [{ name: "CA FTB", url: "https://www.ftb.ca.gov", accessed_at: "2026-03-18T00:00:00.000Z" }],
      verified_by: "ai_extraction",
      confidence: 0.9,
    },
  };

  it("accepts valid tax rules", () => {
    expect(() => StateTaxRulesSchema.parse(validTaxRules)).not.toThrow();
  });

  it("rejects rate above 10000 bps (100%)", () => {
    const invalid = JSON.parse(JSON.stringify(validTaxRules));
    invalid.income_tax.brackets.single[0].rate_bps = 15000;
    expect(() => StateTaxRulesSchema.parse(invalid)).toThrow();
  });

  it("rejects tax year outside range", () => {
    const invalid = { ...validTaxRules, tax_year: 2020 };
    expect(() => StateTaxRulesSchema.parse(invalid)).toThrow();
  });
});
