export const PERSONA_TEAMS: Record<string, string> = {
  // Executive Council
  strategy: "Executive Council",
  cfo: "Executive Council",
  cpa: "Executive Council",
  tax: "Executive Council",
  legal: "Executive Council",
  ea: "Executive Council",
  "capital-allocator": "Executive Council",
  partnerships: "Executive Council",
  // Engineering
  engineering: "Engineering",
  qa: "Engineering",
  "infra-ops": "Engineering",
  "ops-engineer": "Engineering",
  "agent-ops": "Engineering",
  "secrets-ops": "Engineering",
  "revenue-engineer": "Engineering",
  // Product
  "ux-lead": "Product",
  ux: "Product",
  growth: "Product",
  brand: "Product",
  // Domain Specialists
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
  // Brain
  "brain-skill-engineer": "Brain",
  "persona-promoter": "Brain",
  "model-routing-strategist": "Brain",
};

export const TEAM_DESCRIPTIONS: Record<string, string> = {
  "Executive Council": "Leadership team. Strategy, money, legal.",
  Engineering: "Builds and runs the platform.",
  Product: "Design, growth, brand.",
  "Domain Specialists": "Trading, market data, alpha research.",
  Brain: "Brain operators and meta-personas.",
  Other: "Uncategorized owners.",
};

export const TEAM_ORDER = [
  "Executive Council",
  "Engineering",
  "Product",
  "Domain Specialists",
  "Brain",
  "Other",
];

export type HubDocForPersona = {
  slug: string;
  title: string;
  summary?: string;
  category?: string;
  owners?: string[];
};

export type PersonaGroup = {
  team: string;
  personas: {
    slug: string;
    docCount: number;
    docs: HubDocForPersona[];
  }[];
};

export function groupDocsByPersona(docs: HubDocForPersona[]): PersonaGroup[] {
  const teamMap = new Map<string, Map<string, HubDocForPersona[]>>();

  for (const doc of docs) {
    const owners = doc.owners?.length ? doc.owners : ["unowned"];
    for (const owner of owners) {
      const team = PERSONA_TEAMS[owner] ?? "Other";
      if (!teamMap.has(team)) teamMap.set(team, new Map());
      const personaMap = teamMap.get(team)!;
      if (!personaMap.has(owner)) personaMap.set(owner, []);
      personaMap.get(owner)!.push(doc);
    }
  }

  return TEAM_ORDER.flatMap((team) => {
    const personaMap = teamMap.get(team);
    if (!personaMap) return [];
    return [
      {
        team,
        personas: Array.from(personaMap.entries())
          .map(([slug, personaDocs]) => ({
            slug,
            docCount: personaDocs.length,
            docs: personaDocs,
          }))
          .sort((a, b) => b.docCount - a.docCount),
      },
    ];
  });
}
