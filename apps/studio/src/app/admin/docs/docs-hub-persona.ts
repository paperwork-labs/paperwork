import type { DocHubEntry } from "@/lib/docs";

export const PERSONA_TEAMS: Record<string, string> = {
  strategy: "Executive Council",
  cfo: "Executive Council",
  cpa: "Executive Council",
  tax: "Executive Council",
  legal: "Executive Council",
  ea: "Executive Council",
  "capital-allocator": "Executive Council",
  partnerships: "Executive Council",
  engineering: "Engineering",
  qa: "Engineering",
  "infra-ops": "Engineering",
  "ops-engineer": "Engineering",
  "agent-ops": "Engineering",
  "secrets-ops": "Engineering",
  "revenue-engineer": "Engineering",
  "ux-lead": "Product",
  ux: "Product",
  growth: "Product",
  brand: "Product",
  "portfolio-manager": "Domain Specialists",
  "quant-analyst": "Domain Specialists",
  microstructure: "Domain Specialists",
  "systematic-trader": "Domain Specialists",
  "swing-trader": "Domain Specialists",
  "risk-manager": "Domain Specialists",
  "market-data-platform": "Domain Specialists",
  "market-data-guardian": "Domain Specialists",
  "alpha-researcher": "Domain Specialists",
  "validator-curator": "Domain Specialists",
  "token-management": "Domain Specialists",
  "brain-skill-engineer": "Brain",
  "persona-promoter": "Brain",
  "model-routing-strategist": "Brain",
};

export const PERSONA_TEAM_ORDER = [
  "Executive Council",
  "Engineering",
  "Product",
  "Domain Specialists",
  "Brain",
  "Other",
] as const;

export type PersonaTeamName = (typeof PERSONA_TEAM_ORDER)[number];

export const PERSONA_TEAM_BLURB: Record<PersonaTeamName, string> = {
  "Executive Council": "The leadership team. Sets strategy, signs off on big bets.",
  Engineering: "Builds and runs the platform.",
  Product: "Shapes the product experience, narrative, and growth loops.",
  "Domain Specialists": "Markets, portfolio, data, and risk expertise.",
  Brain: "Brain platform — persona skills, promotion, and model routing.",
  Other: "Owners not mapped to a team above.",
};

export type PersonaTeamSection = {
  team: PersonaTeamName;
  blurb: string;
  personas: Array<{ slug: string; docs: DocHubEntry[] }>;
};

export function teamForPersonaSlug(slug: string): PersonaTeamName {
  return (PERSONA_TEAMS[slug] as PersonaTeamName | undefined) ?? "Other";
}

export function buildTeamSections(entries: DocHubEntry[]): PersonaTeamSection[] {
  const byPersona = new Map<string, DocHubEntry[]>();
  for (const doc of entries) {
    for (const owner of doc.owners) {
      const list = byPersona.get(owner) ?? [];
      list.push(doc);
      byPersona.set(owner, list);
    }
  }

  const teamToPersonas = new Map<PersonaTeamName, Map<string, DocHubEntry[]>>();
  for (const [slug, docs] of byPersona) {
    const team = teamForPersonaSlug(slug);
    let personaMap = teamToPersonas.get(team);
    if (!personaMap) {
      personaMap = new Map();
      teamToPersonas.set(team, personaMap);
    }
    const sortedDocs = [...docs].sort((a, b) => a.title.localeCompare(b.title));
    personaMap.set(slug, sortedDocs);
  }

  const sections: PersonaTeamSection[] = [];
  for (const team of PERSONA_TEAM_ORDER) {
    const personaMap = teamToPersonas.get(team);
    if (!personaMap?.size) continue;
    const personas = [...personaMap.entries()]
      .map(([personaSlug, docList]) => ({ slug: personaSlug, docs: docList }))
      .sort((a, b) => a.slug.localeCompare(b.slug));
    sections.push({
      team,
      blurb: PERSONA_TEAM_BLURB[team],
      personas,
    });
  }
  return sections;
}
