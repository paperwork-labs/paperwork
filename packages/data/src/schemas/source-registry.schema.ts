import { z } from "zod";
import { StateCodeSchema } from "./common.schema";

const SourceEntrySchema = z.object({
  name: z.string().min(1),
  url: z.string().url(),
  type: z.enum(["sos", "dor", "tax_foundation", "aggregator", "official"]),
  scrape_method: z.enum(["table_extract", "page_parse", "api", "manual"]),
  notes: z.string().optional(),
});

export const StateSourcesSchema = z.object({
  state: StateCodeSchema,
  state_name: z.string().min(1),
  tax_sources: z.array(SourceEntrySchema).min(1),
  formation_sources: z.array(SourceEntrySchema).min(1),
  compliance_sources: z.array(SourceEntrySchema).optional(),
  last_validated: z.string().datetime(),
});

export type StateSources = z.infer<typeof StateSourcesSchema>;
export type SourceEntry = z.infer<typeof SourceEntrySchema>;
