import type { StateCode, VerificationMeta } from "./common";

export type TaxType = "flat" | "progressive" | "none";

export type TaxBracket = {
  /** Minimum income in cents for this bracket */
  min_income_cents: number;
  /** Maximum income in cents (null = no cap) */
  max_income_cents: number | null;
  /** Tax rate as basis points (e.g., 500 = 5.00%) */
  rate_bps: number;
};

export type FilingStatus =
  | "single"
  | "married_filing_jointly"
  | "married_filing_separately"
  | "head_of_household";

export type StandardDeduction = {
  filing_status: FilingStatus;
  /** Deduction amount in cents */
  amount_cents: number;
};

export type StateTaxRules = {
  state: StateCode;
  state_name: string;
  tax_year: number;

  income_tax:
    | { type: "none" }
    | { type: "flat"; flat_rate_bps: number }
    | { type: "progressive"; brackets: Record<FilingStatus, TaxBracket[]> };

  standard_deductions: StandardDeduction[];

  personal_exemption: {
    /** Exemption amount in cents per person */
    amount_cents: number;
    phases_out: boolean;
    phase_out_threshold_cents?: number;
  };

  notable_credits: {
    name: string;
    description: string;
    max_amount_cents?: number;
  }[];

  notable_deductions: {
    name: string;
    description: string;
    max_amount_cents?: number;
  }[];

  local_taxes: {
    has_local_income_tax: boolean;
    notable_localities?: string[];
  };

  reciprocity: {
    has_reciprocity: boolean;
    reciprocal_states?: StateCode[];
  };

  dor_url: string;
  tax_foundation_url?: string;
  notes?: string;
  verification: VerificationMeta;
};
