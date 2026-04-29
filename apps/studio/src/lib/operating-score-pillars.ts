/** Canonical pillar order from `apis/brain/data/operating_score_spec.yaml`. */

export const OPERATING_SCORE_PILLAR_ORDER = [
  "autonomy",
  "dora_elite",
  "stack_modernity",
  "web_perf_ux",
  "a11y_design_system",
  "code_quality",
  "data_architecture",
  "reliability_security",
  "knowledge_capital",
  "persona_coverage",
  "audit_freshness",
] as const;

export type OperatingScorePillarId = (typeof OPERATING_SCORE_PILLAR_ORDER)[number];

const LABELS: Record<OperatingScorePillarId, string> = {
  autonomy: "Autonomy",
  dora_elite: "DORA elite",
  stack_modernity: "Stack modernity",
  web_perf_ux: "Web perf & UX",
  a11y_design_system: "A11y & design system",
  code_quality: "Code quality",
  data_architecture: "Data architecture",
  reliability_security: "Reliability & security",
  knowledge_capital: "Knowledge capital",
  persona_coverage: "Persona coverage",
  audit_freshness: "Audit freshness",
};

export function operatingScorePillarLabel(id: string): string {
  if (id in LABELS) return LABELS[id as OperatingScorePillarId];
  return id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
