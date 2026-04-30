import { getBrainPersonas } from "@/lib/command-center";

export type ComposePersonaOption = { id: string; label: string };

/** Used when Brain personas are unavailable (local dev / misconfigured secret). */
export const COMPOSE_PERSONA_FALLBACK: ComposePersonaOption[] = [
  { id: "cfo", label: "CFO" },
  { id: "ea", label: "EA" },
  { id: "coach", label: "Coach" },
  { id: "infra", label: "Infra" },
  { id: "legal", label: "Legal" },
];

export async function resolveComposePersonaOptions(): Promise<ComposePersonaOption[]> {
  const personas = await getBrainPersonas();
  if (personas.length === 0) return COMPOSE_PERSONA_FALLBACK;
  return personas.map((p) => ({ id: p.name, label: p.name }));
}
