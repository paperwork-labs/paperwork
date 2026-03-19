import { z } from "zod";
import { StateCodeSchema, VerificationMetaSchema } from "./common.schema";

const FilingMethodSchema = z.enum(["api", "portal", "mail"]);

const FilingTierSchema = z.object({
  method: FilingMethodSchema,
  url: z.string().url().optional(),
  notes: z.string().optional(),
});

const StateFeeSchema = z.object({
  amount_cents: z.number().int().nonnegative(),
  description: z.string().min(1),
  is_expedited: z.boolean(),
  processing_days: z.number().int().positive().optional(),
});

export const FormationRulesSchema = z.object({
  state: StateCodeSchema,
  state_name: z.string().min(1),
  entity_type: z.literal("LLC"),
  sos_url: z.string().url(),
  filing_office: z.string().min(1),

  fees: z.object({
    standard: StateFeeSchema,
    expedited: StateFeeSchema.optional(),
    name_reservation: StateFeeSchema.optional(),
  }),

  filing: z.object({
    primary: FilingTierSchema,
    fallback: FilingTierSchema.optional(),
    portal_url: z.string().url().optional(),
    api_endpoint: z.string().url().optional(),
  }),

  requirements: z.object({
    articles_of_organization: z.boolean(),
    operating_agreement_required: z.boolean(),
    publication_required: z.boolean(),
    registered_agent_required: z.boolean(),
    annual_report_required: z.boolean(),
    annual_report_fee_cents: z.number().int().nonnegative().optional(),
    franchise_tax: z.boolean(),
    franchise_tax_amount_cents: z.number().int().nonnegative().optional(),
  }),

  processing: z.object({
    standard_days: z.number().int().positive(),
    expedited_days: z.number().int().positive().optional(),
  }),

  naming: z.object({
    required_suffix: z.array(z.string()).min(1),
    restricted_words: z.array(z.string()),
    name_check_url: z.string().url().optional(),
  }),

  compliance: z.object({
    annual_report_due: z.string().optional(),
    franchise_tax_due: z.string().optional(),
    first_report_due_after_formation_days: z.number().int().positive().optional(),
  }),

  notes: z.string().optional(),
  verification: VerificationMetaSchema,
});
