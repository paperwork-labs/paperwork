import type { ReactNode } from "react";

export type PersonaRow = {
  id: string;
  name: string;
  description: string;
  model: string | null;
  status: string;
  relative_path: string;
  markdown_body?: string;
};

export type CostWindowPayload = {
  window: string;
  personas: { persona: string; tokens_in: number; tokens_out: number; usd: number }[];
  has_file: boolean;
};

export type RoutingPayload = {
  derived_from_code?: boolean;
  edit_path?: string;
  tag_to_persona?: Record<string, string>;
  content_keyword_to_persona?: Record<string, string[]>;
  default_persona?: string;
  note?: string;
};

export type ActivityPayload = {
  events: {
    id?: string;
    at?: string;
    persona?: string;
    conversation_id?: string;
    input_excerpt?: string;
    output_excerpt?: string;
  }[];
  has_file: boolean;
  parse_error?: boolean;
};

export type PersonasPageInitial = {
  brainConfigured: boolean;
  personas: PersonaRow[] | null;
  cost7d: CostWindowPayload | null;
  cost30d: CostWindowPayload | null;
  routing: RoutingPayload | null;
  activity: ActivityPayload | null;
  modelRegistryMarkdown: string;
  modelRegistryLastReviewed: string | null;
};