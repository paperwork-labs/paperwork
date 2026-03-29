/**
 * State Filing Engine Types
 *
 * Core types for automated LLC formation submission across all 50 states.
 * Three-tier architecture: API (Tier 1), Portal (Tier 2), Mail (Tier 3).
 */

import { z } from "zod";

export const FilingTier = {
  API: "api",
  PORTAL: "portal",
  MAIL: "mail",
} as const;

export type FilingTier = (typeof FilingTier)[keyof typeof FilingTier];

export const FormationStatus = {
  DRAFT: "draft",
  DOCUMENTS_READY: "documents_ready",
  SUBMITTING: "submitting",
  SUBMITTED: "submitted",
  CONFIRMED: "confirmed",
  FAILED: "failed",
  MANUAL_QUEUE: "manual_queue",
} as const;

export type FormationStatus =
  (typeof FormationStatus)[keyof typeof FormationStatus];

export const MemberRole = {
  MEMBER: "member",
  MANAGER: "manager",
  ORGANIZER: "organizer",
} as const;

export type MemberRole = (typeof MemberRole)[keyof typeof MemberRole];

export const AddressSchema = z.object({
  street1: z.string().min(1),
  street2: z.string().optional(),
  city: z.string().min(1),
  state: z.string().length(2),
  zip: z.string().min(5).max(10),
  country: z.string().default("US"),
});

export type Address = z.infer<typeof AddressSchema>;

export const MemberSchema = z.object({
  name: z.string().min(1),
  address: AddressSchema,
  role: z.enum([
    MemberRole.MEMBER,
    MemberRole.MANAGER,
    MemberRole.ORGANIZER,
  ]),
  ownershipPercentage: z.number().min(0).max(100).optional(),
  isOrganizer: z.boolean().default(false),
});

export type Member = z.infer<typeof MemberSchema>;

export const RegisteredAgentSchema = z.object({
  name: z.string().min(1),
  address: AddressSchema,
  isCommercial: z.boolean().default(false),
  agentId: z.string().optional(),
});

export type RegisteredAgent = z.infer<typeof RegisteredAgentSchema>;

export const FormationRequestSchema = z.object({
  id: z.string().uuid(),
  userId: z.string(),
  stateCode: z.string().length(2),
  businessName: z.string().min(1),
  businessPurpose: z.string().default("Any lawful purpose"),
  registeredAgent: RegisteredAgentSchema,
  members: z.array(MemberSchema).min(1),
  principalAddress: AddressSchema,
  mailingAddress: AddressSchema.optional(),
  effectiveDate: z.string().datetime().optional(),
  fiscalYearEnd: z.string().optional(),
  isManagerManaged: z.boolean().default(false),
  metadata: z.record(z.unknown()).optional(),
});

export type FormationRequest = z.infer<typeof FormationRequestSchema>;

export const FilingResultSchema = z.object({
  success: z.boolean(),
  formationId: z.string(),
  status: z.enum([
    "draft",
    "documents_ready",
    "submitting",
    "submitted",
    "confirmed",
    "failed",
    "manual_queue",
  ]),
  tier: z.enum(["api", "portal", "mail"]),
  filingNumber: z.string().optional(),
  confirmationNumber: z.string().optional(),
  filedAt: z.string().datetime().optional(),
  estimatedCompletionDate: z.string().datetime().optional(),
  screenshots: z.array(z.string()).default([]),
  documents: z.array(z.string()).default([]),
  errorCode: z.string().optional(),
  errorMessage: z.string().optional(),
  errorDetails: z.record(z.unknown()).optional(),
  retryCount: z.number().default(0),
  lastAttemptAt: z.string().datetime().optional(),
});

export type FilingResult = z.infer<typeof FilingResultSchema>;

export const PortalStepSchema = z.object({
  name: z.string(),
  url: z.string().url().optional(),
  fields: z.array(
    z.object({
      fieldId: z.string(),
      selector: z.string(),
      selectorType: z.enum(["css", "xpath", "text", "aria"]).default("css"),
      fallbackSelectors: z.array(z.string()).optional(),
      inputType: z.enum([
        "text",
        "select",
        "checkbox",
        "radio",
        "date",
        "file",
      ]),
      value: z.string().optional(),
      valueMapping: z.record(z.string()).optional(),
    })
  ),
  submitButton: z.string().optional(),
  waitForNavigation: z.boolean().default(true),
  screenshotAfter: z.boolean().default(true),
});

export type PortalStep = z.infer<typeof PortalStepSchema>;

export const PortalConfigSchema = z.object({
  stateCode: z.string().length(2),
  stateName: z.string(),
  portalUrl: z.string().url(),
  loginRequired: z.boolean().default(false),
  loginUrl: z.string().url().optional(),
  supportsRALogin: z.boolean().default(false),
  raLoginUrl: z.string().url().optional(),
  filingFee: z.number(),
  expeditedFee: z.number().optional(),
  paymentMethods: z.array(z.enum(["card", "ach", "check"])),
  steps: z.array(PortalStepSchema),
  confirmationPageSelector: z.string(),
  filingNumberSelector: z.string().optional(),
  estimatedProcessingDays: z.number(),
  lastVerified: z.string().datetime(),
  notes: z.string().optional(),
});

export type PortalConfig = z.infer<typeof PortalConfigSchema>;

export interface FilingHandler {
  tier: FilingTier;
  supportedStates: string[];
  submit(request: FormationRequest): Promise<FilingResult>;
  checkStatus(formationId: string): Promise<FilingResult>;
  canHandle(stateCode: string): boolean;
}

export interface FilingOrchestrator {
  dispatch(request: FormationRequest): Promise<FilingResult>;
  getHandlerForState(stateCode: string): FilingHandler | null;
  checkStatus(formationId: string, stateCode: string): Promise<FilingResult>;
}

export interface ScreenshotCapture {
  capture(page: unknown, stepName: string): Promise<string>;
  uploadToStorage(buffer: Buffer, filename: string): Promise<string>;
}

export interface PaymentProcessor {
  createVirtualCard(amount: number, description: string): Promise<CardDetails>;
  deactivateCard(cardId: string): Promise<void>;
  getCardDetails(cardId: string): Promise<CardDetails>;
}

export interface CardDetails {
  cardId: string;
  cardNumber: string;
  expMonth: string;
  expYear: string;
  cvv: string;
  spendLimit: number;
  status: "active" | "inactive" | "frozen";
}

export const StateFilingTiers: Record<string, FilingTier> = {
  DE: "api",
  CA: "portal",
  TX: "portal",
  FL: "portal",
  NY: "portal",
  WY: "portal",
  NV: "portal",
  IL: "portal",
  GA: "portal",
  WA: "portal",
};

export function getFilingTier(stateCode: string): FilingTier {
  return StateFilingTiers[stateCode.toUpperCase()] ?? "portal";
}
