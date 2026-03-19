import { z } from "zod";

export const StateCodeSchema = z.enum([
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
  "DC",
]);

export const SourceSchema = z.object({
  name: z.string().min(1),
  url: z.string().url(),
  accessed_at: z.string().datetime(),
});

export const VerificationMetaSchema = z.object({
  last_verified: z.string().datetime(),
  sources: z.array(SourceSchema).min(1),
  verified_by: z.enum(["ai_extraction", "human_review", "automated_validation"]),
  confidence: z.number().min(0).max(1),
});
