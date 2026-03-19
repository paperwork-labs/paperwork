import { z } from "zod";
import { StateCodeSchema, VerificationMetaSchema } from "./common.schema";

const TaxTypeSchema = z.enum(["flat", "progressive", "none"]);

const FilingStatusSchema = z.enum([
  "single",
  "married_filing_jointly",
  "married_filing_separately",
  "head_of_household",
]);

const TaxBracketSchema = z.object({
  min_income_cents: z.number().int().nonnegative(),
  max_income_cents: z.number().int().positive().nullable(),
  rate_bps: z.number().int().nonnegative().max(10000),
});

const StandardDeductionSchema = z.object({
  filing_status: FilingStatusSchema,
  amount_cents: z.number().int().nonnegative(),
});

const IncomeTaxNone = z.object({
  type: z.literal("none"),
});

const IncomeTaxFlat = z.object({
  type: z.literal("flat"),
  flat_rate_bps: z.number().int().nonnegative().max(10000),
});

const IncomeTaxProgressive = z.object({
  type: z.literal("progressive"),
  brackets: z.record(FilingStatusSchema, z.array(TaxBracketSchema)),
});

const IncomeTaxSchema = z.discriminatedUnion("type", [
  IncomeTaxNone,
  IncomeTaxFlat,
  IncomeTaxProgressive,
]);

export const StateTaxRulesSchema = z.object({
  state: StateCodeSchema,
  state_name: z.string().min(1),
  tax_year: z.number().int().min(2024).max(2030),

  income_tax: IncomeTaxSchema,

  standard_deductions: z.array(StandardDeductionSchema),

  personal_exemption: z.object({
    amount_cents: z.number().int().nonnegative(),
    phases_out: z.boolean(),
    phase_out_threshold_cents: z.number().int().nonnegative().optional(),
  }),

  notable_credits: z.array(z.object({
    name: z.string().min(1),
    description: z.string().min(1),
    max_amount_cents: z.number().int().nonnegative().optional(),
  })),

  notable_deductions: z.array(z.object({
    name: z.string().min(1),
    description: z.string().min(1),
    max_amount_cents: z.number().int().nonnegative().optional(),
  })),

  local_taxes: z.object({
    has_local_income_tax: z.boolean(),
    notable_localities: z.array(z.string()).optional(),
  }),

  reciprocity: z.object({
    has_reciprocity: z.boolean(),
    reciprocal_states: z.array(StateCodeSchema).optional(),
  }),

  dor_url: z.string().url(),
  tax_foundation_url: z.string().url().optional(),
  notes: z.string().optional(),
  verification: VerificationMetaSchema,
});
