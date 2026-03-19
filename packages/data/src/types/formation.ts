import type { StateCode, VerificationMeta } from "./common";

export type FilingMethod = "api" | "portal" | "mail";

export type FilingTier = {
  method: FilingMethod;
  url?: string;
  notes?: string;
};

export type StateFee = {
  /** Fee amount in cents (e.g., 10000 = $100.00) */
  amount_cents: number;
  description: string;
  is_expedited: boolean;
  processing_days?: number;
};

export type FormationRules = {
  state: StateCode;
  state_name: string;
  entity_type: "LLC";
  sos_url: string;
  filing_office: string;

  fees: {
    standard: StateFee;
    expedited?: StateFee;
    name_reservation?: StateFee;
  };

  filing: {
    primary: FilingTier;
    fallback?: FilingTier;
    portal_url?: string;
    api_endpoint?: string;
  };

  requirements: {
    articles_of_organization: boolean;
    operating_agreement_required: boolean;
    publication_required: boolean;
    registered_agent_required: boolean;
    annual_report_required: boolean;
    annual_report_fee_cents?: number;
    franchise_tax: boolean;
    franchise_tax_amount_cents?: number;
  };

  processing: {
    standard_days: number;
    expedited_days?: number;
  };

  naming: {
    required_suffix: string[];
    restricted_words: string[];
    name_check_url?: string;
  };

  compliance: {
    annual_report_due?: string;
    franchise_tax_due?: string;
    first_report_due_after_formation_days?: number;
  };

  notes?: string;
  verification: VerificationMeta;
};
